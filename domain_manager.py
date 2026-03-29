"""
Domain management and API integration.

Supports automated domain purchasing for burner email rotation.
"""
from __future__ import annotations

import logging
import os
import random
import re
import string
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def _parse_price_value(raw_price: object, default: float = 999.0) -> float:
    """Convert registrar price payloads into a float."""
    if raw_price is None:
        return default
    if isinstance(raw_price, (int, float)):
        return float(raw_price)
    if isinstance(raw_price, str):
        cleaned = raw_price.strip().replace("$", "").replace("€", "").replace(",", "")
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", cleaned)
        if not match:
            return default
        try:
            return float(match.group(1))
        except ValueError:
            return default
    return default


class DomainAPIClient(ABC):
    """Base interface for domain registrar API clients."""

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    def search_domain(self, domain: str) -> Dict:
        """Return availability and pricing info for a domain."""

    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase a domain."""

    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Return pricing details for a TLD."""

    def list_domains(self) -> List[str]:
        """List owned domains for this registrar/account."""
        return []


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management.
    https://porkbun.com/api/json/v3/documentation
    """

    BASE_URL = "https://porkbun.com/api/json/v3"

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()

    def _make_request(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make API request."""
        url = f"{self.BASE_URL}/{endpoint}"
        payload = {
            "apikey": self.api_key,
            "secretapikey": self.api_secret,
        }
        if data:
            payload.update(data)
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("Porkbun API request failed: %s", exc)
            return {"status": "ERROR", "message": str(exc)}

    def search_domain(self, domain: str) -> Dict:
        """Check if a domain is available."""
        result = self._make_request("domain/check", {"domain": domain})
        available = result.get("isAvailable", False)
        if isinstance(available, str):
            available = available.lower() in {"true", "yes", "1"}

        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and bool(available),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
            "message": result.get("message", ""),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain.
        Note: this actually purchases the domain and charges your account.
        """
        result = self._make_request("domain/create", {"domain": domain, "years": years})
        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId"),
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get pricing for TLD."""
        result = self._make_request("pricing/get", {"tld": tld})
        if result.get("status") == "SUCCESS":
            pricing = result.get("pricing", {})
            return {
                "tld": tld,
                "registration": pricing.get("registration"),
                "renewal": pricing.get("renewal"),
                "transfer": pricing.get("transfer"),
                "currency": "USD",
            }
        return {}

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("domain/listAll")
        if result.get("status") == "SUCCESS":
            domains = result.get("domains", [])
            return [item.get("domain") for item in domains if item.get("domain")]
        return []


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap API client for domain management.
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        api_user: str,
        username: Optional[str] = None,
        client_ip: Optional[str] = None,
        use_sandbox: bool = False,
    ):
        super().__init__(api_key=api_key, api_secret=None)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip or os.environ.get("NAMECHEAP_CLIENT_IP", "127.0.0.1")
        self.base_url = self.SANDBOX_URL if use_sandbox else self.BASE_URL
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict] = None) -> Dict:
        request_params = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            request_params.update(params)

        try:
            response = self.session.get(self.base_url, params=request_params, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            status = root.attrib.get("Status", "ERROR")
            errors = [err.text or "" for err in root.findall(".//{*}Error")]
            message = "; ".join(msg.strip() for msg in errors if msg.strip())
            if status != "OK" and not message:
                message = "Namecheap request failed"
            return {
                "ok": status == "OK",
                "status": status,
                "root": root,
                "message": message,
            }
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return {"ok": False, "status": "ERROR", "root": None, "message": str(exc)}

    def search_domain(self, domain: str) -> Dict:
        """Check if a domain is available."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not result["ok"] or result["root"] is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": result.get("message", ""),
            }

        domain_result = result["root"].find(".//{*}DomainCheckResult")
        available = False
        price = None
        if domain_result is not None:
            available = (domain_result.attrib.get("Available", "false").lower() == "true")
            premium_price = domain_result.attrib.get("PremiumRegistrationPrice")
            if premium_price:
                price = premium_price
        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "message": result.get("message", ""),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Attempt to purchase a domain.

        Namecheap may require additional contact/profile data depending on account
        settings. API error details are returned in `message`.
        """
        result = self._make_request(
            "namecheap.domains.create",
            {"DomainName": domain, "Years": years},
        )
        order_id = None
        if result.get("root") is not None:
            create_node = result["root"].find(".//{*}DomainCreateResult")
            if create_node is not None:
                order_id = create_node.attrib.get("OrderID")
        return {
            "success": bool(result.get("ok")),
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": order_id,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get registration pricing for a TLD."""
        product_name = f".{tld.lower()}"
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "register",
                "ProductName": product_name,
            },
        )
        if not result["ok"] or result["root"] is None:
            return {}

        best_price = None
        for product in result["root"].findall(".//{*}Product"):
            name = (product.attrib.get("Name") or "").lower()
            if name not in {product_name, tld.lower(), tld.upper().lower()}:
                continue
            for price in product.findall(".//{*}Price"):
                your_price = price.attrib.get("YourPrice")
                if your_price:
                    parsed = _parse_price_value(your_price, default=999.0)
                    if best_price is None or parsed < best_price:
                        best_price = parsed
        if best_price is None:
            return {}
        return {
            "tld": tld,
            "registration": f"{best_price:.2f}",
            "renewal": None,
            "transfer": None,
            "currency": "USD",
        }

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("namecheap.domains.getList")
        if not result["ok"] or result["root"] is None:
            return []
        domains = []
        for entry in result["root"].findall(".//{*}Domain"):
            name = entry.attrib.get("Name")
            if name:
                domains.append(name)
        return domains


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Automatically purchase cheap domains and rotate them.
    """

    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
    ):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.registrar = "custom" if api_client else "unconfigured"
        self.registrar_settings: Dict[str, object] = {}

    def configure(
        self,
        api_key: str,
        secret_key: str = "",
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        **kwargs,
    ) -> Dict:
        """
        Configure registrar credentials and budget.

        Supported registrars:
          - porkbun: api_key + secret_key
          - namecheap: api_key + api_user (+ optional username/client_ip)
        """
        registrar_name = (registrar or "porkbun").strip().lower()
        self.monthly_budget = float(monthly_budget)

        if registrar_name == "porkbun":
            if not api_key or not secret_key:
                raise ValueError("Porkbun requires both api_key and secret_key")
            self.api_client = PorkbunAPIClient(api_key, secret_key)
            self.registrar_settings = {"registrar": "porkbun"}
        elif registrar_name == "namecheap":
            api_user = (
                kwargs.get("api_user")
                or kwargs.get("namecheap_api_user")
                or kwargs.get("username")
            )
            username = kwargs.get("username") or kwargs.get("namecheap_username")
            client_ip = kwargs.get("client_ip") or kwargs.get("namecheap_client_ip")
            use_sandbox = bool(kwargs.get("use_sandbox", False))
            if not api_key or not api_user:
                raise ValueError("Namecheap requires api_key and api_user")
            self.api_client = NamecheapAPIClient(
                api_key=api_key,
                api_user=str(api_user),
                username=str(username) if username else None,
                client_ip=str(client_ip) if client_ip else None,
                use_sandbox=use_sandbox,
            )
            self.registrar_settings = {
                "registrar": "namecheap",
                "api_user": str(api_user),
                "username": str(username or api_user),
                "client_ip": str(client_ip or os.environ.get("NAMECHEAP_CLIENT_IP", "127.0.0.1")),
                "use_sandbox": use_sandbox,
            }
        else:
            raise ValueError(f"Unsupported registrar: {registrar_name}")

        self.registrar = registrar_name
        return self.get_config()

    def get_config(self) -> Dict:
        """Return non-secret runtime configuration details."""
        return {
            "registrar": self.registrar,
            "api_configured": self.api_client is not None,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "registrar_settings": self.registrar_settings.copy(),
        }

    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client directly."""
        self.api_client = api_client
        self.registrar = "custom"
        self.registrar_settings = {"registrar": "custom"}

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name.
        Uses cheap TLDs like .xyz, .club, .online.
        """
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        """Compatibility alias for older integration code."""
        return self.generate_random_domain(tld=tld, length=length)

    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        tlds: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain.
        Returns domain info or None.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return None

        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            result = self.api_client.search_domain(domain)
            if not result.get("available"):
                continue

            price = _parse_price_value(result.get("price"), default=999.0)
            if price == 999.0:
                pricing = self.api_client.get_pricing(tld)
                price = _parse_price_value(pricing.get("registration"), default=999.0)

            if price <= max_price:
                return {
                    "domain": domain,
                    "price": price,
                    "tld": tld,
                    "currency": result.get("currency", "USD"),
                }

        return None

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 5,
    ) -> List[Dict]:
        """Compatibility helper returning multiple candidate domains."""
        found = []
        for _ in range(limit):
            candidate = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=tlds,
            )
            if candidate:
                found.append(candidate)
        return found

    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget.
        Returns True on success.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False

        normalized_price = _parse_price_value(price, default=999.0)
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                normalized_price,
                self.monthly_budget,
            )
            return False

        result = self.api_client.purchase_domain(domain, years=1)
        if result.get("success"):
            now = datetime.now()
            self.current_spending += normalized_price
            self.owned_domains.append(
                {
                    "domain": domain,
                    "price": normalized_price,
                    "purchased_at": now,
                    "expires_at": now + timedelta(days=365),
                }
            )
            if not self.active_domain:
                self.active_domain = domain
            logger.info("Successfully purchased domain: %s for $%s", domain, normalized_price)
            return True

        logger.error("Failed to purchase domain: %s", result.get("message"))
        return False

    def rotate_domain_with_details(self) -> Dict:
        """Rotate to a new domain and return structured results."""
        domain_info = self.find_cheap_available_domain()
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {"success": False, "error": "No cheap available domain found"}

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
        )
        if not success:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded",
                "domain": domain_info["domain"],
                "price": domain_info["price"],
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "price": domain_info["price"],
            "tld": domain_info["tld"],
        }

    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain and return the active domain.
        """
        result = self.rotate_domain_with_details()
        if result.get("success"):
            return result.get("domain")
        return None

    def rotate_to_new_domain(self) -> Dict:
        """Compatibility alias used by older scripts/docs."""
        return self.rotate_domain_with_details()

    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain."""
        return self.active_domain

    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains."""
        return self.owned_domains

    def get_budget_status(self) -> Dict:
        """Get budget information."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
        }

    def export_state(self) -> Dict:
        """Export manager state as JSON-serializable data."""
        serialized = []
        for item in self.owned_domains:
            serialized.append(
                {
                    "domain": item.get("domain"),
                    "price": item.get("price"),
                    "purchased_at": (
                        item.get("purchased_at").isoformat()
                        if isinstance(item.get("purchased_at"), datetime)
                        else item.get("purchased_at")
                    ),
                    "expires_at": (
                        item.get("expires_at").isoformat()
                        if isinstance(item.get("expires_at"), datetime)
                        else item.get("expires_at")
                    ),
                }
            )
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": serialized,
            "active_domain": self.active_domain,
            "registrar": self.registrar,
            "registrar_settings": self.registrar_settings.copy(),
        }

    def import_state(self, state: Optional[Dict]) -> None:
        """Import manager state from previously exported data."""
        if not state:
            return

        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))
        self.current_spending = float(state.get("current_spending", 0.0))
        self.active_domain = state.get("active_domain")
        self.registrar = state.get("registrar", self.registrar)
        self.registrar_settings = state.get("registrar_settings", self.registrar_settings)

        self.owned_domains = []
        for item in state.get("owned_domains", []):
            purchased_at = item.get("purchased_at")
            expires_at = item.get("expires_at")
            try:
                if isinstance(purchased_at, str):
                    purchased_at = datetime.fromisoformat(purchased_at)
            except ValueError:
                purchased_at = datetime.now()
            try:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
            except ValueError:
                expires_at = datetime.now() + timedelta(days=365)

            self.owned_domains.append(
                {
                    "domain": item.get("domain"),
                    "price": _parse_price_value(item.get("price"), default=0.0),
                    "purchased_at": purchased_at or datetime.now(),
                    "expires_at": expires_at or (datetime.now() + timedelta(days=365)),
                }
            )


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
