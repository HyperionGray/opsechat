"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        raise NotImplementedError("search_domain must be implemented by subclasses")
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("purchase_domain must be implemented by subclasses")
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError("get_pricing must be implemented by subclasses")


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
    Namecheap API client for domain management
    https://www.namecheap.com/support/api/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        use_sandbox: bool = False,
    ):
        super().__init__(api_key)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.base_url = self.SANDBOX_URL if use_sandbox else self.BASE_URL

    @staticmethod
    def _extract_errors(root: ET.Element) -> List[str]:
        return [node.text.strip() for node in root.findall(".//{*}Error") if node.text]

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if data:
            params.update(data)

        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            status_ok = str(root.attrib.get("Status", "")).upper() == "OK"
            errors = self._extract_errors(root)
            if not status_ok and not errors:
                errors = ["Namecheap API returned non-OK status"]
            return {"ok": status_ok and not errors, "root": root, "errors": errors}
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return {"ok": False, "root": None, "errors": [str(e)]}

    def search_domain(self, domain: str) -> Dict:
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        root = result.get("root")
        errors = result.get("errors", [])
        if root is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": "namecheap",
                "error": "; ".join(errors) if errors else "Unknown error",
            }

        check_result = root.find(".//{*}DomainCheckResult")
        available = (
            check_result is not None
            and str(check_result.attrib.get("Available", "")).lower() == "true"
        )
        return {
            "domain": domain,
            "available": available,
            "price": None,  # Namecheap check endpoint does not include price
            "currency": "USD",
            "provider": "namecheap",
            "error": "; ".join(errors) if errors else "",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        result = self._make_request(
            "namecheap.domains.create",
            {
                "DomainName": domain,
                "Years": years,
                "UseGlobalDefault": "true",
            },
        )
        root = result.get("root")
        errors = result.get("errors", [])
        success = bool(result.get("ok"))
        order_id = None

        if root is not None:
            create_result = root.find(".//{*}DomainCreateResult")
            if create_result is not None:
                order_id = create_result.attrib.get("OrderID")

        return {
            "success": success,
            "domain": domain,
            "message": "; ".join(errors) if errors else "",
            "order_id": order_id,
        }

    def get_pricing(self, tld: str) -> Dict:
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "DOMAINS",
                "ActionName": "REGISTER",
                "ProductName": tld.lower(),
            },
        )
        root = result.get("root")
        if root is None or not result.get("ok"):
            return {}

        # Namecheap pricing schema can vary by account/endpoint version;
        # return the first available price as registration estimate.
        price_node = root.find(".//{*}Price")
        if price_node is None:
            price_node = root.find(".//{*}ProductPrice")

        if price_node is None:
            return {}

        registration = (
            price_node.attrib.get("Price")
            or price_node.attrib.get("YourPrice")
            or price_node.attrib.get("RegularPrice")
        )
        return {
            "tld": tld,
            "registration": registration,
            "renewal": None,
            "transfer": None,
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
        self.default_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client:
            self.add_api_client("default", api_client, make_default=True)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.add_api_client("default", api_client, make_default=True)

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient, make_default: bool = False):
        """Register an API client provider"""
        normalized = provider_name.strip().lower()
        if not normalized:
            raise ValueError("provider_name cannot be empty")

        self.api_clients[normalized] = api_client
        if make_default or not self.default_provider:
            self.default_provider = normalized
        if normalized == "default":
            self.api_client = api_client

    def get_api_client(self, provider_name: Optional[str] = None) -> Optional[DomainAPIClient]:
        """Return a provider-specific client or the configured default"""
        if not self.api_clients:
            return self.api_client

        if provider_name:
            return self.api_clients.get(provider_name.strip().lower())

        if self.default_provider and self.default_provider in self.api_clients:
            return self.api_clients[self.default_provider]

        # Fall back to first registered provider.
        first_provider = next(iter(self.api_clients))
        return self.api_clients[first_provider]

    def list_providers(self) -> List[str]:
        """List configured provider names"""
        return sorted(self.api_clients.keys())

    @staticmethod
    def _normalize_price(raw_price: Any) -> Optional[float]:
        """Convert mixed price values into a float"""
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if isinstance(raw_price, str):
            cleaned = (
                raw_price.replace("$", "")
                .replace("€", "")
                .replace(",", "")
                .strip()
            )
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_datetime(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value
        return value

    @staticmethod
    def _serialize_datetime(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def serialize_state(self) -> Dict[str, Any]:
        """Serialize manager state to JSON-safe dictionary"""
        serialized_domains = []
        for domain in self.owned_domains:
            item = dict(domain)
            item["purchased_at"] = self._serialize_datetime(item.get("purchased_at"))
            item["expires_at"] = self._serialize_datetime(item.get("expires_at"))
            serialized_domains.append(item)

        return {
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "default_provider": self.default_provider,
        }

    def deserialize_state(self, state: Dict[str, Any]) -> None:
        """Load manager state from dictionary"""
        self.current_spending = float(state.get("current_spending", self.current_spending))
        self.active_domain = state.get("active_domain", self.active_domain)

        default_provider = state.get("default_provider")
        if default_provider and default_provider in self.api_clients:
            self.default_provider = default_provider

        owned_domains = []
        for domain in state.get("owned_domains", []):
            item = dict(domain)
            item["purchased_at"] = self._parse_datetime(item.get("purchased_at"))
            item["expires_at"] = self._parse_datetime(item.get("expires_at"))
            owned_domains.append(item)
        self.owned_domains = owned_domains
    
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
        provider: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_clients and not self.api_client:
            logger.error("No API client configured")
            return None

        if self.api_client and "default" not in self.api_clients:
            self.api_clients["default"] = self.api_client
            if not self.default_provider:
                self.default_provider = "default"

        provider_names: List[str]
        if provider:
            normalized_provider = provider.strip().lower()
            if normalized_provider not in self.api_clients:
                logger.error(f"Provider '{provider}' is not configured")
                return None
            provider_names = [normalized_provider]
        else:
            provider_names = list(self.api_clients.keys())
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for provider_name in provider_names:
                client = self.api_clients[provider_name]
                result = client.search_domain(domain)

                if not result.get("available"):
                    continue

                price = self._normalize_price(result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
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
    
    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider: Optional[str] = None,
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        api_client = self.get_api_client(provider)
        if not api_client:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            provider_name = (
                provider.strip().lower()
                if provider
                else self.default_provider
            )
            now = datetime.now()
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": provider_name,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365),
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self, provider: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(provider=provider)
        
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
            "default_provider": self.default_provider,
            "providers": self.list_providers(),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
