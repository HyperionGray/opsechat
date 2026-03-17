"""
Domain management and API integration.

Supports automated domain purchasing for burner email rotation.
"""
import logging
import random
import string
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """Base class for domain registrar API clients."""

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search whether a domain is available."""

    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase domain."""

    @abstractmethod
    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing for TLD."""


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management
    https://porkbun.com/api/json/v3/documentation
    """
    
    BASE_URL = "https://porkbun.com/api/json/v3"
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()
    
    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        payload = {
            "apikey": self.api_key,
            "secretapikey": self.api_secret
        }
        
        if data:
            payload.update(data)
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Porkbun API request failed: {e}")
            return {"status": "ERROR", "message": str(e)}
    
    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check if domain is available"""
        result = self._make_request("domain/check", {"domain": domain})
        
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and result.get("isAvailable", False),
            "price": result.get("price"),
            "currency": result.get("currency", "USD")
        }
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase domain
        Note: This actually purchases the domain and charges your account
        """
        result = self._make_request("domain/create", {
            "domain": domain,
            "years": years
        })
        
        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId")
        }
    
    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get pricing for TLD"""
        result = self._make_request("pricing/get", {"tld": tld})
        
        if result.get("status") == "SUCCESS":
            pricing = result.get("pricing", {})
            return {
                "tld": tld,
                "registration": pricing.get("registration"),
                "renewal": pricing.get("renewal"),
                "transfer": pricing.get("transfer"),
                "currency": "USD"
            }
        
        return {}
    
    def list_domains(self) -> List[str]:
        """List owned domains"""
        result = self._make_request("domain/listAll")
        
        if result.get("status") == "SUCCESS":
            domains = result.get("domains", [])
            return [d.get("domain") for d in domains if d.get("domain")]
        
        return []


class NamecheapAPIClient(DomainAPIClient):
    """Namecheap API client for domain management."""

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_BASE_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str,
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key, None)
        self.username = username
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.contact_profile = contact_profile or {}
        self.base_url = self.SANDBOX_BASE_URL if sandbox else self.BASE_URL
        self.session = requests.Session()

    def _build_payload(self, command: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ApiUser": self.username,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if extra:
            payload.update(extra)
        return payload

    def _to_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = value.strip().replace("$", "").replace(",", "")
            if not normalized:
                return None
            try:
                return float(normalized)
            except ValueError:
                return None
        return None

    def _make_request(self, command: str, extra: Optional[Dict[str, Any]] = None) -> Optional[ET.Element]:
        try:
            response = self.session.get(
                self.base_url,
                params=self._build_payload(command, extra),
                timeout=30,
            )
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as exc:  # pragma: no cover - network and parser failures
            logger.error("Namecheap API request failed: %s", exc)
            return None

    def _is_success(self, root: ET.Element) -> bool:
        return root.attrib.get("Status") == "OK"

    def _find(self, root: ET.Element, suffix: str) -> Optional[ET.Element]:
        for node in root.iter():
            if node.tag.endswith(suffix):
                return node
        return None

    def search_domain(self, domain: str) -> Dict[str, Any]:
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if root is None or not self._is_success(root):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "Namecheap request failed",
            }

        node = self._find(root, "DomainCheckResult")
        if node is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "Missing DomainCheckResult",
            }

        available = str(node.attrib.get("Available", "")).lower() == "true"
        premium_price = self._to_float(
            node.attrib.get("PremiumRegistrationPrice")
            or node.attrib.get("PremiumRegistrationPriceDisplay")
        )

        return {
            "domain": domain,
            "available": available,
            "price": premium_price,
            "currency": "USD",
            "premium": str(node.attrib.get("IsPremiumName", "")).lower() == "true",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        required = [
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
        missing = [key for key in required if not self.contact_profile.get(key)]
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": f"Missing Namecheap contact fields: {', '.join(missing)}",
            }

        parsed = urlparse(f"//{domain}")
        full_domain = parsed.hostname or domain
        if "." not in full_domain:
            return {"success": False, "domain": domain, "message": "Invalid domain format"}

        sld, tld = full_domain.split(".", 1)

        contacts_payload = {}
        for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for key, value in self.contact_profile.items():
                contacts_payload[f"{role}{key}"] = value

        extra = {
            "DomainName": full_domain,
            "SLD": sld,
            "TLD": tld,
            "Years": years,
            **contacts_payload,
        }

        root = self._make_request("namecheap.domains.create", extra)
        if root is None or not self._is_success(root):
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap purchase request failed",
            }

        return {
            "success": True,
            "domain": domain,
            "message": "Domain purchased via Namecheap",
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        root = self._make_request(
            "namecheap.users.getPricing",
            {"ProductType": "DOMAIN", "ProductCategory": "register", "ActionName": "register"},
        )
        if root is None or not self._is_success(root):
            return {}

        tld_lower = tld.lower().lstrip(".")
        for node in root.iter():
            if not node.tag.endswith("ProductPrice"):
                continue
            if str(node.attrib.get("ProductName", "")).lower().lstrip(".") != tld_lower:
                continue

            registration = (
                self._to_float(node.attrib.get("Price"))
                or self._to_float(node.attrib.get("YourPrice"))
                or self._to_float(node.attrib.get("RegularPrice"))
            )
            renewal = self._to_float(node.attrib.get("AdditionalCost"))

            return {
                "tld": tld_lower,
                "registration": registration,
                "renewal": renewal,
                "transfer": None,
                "currency": "USD",
            }

        return {}


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, monthly_budget: float = 50.0):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict[str, Any]] = []
        self.active_domain: Optional[str] = None
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None

        if api_client:
            self.add_api_client("primary", api_client, set_active=True)

    @staticmethod
    def _normalize_price(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = value.strip().replace("$", "").replace("€", "").replace(",", "")
            if not normalized:
                return None
            try:
                return float(normalized)
            except ValueError:
                return None
        return None

    @staticmethod
    def _serialize_datetime(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def _parse_datetime(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient, set_active: bool = False):
        """Register an API client for a provider."""
        normalized = provider_name.strip().lower()
        if not normalized:
            raise ValueError("provider_name is required")
        self.api_clients[normalized] = api_client
        self.api_client = api_client
        if set_active or not self.active_provider:
            self.active_provider = normalized

    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.add_api_client("primary", api_client, set_active=True)

    def set_active_provider(self, provider_name: str) -> bool:
        """Set active provider if registered."""
        normalized = provider_name.strip().lower()
        if normalized in self.api_clients:
            self.active_provider = normalized
            self.api_client = self.api_clients[normalized]
            return True
        return False

    def get_provider_names(self) -> List[str]:
        """List configured provider names."""
        return sorted(self.api_clients.keys())

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        provider: str = "porkbun",
        **provider_options: Any,
    ) -> Dict[str, Any]:
        """
        Configure and register a provider client.

        Supported providers:
        - porkbun: api_key + secret_key
        - namecheap: api_key + username + client_ip (+ optional sandbox/contact_profile)
        """
        provider_normalized = provider.strip().lower()
        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        if provider_normalized == "porkbun":
            if not secret_key:
                raise ValueError("secret_key is required for Porkbun configuration")
            client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
            self.add_api_client("porkbun", client, set_active=True)
        elif provider_normalized == "namecheap":
            username = provider_options.get("username")
            client_ip = provider_options.get("client_ip")
            if not username or not client_ip:
                raise ValueError("username and client_ip are required for Namecheap configuration")
            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                sandbox=bool(provider_options.get("sandbox", False)),
                contact_profile=provider_options.get("contact_profile"),
            )
            self.add_api_client("namecheap", client, set_active=True)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return current domain-rotation configuration metadata."""
        return {
            "active_provider": self.active_provider,
            "providers": self.get_provider_names(),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "configured": bool(self.api_clients),
        }

    def _iter_clients(self, provider_preference: Optional[str] = None) -> List[Tuple[str, DomainAPIClient]]:
        if provider_preference:
            preferred = provider_preference.strip().lower()
            client = self.api_clients.get(preferred)
            if client:
                return [(preferred, client)]
            return []

        ordered_names: List[str] = []
        if self.active_provider and self.active_provider in self.api_clients:
            ordered_names.append(self.active_provider)

        for name in self.api_clients:
            if name not in ordered_names:
                ordered_names.append(name)

        if not ordered_names and self.api_client:
            # Backward compatibility for callers that only used set_api_client.
            return [("primary", self.api_client)]

        return [(name, self.api_clients[name]) for name in ordered_names]

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"
    
    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        provider_preference: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        clients = self._iter_clients(provider_preference)
        if not clients:
            logger.error("No API client configured")
            return None

        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]

        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for provider_name, client in clients:
                result = client.search_domain(domain)
                if not result.get("available"):
                    continue

                price = self._normalize_price(result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
                    price = self._normalize_price(pricing.get("registration")) if pricing else None

                if price is None:
                    logger.debug(
                        "Provider %s returned no price for %s; skipping", provider_name, domain
                    )
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider_name,
                    }

        return None

    def purchase_domain_if_budget_allows(
        self, domain: str, price: float, provider: Optional[str] = None
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        clients = self._iter_clients(provider_preference=provider)
        if not clients:
            logger.error("No API client configured")
            return False

        provider_name, client = clients[0]
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                price,
                self.monthly_budget,
            )
            return False

        # Attempt purchase
        result = client.purchase_domain(domain, years=1)

        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365),
                "provider": provider_name,
            })

            # Set as active if no active domain
            self.active_domain = domain
            self.active_provider = provider_name

            logger.info("Successfully purchased domain: %s for $%s via %s", domain, price, provider_name)
            return True
        logger.error("Failed to purchase domain: %s", result.get("message"))
        return False

    def rotate_domain(
        self,
        provider_preference: Optional[str] = None,
        max_price: float = 5.0,
        max_attempts: int = 10,
    ) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=max_attempts,
            provider_preference=provider_preference,
        )

        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None

        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider=domain_info.get("provider"),
        )

        if success:
            self.active_domain = domain_info["domain"]
            if domain_info.get("provider"):
                self.active_provider = domain_info["provider"]
            return self.active_domain

        return None

    def rotate_to_new_domain(
        self,
        provider_preference: Optional[str] = None,
        max_price: float = 5.0,
        max_attempts: int = 10,
    ) -> Dict[str, Any]:
        """
        Rotate to a new domain and return structured result.
        """
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=max_attempts,
            provider_preference=provider_preference,
        )
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain",
                "provider": provider_preference or self.active_provider,
            }

        success = self.purchase_domain_if_budget_allows(
            domain=domain_info["domain"],
            price=domain_info["price"],
            provider=domain_info.get("provider"),
        )
        if not success:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded",
                "domain": domain_info["domain"],
                "cost": domain_info["price"],
                "provider": domain_info.get("provider"),
            }

        return {
            "success": True,
            "domain": domain_info["domain"],
            "cost": domain_info["price"],
            "provider": domain_info.get("provider"),
        }

    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain

    def get_owned_domains(self) -> List[Dict[str, Any]]:
        """Get list of owned domains"""
        return self.owned_domains

    def get_budget_status(self) -> Dict[str, Any]:
        """Get budget information"""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }

    def export_state(self) -> Dict[str, Any]:
        """Export state as JSON-serializable data."""
        exported_domains: List[Dict[str, Any]] = []
        for domain in self.owned_domains:
            exported_domain: Dict[str, Any] = {}
            for key, value in domain.items():
                exported_domain[key] = self._serialize_datetime(value)
            exported_domains.append(exported_domain)

        return {
            "current_spending": self.current_spending,
            "owned_domains": exported_domains,
            "active_domain": self.active_domain,
            "active_provider": self.active_provider,
            "monthly_budget": self.monthly_budget,
        }

    def import_state(self, state: Dict[str, Any]):
        """Import manager state from JSON-friendly payload."""
        self.current_spending = float(state.get("current_spending", self.current_spending))
        self.active_domain = state.get("active_domain", self.active_domain)
        self.active_provider = state.get("active_provider", self.active_provider)
        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))

        loaded_domains: List[Dict[str, Any]] = []
        for item in state.get("owned_domains", []):
            loaded_item: Dict[str, Any] = {}
            for key, value in item.items():
                if key in {"purchased_at", "expires_at"}:
                    loaded_item[key] = self._parse_datetime(value)
                else:
                    loaded_item[key] = value
            loaded_domains.append(loaded_item)
        self.owned_domains = loaded_domains


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
