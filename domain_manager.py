"""
Domain management and API integration.

Supports automated domain purchasing and multi-registrar fallback for burner
email rotation.
"""

from datetime import datetime, timedelta
import logging
import random
import string
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)


def _parse_price(raw_price: Any) -> Optional[float]:
    """Normalize registrar price values into a float."""
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return float(raw_price)
    if not isinstance(raw_price, str):
        return None

    cleaned = raw_price.strip().replace("$", "").replace("€", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_datetime(raw_value: Any) -> Any:
    """Convert ISO datetime strings back to datetime objects when possible."""
    if not isinstance(raw_value, str):
        return raw_value
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return raw_value


class DomainAPIClient:
    """Base class for domain registrar API clients."""

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search whether a domain is available."""
        raise NotImplementedError

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase a domain."""
        raise NotImplementedError

    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing for a TLD."""
        raise NotImplementedError


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management.
    https://porkbun.com/api/json/v3/documentation
    """

    BASE_URL = "https://porkbun.com/api/json/v3"

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()

    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a Porkbun API request."""
        url = f"{self.BASE_URL}/{endpoint}"
        payload = {"apikey": self.api_key, "secretapikey": self.api_secret}
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
        """Check if a domain is available."""
        result = self._make_request("domain/check", {"domain": domain})
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and bool(result.get("isAvailable", False)),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
            "provider": "porkbun",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase a domain.
        Note: this actually purchases the domain and charges your account.
        """
        result = self._make_request("domain/create", {"domain": domain, "years": years})
        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId"),
            "provider": "porkbun",
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get pricing for a TLD."""
        result = self._make_request("pricing/get", {"tld": tld})
        if result.get("status") == "SUCCESS":
            pricing = result.get("pricing", {})
            return {
                "tld": tld,
                "registration": pricing.get("registration"),
                "renewal": pricing.get("renewal"),
                "transfer": pricing.get("transfer"),
                "currency": "USD",
                "provider": "porkbun",
            }
        return {}

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("domain/listAll")
        if result.get("status") == "SUCCESS":
            domains = result.get("domains", [])
            return [entry.get("domain") for entry in domains if entry.get("domain")]
        return []


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap API client for domain management.
    https://www.namecheap.com/support/api/intro/
    """

    PRODUCTION_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
    ):
        super().__init__(api_key, None)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.base_url = self.SANDBOX_URL if sandbox else self.PRODUCTION_URL
        self.session = requests.Session()

    def _make_request(self, command: str, extra_params: Optional[Dict[str, Any]] = None) -> Optional[ET.Element]:
        """Make a Namecheap XML API request."""
        params: Dict[str, Any] = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if extra_params:
            params.update(extra_params)

        try:
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return None

    def _request_status(self, root: Optional[ET.Element]) -> str:
        if root is None:
            return "ERROR"
        return root.attrib.get("Status", "ERROR")

    def _request_error(self, root: Optional[ET.Element]) -> str:
        if root is None:
            return "Request failed"
        error = root.find(".//{*}Errors/{*}Error")
        if error is not None and error.text:
            return error.text
        return "Unknown error"

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check if a domain is available."""
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})
        result = root.find(".//{*}DomainCheckResult") if root is not None else None
        available = False
        price: Optional[str] = None

        if result is not None:
            available = result.attrib.get("Available", "false").lower() == "true"
            price = result.attrib.get("PremiumRegistrationPrice")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "provider": "namecheap",
            "message": self._request_error(root) if self._request_status(root) != "OK" else "",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase a domain."""
        if "." not in domain:
            return {
                "success": False,
                "domain": domain,
                "message": "Invalid domain format",
                "provider": "namecheap",
            }

        sld, tld = domain.rsplit(".", 1)
        root = self._make_request(
            "namecheap.domains.create",
            {"DomainName": domain, "SLD": sld, "TLD": tld, "Years": years},
        )
        result = root.find(".//{*}DomainCreateResult") if root is not None else None
        success = (
            self._request_status(root) == "OK"
            and result is not None
            and result.attrib.get("Registered", "false").lower() == "true"
        )

        return {
            "success": success,
            "domain": domain,
            "message": "" if success else self._request_error(root),
            "order_id": result.attrib.get("OrderID") if result is not None else None,
            "provider": "namecheap",
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get pricing for a TLD."""
        root = self._make_request(
            "namecheap.users.getPricing",
            {"ProductType": "DOMAIN", "ActionName": "REGISTER", "ProductName": tld},
        )
        if self._request_status(root) != "OK":
            return {}

        price_node = root.find(".//{*}ProductPrice") if root is not None else None
        return {
            "tld": tld,
            "registration": price_node.attrib.get("YourPrice") if price_node is not None else None,
            "currency": "USD",
            "provider": "namecheap",
        }

    def list_domains(self) -> List[str]:
        """List owned domains."""
        root = self._make_request("namecheap.domains.getList", {"PageSize": 100, "SortBy": "NAME"})
        if self._request_status(root) != "OK":
            return []
        domains = root.findall(".//{*}Domain") if root is not None else []
        return [entry.attrib.get("Name") for entry in domains if entry.attrib.get("Name")]


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Automatically purchase cheap domains and rotate them.
    """

    def __init__(self, api_client: Optional[DomainAPIClient] = None, monthly_budget: float = 50.0):
        self.api_client: Optional[DomainAPIClient] = None
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None

        self.monthly_budget = float(monthly_budget)
        self.current_spending = 0.0
        self.owned_domains: List[Dict[str, Any]] = []
        self.active_domain: Optional[str] = None

        if api_client is not None:
            self.set_api_client(api_client)

    def _provider_name_for_client(self, api_client: DomainAPIClient) -> str:
        if isinstance(api_client, PorkbunAPIClient):
            return "porkbun"
        if isinstance(api_client, NamecheapAPIClient):
            return "namecheap"
        return "default"

    def _provider_clients(self, providers: Optional[List[str]] = None) -> List[Tuple[str, DomainAPIClient]]:
        if providers:
            selected: List[Tuple[str, DomainAPIClient]] = []
            for name in providers:
                normalized = (name or "").strip().lower()
                client = self.api_clients.get(normalized)
                if client is not None:
                    selected.append((normalized, client))
            return selected

        if self.api_clients:
            items = list(self.api_clients.items())
            if self.active_provider and self.active_provider in self.api_clients:
                active_client = self.api_clients[self.active_provider]
                remaining = [(name, client) for name, client in items if name != self.active_provider]
                return [(self.active_provider, active_client)] + remaining
            return items

        if self.api_client is not None:
            return [("default", self.api_client)]
        return []

    def _resolve_purchase_client(self, provider: Optional[str] = None) -> Tuple[Optional[str], Optional[DomainAPIClient]]:
        if provider:
            normalized = provider.strip().lower()
            client = self.api_clients.get(normalized)
            if client is not None:
                return normalized, client
            return None, None

        if self.active_provider and self.active_provider in self.api_clients:
            return self.active_provider, self.api_clients[self.active_provider]
        if self.api_client is not None:
            return self.active_provider or "default", self.api_client
        return None, None

    def set_api_client(self, api_client: DomainAPIClient):
        """Set and activate a single API client (backward-compatible helper)."""
        provider = self._provider_name_for_client(api_client)
        self.add_api_client(provider, api_client, make_active=True)

    def add_api_client(self, provider: str, api_client: DomainAPIClient, make_active: bool = False):
        """Register a provider client for multi-registrar fallback."""
        normalized = provider.strip().lower()
        if not normalized:
            raise ValueError("Provider name cannot be empty")

        self.api_clients[normalized] = api_client
        if make_active or self.active_provider is None:
            self.active_provider = normalized
            self.api_client = api_client

    def set_active_provider(self, provider: str) -> bool:
        """Switch active registrar provider if registered."""
        normalized = provider.strip().lower()
        if normalized not in self.api_clients:
            return False

        self.active_provider = normalized
        self.api_client = self.api_clients[normalized]
        return True

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: float = 50.0,
        provider: str = "porkbun",
        api_secret: Optional[str] = None,
        api_username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
    ) -> Dict[str, Any]:
        """
        Configure and activate a registrar provider.

        Supports both legacy Porkbun fields and Namecheap fields.
        """
        normalized = provider.strip().lower()
        self.monthly_budget = float(monthly_budget)

        if normalized == "porkbun":
            secret = (api_secret or secret_key or "").strip()
            if not api_key or not secret:
                raise ValueError("Porkbun requires api_key and secret_key")
            client = PorkbunAPIClient(api_key.strip(), secret)
        elif normalized == "namecheap":
            username = (api_username or "").strip()
            if not username or not api_key:
                raise ValueError("Namecheap requires api_username and api_key")
            client = NamecheapAPIClient(
                api_user=username,
                api_key=api_key.strip(),
                username=username,
                client_ip=(client_ip or "127.0.0.1").strip(),
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self.add_api_client(normalized, client, make_active=True)
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Get manager runtime configuration summary for UI and APIs."""
        return {
            "configured": self.api_client is not None,
            "active_provider": self.active_provider,
            "providers": list(self.api_clients.keys()),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def export_state(self) -> Dict[str, Any]:
        """Serialize state for persistence in CLI config files."""
        serialized_domains: List[Dict[str, Any]] = []
        for entry in self.owned_domains:
            copied = dict(entry)
            if isinstance(copied.get("purchased_at"), datetime):
                copied["purchased_at"] = copied["purchased_at"].isoformat()
            if isinstance(copied.get("expires_at"), datetime):
                copied["expires_at"] = copied["expires_at"].isoformat()
            serialized_domains.append(copied)

        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "active_provider": self.active_provider,
        }

    def load_state(self, state: Dict[str, Any]):
        """Load persisted state (CLI helper)."""
        if not isinstance(state, dict):
            return

        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))
        self.current_spending = float(state.get("current_spending", self.current_spending))
        self.active_domain = state.get("active_domain", self.active_domain)

        raw_domains = state.get("owned_domains", [])
        if isinstance(raw_domains, list):
            self.owned_domains = []
            for entry in raw_domains:
                if not isinstance(entry, dict):
                    continue
                copied = dict(entry)
                copied["purchased_at"] = _parse_datetime(copied.get("purchased_at"))
                copied["expires_at"] = _parse_datetime(copied.get("expires_at"))
                self.owned_domains.append(copied)

        stored_provider = state.get("active_provider")
        if stored_provider and isinstance(stored_provider, str):
            self.set_active_provider(stored_provider)

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name.
        Uses cheap TLDs like .xyz, .club, .online.
        """
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        providers: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a cheap available domain.
        Returns domain info or None.
        """
        provider_clients = self._provider_clients(providers)
        if not provider_clients:
            logger.error("No API client configured")
            return None

        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        max_price = float(max_price)

        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for provider_name, client in provider_clients:
                result = client.search_domain(domain)
                if not result.get("available"):
                    continue

                parsed_price = _parse_price(result.get("price"))
                if parsed_price is None:
                    continue

                if parsed_price <= max_price:
                    return {
                        "domain": domain,
                        "price": parsed_price,
                        "tld": tld,
                        "provider": provider_name,
                    }

        return None

    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider: Optional[str] = None,
    ) -> bool:
        """
        Purchase a domain if within budget.
        Returns True on success.
        """
        parsed_price = _parse_price(price)
        if parsed_price is None:
            logger.error("Invalid domain price: %s", price)
            return False

        provider_name, client = self._resolve_purchase_client(provider)
        if client is None or provider_name is None:
            logger.error("No API client configured")
            return False

        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                parsed_price,
                self.monthly_budget,
            )
            return False

        result = client.purchase_domain(domain, years=1)
        if result.get("success"):
            now = datetime.now()
            self.current_spending += parsed_price
            self.owned_domains.append(
                {
                    "domain": domain,
                    "price": parsed_price,
                    "provider": provider_name,
                    "purchased_at": now,
                    "expires_at": now + timedelta(days=365),
                }
            )

            if not self.active_domain:
                self.active_domain = domain
            self.active_provider = provider_name
            self.api_client = client

            logger.info("Successfully purchased domain: %s for $%s", domain, parsed_price)
            return True

        logger.error("Failed to purchase domain: %s", result.get("message"))
        return False

    def rotate_domain(self, providers: Optional[List[str]] = None) -> Optional[str]:
        """
        Rotate to a new domain by searching and purchasing a cheap one.

        Returns newly active domain string or None.
        """
        domain_info = self.find_cheap_available_domain(providers=providers)
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider=domain_info.get("provider"),
        )
        if success:
            self.active_domain = domain_info["domain"]
            return self.active_domain
        return None

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
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
