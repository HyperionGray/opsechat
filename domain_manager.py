"""
Domain management and API integration.
Supports automated domain purchasing for burner email rotation.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
import random
import string
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)


def _parse_price_value(raw_price: Any) -> Optional[float]:
    """Parse registrar price values into float when possible."""
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return float(raw_price)
    if isinstance(raw_price, str):
        cleaned = raw_price.replace("$", "").replace("€", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _to_bool(value: Any) -> bool:
    """Best-effort conversion for XML-style boolean strings."""
    return str(value).strip().lower() in {"1", "true", "yes"}


class DomainAPIClient(ABC):
    """Base class for domain registrar API clients."""

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available."""

    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain."""

    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD."""


class PorkbunAPIClient(DomainAPIClient):
    """Porkbun API client for domain management."""

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
        except Exception as exc:  # pragma: no cover - network failures are nondeterministic
            logger.error("Porkbun API request failed: %s", exc)
            return {"status": "ERROR", "message": str(exc)}

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        result = self._make_request("domain/check", {"domain": domain})
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and result.get("isAvailable", False),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase a domain."""
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
        if result.get("status") != "SUCCESS":
            return {}
        pricing = result.get("pricing", {})
        return {
            "tld": tld,
            "registration": pricing.get("registration"),
            "renewal": pricing.get("renewal"),
            "transfer": pricing.get("transfer"),
            "currency": "USD",
        }

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("domain/listAll")
        if result.get("status") != "SUCCESS":
            return []
        domains = result.get("domains", [])
        return [domain_info.get("domain") for domain_info in domains if domain_info.get("domain")]


class NamecheapAPIClient(DomainAPIClient):
    """Namecheap API client for domain management."""

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"
    REQUIRED_CONTACT_FIELDS = [
        "FirstName",
        "LastName",
        "Address1",
        "City",
        "StateProvince",
        "PostalCode",
        "Country",
        "Phone",
        "EmailAddress",
    ]

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str = "127.0.0.1",
        api_user: Optional[str] = None,
        use_sandbox: bool = False,
        default_contact: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key=api_key)
        self.username = username
        self.api_user = api_user or username
        self.client_ip = client_ip
        self.use_sandbox = use_sandbox
        self.default_contact = default_contact or {}
        self.session = requests.Session()

    def set_default_contact(self, contact: Dict[str, str]) -> None:
        """Set default domain contact for purchase operations."""
        self.default_contact = contact

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Make Namecheap API request and return parsed XML."""
        url = self.SANDBOX_URL if self.use_sandbox else self.BASE_URL
        request_params = {
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ApiUser": self.api_user,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            request_params.update(params)

        try:
            response = self.session.get(url, params=request_params, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception as exc:  # pragma: no cover - network failures are nondeterministic
            logger.error("Namecheap API request failed: %s", exc)
            return {"status": "ERROR", "message": str(exc)}

        errors = [error.text.strip() for error in root.findall(".//{*}Error") if error.text]
        if errors:
            message = "; ".join(errors)
            logger.error("Namecheap API error: %s", message)
            return {"status": "ERROR", "message": message}

        if root.attrib.get("Status", "").upper() != "OK":
            message = "Namecheap API returned non-OK status"
            logger.error(message)
            return {"status": "ERROR", "message": message}

        return {"status": "OK", "xml": root}

    @staticmethod
    def _extract_pricing_from_root(root: ET.Element, tld: str) -> Optional[str]:
        """Extract pricing for a given TLD from Namecheap pricing XML."""
        tld_upper = tld.upper()
        for product in root.findall(".//{*}Product"):
            product_name = (product.attrib.get("Name") or "").upper()
            if product_name and product_name != tld_upper:
                continue
            for price in product.findall(".//{*}Price"):
                price_value = price.attrib.get("YourPrice") or price.attrib.get("Price")
                if price_value:
                    return price_value
        return None

    def _get_action_price(self, tld: str, action_name: str) -> Optional[str]:
        """Fetch action-specific pricing from Namecheap."""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "DOMAINS",
                "ProductName": tld.upper(),
                "ActionName": action_name,
            },
        )
        if result.get("status") != "OK":
            return None
        return self._extract_pricing_from_root(result["xml"], tld)

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if result.get("status") != "OK":
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": result.get("message", "Unknown API error"),
            }

        check_result = result["xml"].find(".//{*}DomainCheckResult")
        if check_result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "Invalid Namecheap API response",
            }

        premium_price = _parse_price_value(check_result.attrib.get("PremiumRegistrationPrice"))
        return {
            "domain": domain,
            "available": _to_bool(check_result.attrib.get("Available", False)),
            "is_premium": _to_bool(check_result.attrib.get("IsPremiumName", False)),
            "price": premium_price,
            "currency": "USD",
        }

    def _build_purchase_contact_params(self, contact: Dict[str, str]) -> Dict[str, str]:
        """Build Namecheap create-domain contact payload."""
        missing_fields = [field for field in self.REQUIRED_CONTACT_FIELDS if not contact.get(field)]
        if missing_fields:
            raise ValueError(f"Missing required Namecheap contact fields: {', '.join(missing_fields)}")

        params: Dict[str, str] = {}
        for prefix in ("Registrant", "Admin", "Tech", "AuxBilling"):
            for field, value in contact.items():
                params[f"{prefix}{field}"] = value
        return params

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain (requires Namecheap contact profile data)."""
        if not self.default_contact:
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap contact profile not configured",
                "order_id": None,
            }

        try:
            contact_params = self._build_purchase_contact_params(self.default_contact)
        except ValueError as exc:
            return {
                "success": False,
                "domain": domain,
                "message": str(exc),
                "order_id": None,
            }

        params = {"DomainName": domain, "Years": str(years), **contact_params}
        result = self._make_request("namecheap.domains.create", params)
        if result.get("status") != "OK":
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Namecheap purchase failed"),
                "order_id": None,
            }

        create_result = result["xml"].find(".//{*}DomainCreateResult")
        success = create_result is not None and _to_bool(create_result.attrib.get("Registered", False))
        order_id = None
        if create_result is not None:
            order_id = create_result.attrib.get("OrderID")
        if not order_id:
            order_node = result["xml"].find(".//{*}OrderID")
            order_id = order_node.text if order_node is not None else None

        charged_amount = create_result.attrib.get("ChargedAmount") if create_result is not None else None
        message = "Domain purchased successfully" if success else "Domain purchase failed"
        return {
            "success": success,
            "domain": domain,
            "message": message,
            "order_id": order_id,
            "charged_amount": charged_amount,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get registration/renewal/transfer pricing for TLD."""
        normalized_tld = tld.lstrip(".")
        registration = self._get_action_price(normalized_tld, "REGISTER")
        renewal = self._get_action_price(normalized_tld, "RENEW")
        transfer = self._get_action_price(normalized_tld, "TRANSFER")
        if registration is None and renewal is None and transfer is None:
            return {}
        return {
            "tld": normalized_tld,
            "registration": registration,
            "renewal": renewal,
            "transfer": transfer,
            "currency": "USD",
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Automatically purchase cheap domains and rotate them.
    """

    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
    ):
        self.api_client = api_client
        self.registrar = registrar
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

    def set_api_client(self, api_client: DomainAPIClient, registrar: Optional[str] = None) -> None:
        """Set the domain API client."""
        self.api_client = api_client
        if registrar:
            self.registrar = registrar

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        **kwargs: Any,
    ) -> None:
        """Configure registrar and budget from route/forms."""
        normalized_registrar = registrar.strip().lower()
        self.monthly_budget = float(monthly_budget)

        if normalized_registrar == "porkbun":
            if not secret_key:
                raise ValueError("Porkbun requires API key and secret key")
            self.set_api_client(PorkbunAPIClient(api_key, secret_key), registrar="porkbun")
            return

        if normalized_registrar == "namecheap":
            username = kwargs.get("username")
            if not username:
                raise ValueError("Namecheap requires username")
            client_ip = kwargs.get("client_ip", "127.0.0.1")
            api_user = kwargs.get("api_user")
            use_sandbox = bool(kwargs.get("use_sandbox", False))
            default_contact = kwargs.get("default_contact")
            self.set_api_client(
                NamecheapAPIClient(
                    api_key=api_key,
                    username=username,
                    client_ip=client_ip,
                    api_user=api_user,
                    use_sandbox=use_sandbox,
                    default_contact=default_contact,
                ),
                registrar="namecheap",
            )
            return

        raise ValueError(f"Unsupported registrar: {registrar}")

    def get_config(self) -> Dict[str, Any]:
        """Expose current domain manager configuration for routes."""
        return {
            "registrar": self.registrar,
            "configured": self.api_client is not None,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """Generate random domain name."""
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def find_cheap_available_domain(self, max_price: float = 5.0, max_attempts: int = 10) -> Optional[Dict]:
        """Find a cheap available domain and return metadata."""
        if not self.api_client:
            logger.error("No API client configured")
            return None

        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            result = self.api_client.search_domain(domain)
            if not result.get("available"):
                continue

            price = _parse_price_value(result.get("price"))
            if price is None:
                pricing = self.api_client.get_pricing(tld)
                price = _parse_price_value(pricing.get("registration"))
            if price is None:
                continue

            if price <= max_price:
                return {"domain": domain, "price": price, "tld": tld}
        return None

    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """Purchase domain if within budget."""
        if not self.api_client:
            logger.error("No API client configured")
            return False

        normalized_price = _parse_price_value(price)
        if normalized_price is None:
            logger.error("Invalid domain price for %s: %s", domain, price)
            return False

        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                normalized_price,
                self.monthly_budget,
            )
            return False

        result = self.api_client.purchase_domain(domain, years=1)
        if not result.get("success"):
            logger.error("Failed to purchase domain: %s", result.get("message"))
            return False

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

    def rotate_domain(self) -> Optional[str]:
        """Rotate to a new domain by finding and purchasing one."""
        domain_info = self.find_cheap_available_domain()
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None

        success = self.purchase_domain_if_budget_allows(domain_info["domain"], domain_info["price"])
        if success:
            self.active_domain = domain_info["domain"]
            return self.active_domain
        return None

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


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
