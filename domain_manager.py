"""
Domain management and API integration.
Supports automated domain purchasing for burner email rotation.
"""
import logging
import random
import string
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def _coerce_price(raw_value: Any, default: Optional[float] = 999.0) -> Optional[float]:
    """Convert API price values to float safely."""
    if raw_value is None:
        return default
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    try:
        cleaned = str(raw_value).strip().replace("$", "").replace("€", "").replace(",", "")
        return float(cleaned)
    except (TypeError, ValueError):
        return default


class DomainAPIClient:
    """Base class for domain registrar API clients."""

    registrar_name = "generic"
    supports_purchase = True

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search if domain is available."""
        raise NotImplementedError("search_domain must be implemented by subclasses")

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase domain."""
        raise NotImplementedError("purchase_domain must be implemented by subclasses")

    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing for TLD."""
        raise NotImplementedError("get_pricing must be implemented by subclasses")


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management.
    https://porkbun.com/api/json/v3/documentation
    """

    registrar_name = "porkbun"
    BASE_URL = "https://porkbun.com/api/json/v3"

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()

    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check if domain is available."""
        result = self._make_request("domain/check", {"domain": domain})
        is_available = str(result.get("isAvailable", "")).lower() in {"1", "true", "yes"}

        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and is_available,
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
            "registrar": self.registrar_name,
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
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
            "registrar": self.registrar_name,
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get pricing for TLD."""
        result = self._make_request("pricing/get", {"tld": tld})
        if result.get("status") != "SUCCESS":
            return {}

        pricing = result.get("pricing", {})
        return {
            "tld": tld,
            "registration": pricing.get("registration"),
            "renewal": pricing.get("renewal"),
            "transfer": pricing.get("transfer"),
            "currency": "USD",
            "registrar": self.registrar_name,
        }

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("domain/listAll")
        if result.get("status") != "SUCCESS":
            return []

        domains = result.get("domains", [])
        return [d.get("domain") for d in domains if d.get("domain")]


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap API client.

    Supports domain availability checks and pricing. Purchase is intentionally
    disabled by default here because Namecheap registration requires a complete
    contact profile payload that should be handled explicitly in a separate flow.
    """

    registrar_name = "namecheap"
    supports_purchase = False
    PRODUCTION_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        api_username: str,
        client_ip: str = "127.0.0.1",
        use_sandbox: bool = False,
    ):
        super().__init__(api_key, api_username)
        self.api_username = api_username
        self.client_ip = client_ip
        self.base_url = self.SANDBOX_URL if use_sandbox else self.PRODUCTION_URL
        self.session = requests.Session()

    def _request(self, command: str, extra_params: Optional[Dict[str, Any]] = None) -> Optional[ET.Element]:
        """Perform Namecheap XML API request and return parsed root element."""
        params = {
            "ApiUser": self.api_username,
            "ApiKey": self.api_key,
            "UserName": self.api_username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if extra_params:
            params.update(extra_params)

        try:
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return None

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            logger.error("Namecheap API returned invalid XML: %s", exc)
            return None

        errors = [e.text.strip() for e in root.findall(".//Errors/Error") if e.text and e.text.strip()]
        if errors:
            logger.error("Namecheap API error: %s", "; ".join(errors))
            return None

        return root

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check if domain is available via Namecheap."""
        root = self._request("namecheap.domains.check", {"DomainList": domain})
        if root is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "registrar": self.registrar_name,
            }

        result = root.find(".//DomainCheckResult")
        if result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "registrar": self.registrar_name,
            }

        available = str(result.attrib.get("Available", "")).lower() in {"1", "true", "yes"}
        price_raw = (
            result.attrib.get("PremiumRegistrationPrice")
            or result.attrib.get("RegistrationPrice")
            or result.attrib.get("Price")
        )

        return {
            "domain": result.attrib.get("Domain", domain),
            "available": available,
            "price": _coerce_price(price_raw, default=None),
            "currency": "USD",
            "registrar": self.registrar_name,
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Return explicit unsupported response for automated purchase."""
        return {
            "success": False,
            "domain": domain,
            "message": (
                "Namecheap automated purchase is disabled in this flow. "
                "Use a contact-profile aware registration path."
            ),
            "registrar": self.registrar_name,
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get approximate registration pricing from Namecheap."""
        root = self._request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductName": tld,
            },
        )
        if root is None:
            return {}

        price_value: Optional[float] = None
        for product_price in root.findall(".//ProductPrice"):
            candidate = _coerce_price(product_price.attrib.get("Price"), default=None)
            if candidate is not None:
                price_value = candidate
                break

        return {
            "tld": tld,
            "registration": price_value,
            "renewal": None,
            "transfer": None,
            "currency": "USD",
            "registrar": self.registrar_name,
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Supports one or more registrar clients.
    """

    def __init__(self, api_client: Optional[DomainAPIClient] = None, monthly_budget: float = 50.0):
        self.monthly_budget = float(monthly_budget)
        self.current_spending = 0.0
        self.owned_domains: List[Dict[str, Any]] = []
        self.active_domain: Optional[str] = None
        self.active_registrar: Optional[str] = None
        self.api_clients: List[DomainAPIClient] = []
        self._config: Dict[str, Any] = {}

        if api_client:
            self.set_api_client(api_client)

    @property
    def api_client(self) -> Optional[DomainAPIClient]:
        """Backwards-compatible single active client access."""
        if not self.api_clients:
            return None
        return self.api_clients[0]

    def set_api_client(self, api_client: DomainAPIClient):
        """Set a single active domain API client."""
        self.api_clients = [api_client]
        self.active_registrar = getattr(api_client, "registrar_name", None)

    def add_api_client(self, api_client: DomainAPIClient):
        """Add an additional domain API client for fallback or comparison."""
        self.api_clients.append(api_client)
        if self.active_registrar is None:
            self.active_registrar = getattr(api_client, "registrar_name", None)

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Configure manager with registrar credentials."""
        self.monthly_budget = float(monthly_budget)
        registrar_key = (registrar or "porkbun").strip().lower()

        if registrar_key == "porkbun":
            if not secret_key:
                raise ValueError("Porkbun configuration requires secret_key")
            client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
            self.set_api_client(client)
            self._config = {
                "registrar": "porkbun",
                "api_key": api_key,
                "secret_key": secret_key,
                "monthly_budget": self.monthly_budget,
            }
            return self.get_config()

        if registrar_key == "namecheap":
            api_username = kwargs.get("api_username") or kwargs.get("username") or secret_key
            if not api_username:
                raise ValueError("Namecheap configuration requires api_username")
            client_ip = kwargs.get("client_ip", "127.0.0.1")
            use_sandbox = bool(kwargs.get("use_sandbox", False))
            client = NamecheapAPIClient(
                api_key=api_key,
                api_username=api_username,
                client_ip=client_ip,
                use_sandbox=use_sandbox,
            )
            self.set_api_client(client)
            self._config = {
                "registrar": "namecheap",
                "api_key": api_key,
                "api_username": api_username,
                "client_ip": client_ip,
                "use_sandbox": use_sandbox,
                "monthly_budget": self.monthly_budget,
            }
            return self.get_config()

        raise ValueError(f"Unsupported registrar: {registrar}")

    def get_config(self) -> Dict[str, Any]:
        """Return non-secret configuration/status summary."""
        config = {
            "configured": bool(self.api_clients),
            "registrar": self.active_registrar,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "api_key_configured": bool(self._config.get("api_key")),
        }

        if self.active_registrar == "porkbun":
            config["secret_key_configured"] = bool(self._config.get("secret_key"))
        elif self.active_registrar == "namecheap":
            config["api_username_configured"] = bool(self._config.get("api_username"))
            config["client_ip"] = self._config.get("client_ip")
            config["use_sandbox"] = bool(self._config.get("use_sandbox", False))

        return config

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name.
        Uses cheap TLDs like .xyz, .club, .online.
        """
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def find_cheap_available_domain(self, max_price: float = 5.0, max_attempts: int = 10) -> Optional[Dict[str, Any]]:
        """
        Find a cheap available domain across configured registrars.
        Returns domain info or None.
        """
        if not self.api_clients:
            logger.error("No API client configured")
            return None

        cheap_tlds = ["xyz", "club", "online", "site", "website"]

        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            for client in self.api_clients:
                domain = self.generate_random_domain(tld)
                result = client.search_domain(domain)

                if not result.get("available"):
                    continue

                price = _coerce_price(result.get("price"), default=999.0)
                if price is None or price > max_price:
                    continue

                return {
                    "domain": result.get("domain", domain),
                    "price": price,
                    "tld": tld,
                    "registrar": result.get("registrar", getattr(client, "registrar_name", "unknown")),
                    "api_client": client,
                }

        return None

    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        api_client: Optional[DomainAPIClient] = None,
    ) -> bool:
        """
        Purchase domain if within budget.
        Returns True on success.
        """
        client = api_client or self.api_client
        if client is None:
            logger.error("No API client configured")
            return False

        if self.current_spending + price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                price,
                self.monthly_budget,
            )
            return False

        if not bool(getattr(client, "supports_purchase", True)):
            logger.warning("Registrar %s does not support automated purchase in this flow", client.registrar_name)
            return False

        result = client.purchase_domain(domain, years=1)
        if not result.get("success"):
            logger.error("Failed to purchase domain: %s", result.get("message"))
            return False

        self.current_spending += price
        self.owned_domains.append(
            {
                "domain": domain,
                "price": price,
                "registrar": result.get("registrar", getattr(client, "registrar_name", "unknown")),
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365),
            }
        )

        if not self.active_domain:
            self.active_domain = domain
            self.active_registrar = result.get("registrar", getattr(client, "registrar_name", self.active_registrar))

        logger.info("Successfully purchased domain: %s for $%s", domain, price)
        return True

    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain.
        Finds and purchases a new cheap domain.
        """
        domain_info = self.find_cheap_available_domain()
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            api_client=domain_info.get("api_client"),
        )
        if not success:
            return None

        self.active_domain = domain_info["domain"]
        self.active_registrar = domain_info.get("registrar", self.active_registrar)
        return self.active_domain

    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain."""
        return self.active_domain

    def get_owned_domains(self) -> List[Dict[str, Any]]:
        """Get list of owned domains."""
        return self.owned_domains

    def get_budget_status(self) -> Dict[str, Any]:
        """Get budget information."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "active_registrar": self.active_registrar,
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
