"""
Domain management and API integration.
Supports automated domain purchasing for burner email rotation.
"""
import logging
import random
import string
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """Base class for domain registrar API clients."""

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search whether a domain is available."""
        raise NotImplementedError()

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase a domain."""
        raise NotImplementedError()

    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing for a TLD."""
        raise NotImplementedError()


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
        """Make API request."""
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
        """Check if domain is available."""
        result = self._make_request("domain/check", {"domain": domain})
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and result.get("isAvailable", False),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase domain and return purchase metadata."""
        result = self._make_request("domain/create", {"domain": domain, "years": years})
        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId"),
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
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
            return [entry.get("domain") for entry in domains if entry.get("domain")]
        return []


class NamecheapAPIClient(DomainAPIClient):
    """Namecheap XML API client for domain management."""

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"
    CONTACT_FIELDS = [
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
    OPTIONAL_CONTACT_FIELDS = ["OrganizationName", "Address2", "JobTitle", "PhoneExt"]

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        registrant_contact: Optional[Dict[str, str]] = None,
        sandbox: bool = False,
    ):
        super().__init__(api_key=api_key, api_secret=None)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.registrant_contact = registrant_contact or {}
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            payload.update(params)

        try:
            response = self.session.get(self.base_url, params=payload, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return {"success": False, "message": str(exc)}

        status = root.attrib.get("Status", "").upper()
        if status != "OK":
            errors = [entry.text for entry in root.findall(".//Errors/Error") if entry.text]
            message = "; ".join(errors) if errors else "Namecheap API returned error response"
            return {"success": False, "message": message, "root": root}

        return {"success": True, "root": root}

    @staticmethod
    def _str_to_bool(value: Optional[str]) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes"}

    def _extract_registration_price(self, root: ET.Element, tld: str) -> Optional[float]:
        tld = tld.lstrip(".").lower()
        for product in root.findall(".//Product"):
            product_name = (product.attrib.get("Name", "") or "").lstrip(".").lower()
            if product_name != tld:
                continue
            price_entry = product.find("./Price[@Duration='1']") or product.find("./Price")
            if price_entry is None:
                return None
            raw_price = price_entry.attrib.get("YourPrice") or price_entry.attrib.get("Price")
            try:
                return float(raw_price) if raw_price is not None else None
            except ValueError:
                return None
        return None

    def _build_contact_params(self) -> Dict[str, str]:
        missing = [field for field in self.CONTACT_FIELDS if not self.registrant_contact.get(field)]
        if missing:
            raise ValueError(
                "Missing required Namecheap contact fields: " + ", ".join(sorted(missing))
            )

        contact_data: Dict[str, str] = {}
        prefixes = ["Registrant", "Admin", "Tech", "AuxBilling"]
        for prefix in prefixes:
            for field in self.CONTACT_FIELDS + self.OPTIONAL_CONTACT_FIELDS:
                value = self.registrant_contact.get(field, "")
                if value:
                    contact_data[f"{prefix}{field}"] = value
        return contact_data

    def search_domain(self, domain: str) -> Dict[str, Any]:
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not result.get("success"):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": result.get("message", "unknown error"),
            }

        root = result["root"]
        check_entry = root.find(".//DomainCheckResult")
        available = self._str_to_bool(check_entry.attrib.get("Available")) if check_entry is not None else False

        price: Optional[float] = None
        if available and "." in domain:
            tld = domain.rsplit(".", 1)[1]
            price = self.get_pricing(tld).get("registration")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        if "." not in domain:
            return {"success": False, "domain": domain, "message": "Invalid domain format"}

        try:
            contact_params = self._build_contact_params()
        except ValueError as exc:
            return {"success": False, "domain": domain, "message": str(exc)}

        payload: Dict[str, Any] = {"DomainName": domain, "Years": years}
        payload.update(contact_params)

        result = self._make_request("namecheap.domains.create", payload)
        if not result.get("success"):
            return {"success": False, "domain": domain, "message": result.get("message", "")}

        root = result["root"]
        create_entry = root.find(".//DomainCreateResult")
        order_id = create_entry.attrib.get("OrderID") if create_entry is not None else None
        return {
            "success": True,
            "domain": domain,
            "message": "Domain purchased successfully",
            "order_id": order_id,
        }

    def get_pricing(self, tld: str) -> Dict[str, Any]:
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductName": tld.lstrip("."),
            },
        )
        if not result.get("success"):
            return {}
        registration = self._extract_registration_price(result["root"], tld=tld)
        return {
            "tld": tld.lstrip("."),
            "registration": registration,
            "renewal": None,
            "transfer": None,
            "currency": "USD",
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Automatically purchases cheap domains and rotates them.
    """

    def __init__(self, api_client: Optional[DomainAPIClient] = None, monthly_budget: float = 50.0):
        self.api_client = api_client  # Backward-compatible primary reference
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.primary_provider: Optional[str] = None
        self.provider_configs: Dict[str, Dict[str, Any]] = {}
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict[str, Any]] = []
        self.active_domain: Optional[str] = None
        self.last_provider_used: Optional[str] = None

        if api_client:
            self.api_clients["default"] = api_client
            self.primary_provider = "default"

    def set_api_client(self, api_client: DomainAPIClient, provider_name: str = "default") -> None:
        """Set the default API client and also register it by provider name."""
        self.api_client = api_client
        self.add_api_client(provider_name, api_client)
        self.set_primary_provider(provider_name)

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient) -> None:
        """Register an additional registrar API client."""
        normalized_name = provider_name.strip().lower()
        if not normalized_name:
            raise ValueError("Provider name cannot be empty")
        self.api_clients[normalized_name] = api_client
        if self.primary_provider is None:
            self.primary_provider = normalized_name
        if self.api_client is None:
            self.api_client = api_client

    def set_primary_provider(self, provider_name: str) -> None:
        """Set which configured registrar should be used first."""
        normalized_name = provider_name.strip().lower()
        if normalized_name not in self.api_clients:
            raise ValueError(f"Unknown provider: {provider_name}")
        self.primary_provider = normalized_name
        self.api_client = self.api_clients[normalized_name]

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        provider: str = "porkbun",
        **kwargs: Any,
    ) -> bool:
        """
        Configure and register a registrar provider for the manager.

        Supported providers:
        - porkbun: requires api_key + secret_key
        - namecheap: requires api_key + api_user (+ optional username/client_ip/sandbox/contact)
        """
        provider_name = provider.strip().lower()
        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        if provider_name == "porkbun":
            if not api_key or not secret_key:
                raise ValueError("Porkbun configuration requires api_key and secret_key")
            client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
            self.add_api_client("porkbun", client)
            self.set_primary_provider("porkbun")
            self.provider_configs["porkbun"] = {
                "configured": True,
                "api_key_set": True,
                "secret_key_set": True,
            }
            return True

        if provider_name == "namecheap":
            api_user = kwargs.get("api_user")
            username = kwargs.get("username")
            client_ip = kwargs.get("client_ip", "127.0.0.1")
            sandbox = bool(kwargs.get("sandbox", False))
            registrant_contact = kwargs.get("registrant_contact")
            if not api_key or not api_user:
                raise ValueError("Namecheap configuration requires api_key and api_user")

            client = NamecheapAPIClient(
                api_user=api_user,
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                sandbox=sandbox,
                registrant_contact=registrant_contact,
            )
            self.add_api_client("namecheap", client)
            self.set_primary_provider("namecheap")
            self.provider_configs["namecheap"] = {
                "configured": True,
                "api_key_set": True,
                "api_user_set": True,
                "username_set": bool(username or api_user),
                "client_ip": client_ip,
                "sandbox": sandbox,
                "registrant_contact_set": bool(registrant_contact),
            }
            return True

        raise ValueError(f"Unsupported provider: {provider}")

    def get_config(self) -> Dict[str, Any]:
        """Get current manager configuration and provider status."""
        providers: Dict[str, Dict[str, Any]] = {}
        for provider_name in self.api_clients:
            providers[provider_name] = {"configured": True}
            providers[provider_name].update(self.provider_configs.get(provider_name, {}))

        return {
            "primary_provider": self.primary_provider,
            "providers": providers,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """Generate random domain name with cheap TLDs."""
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    @staticmethod
    def _normalize_price(raw_price: Any) -> Optional[float]:
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if isinstance(raw_price, str):
            sanitized = raw_price.strip().replace("$", "").replace("€", "")
            try:
                return float(sanitized)
            except ValueError:
                return None
        return None

    def _provider_sequence(self, preferred_provider: Optional[str] = None) -> List[Tuple[str, DomainAPIClient]]:
        if not self.api_clients and self.api_client:
            # Legacy mode safety path if only api_client is set manually.
            self.api_clients["default"] = self.api_client
            if self.primary_provider is None:
                self.primary_provider = "default"

        if not self.api_clients:
            return []

        ordered: List[Tuple[str, DomainAPIClient]] = []
        used = set()

        preferred = preferred_provider.strip().lower() if preferred_provider else None
        if preferred and preferred in self.api_clients:
            ordered.append((preferred, self.api_clients[preferred]))
            used.add(preferred)

        if self.primary_provider and self.primary_provider in self.api_clients and self.primary_provider not in used:
            ordered.append((self.primary_provider, self.api_clients[self.primary_provider]))
            used.add(self.primary_provider)

        for name, client in self.api_clients.items():
            if name not in used:
                ordered.append((name, client))
        return ordered

    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        preferred_provider: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find a cheap available domain across configured providers."""
        providers = self._provider_sequence(preferred_provider=preferred_provider)
        if not providers:
            logger.error("No API client configured")
            return None

        cheap_tlds = ["xyz", "club", "online", "site", "website"]

        for _ in range(max_attempts):
            for provider_name, provider_client in providers:
                tld = random.choice(cheap_tlds)
                domain = self.generate_random_domain(tld)
                result = provider_client.search_domain(domain)
                if not result.get("available"):
                    continue

                price = self._normalize_price(result.get("price"))
                if price is None:
                    pricing = provider_client.get_pricing(tld)
                    price = self._normalize_price(pricing.get("registration"))
                if price is None:
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider_name,
                    }

        return None

    def _select_purchase_provider(
        self, provider_name: Optional[str] = None
    ) -> Optional[Tuple[str, DomainAPIClient]]:
        sequence = self._provider_sequence(preferred_provider=provider_name)
        if not sequence:
            return None
        return sequence[0]

    def purchase_domain_if_budget_allows(
        self, domain: str, price: float, provider_name: Optional[str] = None
    ) -> bool:
        """Purchase domain if within budget. Returns True on success."""
        selected = self._select_purchase_provider(provider_name=provider_name)
        if not selected:
            logger.error("No API client configured")
            return False

        provider, client = selected
        if self.current_spending + price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                price,
                self.monthly_budget,
            )
            return False

        result = client.purchase_domain(domain, years=1)
        if not result.get("success"):
            logger.error("Failed to purchase domain via %s: %s", provider, result.get("message"))
            return False

        now = datetime.now()
        self.current_spending += price
        self.owned_domains.append(
            {
                "domain": domain,
                "price": price,
                "provider": provider,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365),
            }
        )
        self.last_provider_used = provider
        if not self.active_domain:
            self.active_domain = domain

        logger.info("Successfully purchased domain via %s: %s for $%s", provider, domain, price)
        return True

    def rotate_domain(
        self,
        return_details: bool = False,
        preferred_provider: Optional[str] = None,
    ) -> Any:
        """
        Rotate to a new domain by searching then purchasing within budget.

        Backward compatibility:
        - return_details=False: returns active domain string or None
        - return_details=True: returns detailed result dictionary
        """
        domain_info = self.find_cheap_available_domain(preferred_provider=preferred_provider)
        if not domain_info:
            logger.error("Could not find available cheap domain")
            if return_details:
                return {
                    "success": False,
                    "error": "Could not find available cheap domain",
                }
            return None

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider_name=domain_info.get("provider"),
        )
        if not success:
            if return_details:
                return {
                    "success": False,
                    "error": "Failed to purchase domain (budget or API error)",
                    "domain": domain_info["domain"],
                    "price": domain_info["price"],
                    "provider": domain_info.get("provider"),
                }
            return None

        self.active_domain = domain_info["domain"]
        if return_details:
            return {
                "success": True,
                "domain": self.active_domain,
                "price": domain_info["price"],
                "provider": domain_info.get("provider"),
                "budget_status": self.get_budget_status(),
            }
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
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
