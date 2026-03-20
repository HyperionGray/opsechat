"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
from __future__ import annotations

import requests
import random
import string
import logging
from abc import ABC, abstractmethod
from xml.etree import ElementTree
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    @abstractmethod
    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search if domain is available"""
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase domain"""
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing for TLD"""


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management
    https://porkbun.com/api/json/v3/documentation
    """
    
    BASE_URL = "https://porkbun.com/api/json/v3"
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()
    
    def _make_request(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
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
    
    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available"""
        result = self._make_request("domain/check", {"domain": domain})
        
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and result.get("isAvailable", False),
            "price": result.get("price"),
            "currency": result.get("currency", "USD")
        }
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
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
    
    def get_pricing(self, tld: str = "com") -> Dict:
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
    """
    Namecheap API client for domain management.
    API Docs: https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str,
        api_user: Optional[str] = None,
        default_contact: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key, api_secret=None)
        self.username = username
        self.api_user = api_user or username
        self.client_ip = client_ip
        self.default_contact = default_contact or {}
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if data:
            params.update(data)

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            root = ElementTree.fromstring(response.text)
            status = root.attrib.get("Status", "")
            errors = [node.text for node in root.findall(".//Errors/Error") if node.text]

            return {
                "status": status,
                "errors": errors,
                "xml_root": root,
            }
        except Exception as exc:
            logger.error(f"Namecheap API request failed: {exc}")
            return {"status": "ERROR", "errors": [str(exc)]}

    def search_domain(self, domain: str) -> Dict[str, Any]:
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if result.get("status") != "OK":
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "; ".join(result.get("errors", [])) or "Namecheap lookup failed",
            }

        check_result = result["xml_root"].find(".//DomainCheckResult")
        if check_result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "No DomainCheckResult returned",
            }

        available = check_result.attrib.get("Available", "false").lower() == "true"
        # Namecheap check endpoint does not always include price.
        return {
            "domain": domain,
            "available": available,
            "price": None,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        if not self.default_contact:
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap purchase requires contact defaults in client configuration",
            }

        payload: Dict[str, Any] = {
            "DomainName": domain,
            "Years": years,
        }
        payload.update(self.default_contact)

        result = self._make_request("namecheap.domains.create", payload)
        if result.get("status") != "OK":
            return {
                "success": False,
                "domain": domain,
                "message": "; ".join(result.get("errors", [])) or "Namecheap purchase failed",
            }

        create_result = result["xml_root"].find(".//DomainCreateResult")
        registered = (
            create_result is not None and
            create_result.attrib.get("Registered", "false").lower() == "true"
        )
        return {
            "success": registered,
            "domain": domain,
            "message": "Purchase completed" if registered else "Domain registration not confirmed",
            "order_id": create_result.attrib.get("OrderID") if create_result is not None else None,
        }

    def get_pricing(self, tld: str) -> Dict[str, Any]:
        product_name = f"com,{tld}".split(",")[-1]  # guard against malformed caller input
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "DOMAINS",
                "ActionName": "REGISTER",
                "ProductName": product_name,
            },
        )
        if result.get("status") != "OK":
            return {}

        price_node = result["xml_root"].find(".//Price[@Duration='1']")
        if price_node is None:
            return {}

        return {
            "tld": tld,
            "registration": price_node.attrib.get("YourPrice"),
            "renewal": price_node.attrib.get("YourAdditonalCost"),
            "transfer": price_node.attrib.get("YourPrice"),
            "currency": "USD",
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.provider_priority: List[str] = []
        if api_client:
            self.api_clients["default"] = api_client
            self.provider_priority.append("default")
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.active_provider: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient, provider_name: str = "default"):
        """Set the domain API client"""
        self.api_client = api_client
        self.api_clients[provider_name] = api_client
        if provider_name in self.provider_priority:
            self.provider_priority.remove(provider_name)
        self.provider_priority.insert(0, provider_name)

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient, set_primary: bool = False):
        """Register an additional provider client."""
        self.api_clients[provider_name] = api_client
        if provider_name not in self.provider_priority:
            self.provider_priority.append(provider_name)

        if set_primary:
            self.provider_priority.remove(provider_name)
            self.provider_priority.insert(0, provider_name)

        if not self.api_client:
            self.api_client = api_client

    def set_provider_priority(self, providers: List[str]):
        """Set provider lookup order for search/purchase operations."""
        known = [provider for provider in providers if provider in self.api_clients]
        if known:
            self.provider_priority = known

    def _iter_clients(self, providers: Optional[List[str]] = None) -> List[Tuple[str, DomainAPIClient]]:
        if not self.api_clients and self.api_client:
            self.api_clients["default"] = self.api_client
            if "default" not in self.provider_priority:
                self.provider_priority.append("default")

        if providers:
            names = [name for name in providers if name in self.api_clients]
        elif self.provider_priority:
            names = [name for name in self.provider_priority if name in self.api_clients]
        else:
            names = list(self.api_clients.keys())

        return [(name, self.api_clients[name]) for name in names]

    @staticmethod
    def _normalize_price(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace("€", "").strip()
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None
    
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
        providers: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        clients = self._iter_clients(providers=providers)
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

                # Some providers (e.g., Namecheap check endpoint) do not return price.
                raw_price = result.get("price")
                price = self._normalize_price(raw_price)
                if price is None:
                    pricing = client.get_pricing(tld)
                    price = self._normalize_price(pricing.get("registration"))

                if price is None:
                    logger.warning(
                        f"Could not determine price for {domain} via {provider_name}, skipping"
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
        clients = self._iter_clients(providers=[provider] if provider else None)
        if not clients:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        provider_name, client = clients[0]
        result = client.purchase_domain(domain, years=1)
        if not result.get("success"):
            logger.error(f"Failed to purchase domain via {provider_name}: {result.get('message')}")
            return False

        now = datetime.now()
        self.current_spending += price
        self.owned_domains.append({
            "domain": domain,
            "price": price,
            "provider": provider_name,
            "purchased_at": now,
            "expires_at": now + timedelta(days=365)
        })

        # Set as active if no active domain
        if not self.active_domain:
            self.active_domain = domain
            self.active_provider = provider_name

        logger.info(
            f"Successfully purchased domain: {domain} for ${price} via {provider_name}"
        )
        return True
    
    def rotate_domain(self, providers: Optional[List[str]] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(providers=providers)
        
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
            self.active_provider = domain_info.get("provider")
            return self.active_domain
        
        return None
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return self.owned_domains
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "providers": list(self.api_clients.keys()),
            "active_provider": self.active_provider,
        }

    def configure(
        self,
        api_key: str,
        secret_key: str = "",
        monthly_budget: float = 10.0,
        provider: str = "porkbun",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Backwards-compatible helper used by email route handlers.
        """
        provider_name = provider.lower().strip()
        self.monthly_budget = monthly_budget

        if provider_name == "namecheap":
            username = kwargs.get("username", "").strip()
            client_ip = kwargs.get("client_ip", "").strip()
            api_user = kwargs.get("api_user", "").strip() or None
            if not username or not client_ip:
                raise ValueError("Namecheap requires username and client_ip")

            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                api_user=api_user,
                default_contact=kwargs.get("default_contact"),
            )
        else:
            if not secret_key:
                raise ValueError("Porkbun requires secret_key")
            provider_name = "porkbun"
            client = PorkbunAPIClient(api_key, secret_key)

        self.set_api_client(client, provider_name=provider_name)
        self.active_provider = provider_name
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Expose a safe config summary (no secrets)."""
        return {
            "providers": list(self.api_clients.keys()),
            "primary_provider": self.provider_priority[0] if self.provider_priority else None,
            "active_provider": self.active_provider,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "domains_owned": len(self.owned_domains),
        }

    @staticmethod
    def _serialize_domain_record(record: Dict[str, Any]) -> Dict[str, Any]:
        serialized = dict(record)
        for key in ("purchased_at", "expires_at"):
            value = serialized.get(key)
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
        return serialized

    @staticmethod
    def _deserialize_domain_record(record: Dict[str, Any]) -> Dict[str, Any]:
        parsed = dict(record)
        for key in ("purchased_at", "expires_at"):
            value = parsed.get(key)
            if isinstance(value, str):
                try:
                    parsed[key] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep original value so caller can still inspect corrupted records.
                    logger.warning(f"Could not parse datetime field '{key}': {value}")
        return parsed

    def export_state(self) -> Dict[str, Any]:
        """Export JSON-safe manager state for persistence."""
        return {
            "current_spending": self.current_spending,
            "owned_domains": [
                self._serialize_domain_record(record)
                for record in self.owned_domains
            ],
            "active_domain": self.active_domain,
            "active_provider": self.active_provider,
        }

    def import_state(self, state: Dict[str, Any]):
        """Import manager state from persisted JSON content."""
        self.current_spending = float(state.get("current_spending", 0.0) or 0.0)
        owned = state.get("owned_domains", [])
        self.owned_domains = [
            self._deserialize_domain_record(record)
            for record in owned
            if isinstance(record, dict)
        ]
        self.active_domain = state.get("active_domain")
        self.active_provider = state.get("active_provider")


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
