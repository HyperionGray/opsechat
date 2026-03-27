"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
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
        raise NotImplementedError
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError


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


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0):
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        self.provider_configs: Dict[str, Dict[str, Optional[str]]] = {}
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        # Backward compatibility: existing callers may pass one client directly.
        if api_client is not None:
            self.set_api_client(api_client, provider_name="default")

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient,
                       activate: bool = False):
        """Register an API client for a provider."""
        self.api_clients[provider_name] = api_client
        if activate or self.active_provider is None:
            self.active_provider = provider_name

    def set_api_client(self, api_client: DomainAPIClient,
                       provider_name: str = "default"):
        """Set (or replace) a provider API client and activate it."""
        self.add_api_client(provider_name, api_client, activate=True)

    def set_active_provider(self, provider_name: str) -> bool:
        """Switch active provider by name."""
        if provider_name not in self.api_clients:
            logger.error(f"Provider '{provider_name}' is not configured")
            return False
        self.active_provider = provider_name
        return True

    def _get_active_client(self) -> Optional[DomainAPIClient]:
        """Get currently active API client."""
        if not self.active_provider:
            return None
        return self.api_clients.get(self.active_provider)

    @staticmethod
    def _mask_secret(value: Optional[str]) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * (len(value) - 4)}{value[-4:]}"

    @staticmethod
    def _normalize_price(price: Any) -> Optional[float]:
        """Normalize registrar price formats to float."""
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            cleaned = price.strip().replace("$", "").replace("€", "").replace(",", "")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def configure(self, api_key: str, secret_key: Optional[str] = None,
                  api_secret: Optional[str] = None, monthly_budget: float = 50.0,
                  provider: str = "porkbun") -> bool:
        """
        Configure domain provider credentials and budget.
        Returns True when provider is configured successfully.
        """
        provider_name = (provider or "porkbun").strip().lower()
        resolved_secret = (api_secret or secret_key or "").strip()
        resolved_key = (api_key or "").strip()

        if not resolved_key:
            raise ValueError("API key is required")
        if provider_name == "porkbun" and not resolved_secret:
            raise ValueError("Porkbun secret key is required")

        if provider_name == "porkbun":
            client = PorkbunAPIClient(resolved_key, resolved_secret)
        else:
            raise ValueError(f"Unsupported provider '{provider_name}'")

        self.add_api_client(provider_name, client, activate=True)
        self.monthly_budget = float(monthly_budget)
        self.provider_configs[provider_name] = {
            "api_key": resolved_key,
            "api_secret": resolved_secret
        }
        return True

    def get_config(self) -> Dict:
        """Return sanitized configuration metadata for UI/API use."""
        providers = {}
        for provider_name, creds in self.provider_configs.items():
            providers[provider_name] = {
                "configured": provider_name in self.api_clients,
                "api_key": self._mask_secret(creds.get("api_key")),
                "has_secret": bool(creds.get("api_secret"))
            }

        return {
            "active_provider": self.active_provider,
            "provider_count": len(self.api_clients),
            "providers": providers,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains)
        }
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"
    
    def find_cheap_available_domain(self, max_price: float = 5.0,
                                   max_attempts: int = 10,
                                   tlds: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        api_client = self._get_active_client()
        if not api_client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = api_client.search_domain(domain)
            
            if result.get("available"):
                price = self._normalize_price(result.get("price", 999))
                if price is None:
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        api_client = self._get_active_client()
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
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": self.active_provider,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            return self.active_domain
        
        return None

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict:
        """
        Rotate to a new domain and return API-friendly response details.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            return {
                "success": False,
                "error": "No cheap available domain found",
                "provider": self.active_provider
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"]
        )
        if not success:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded",
                "domain": domain_info["domain"],
                "price": domain_info["price"],
                "provider": self.active_provider
            }

        return {
            "success": True,
            "domain": domain_info["domain"],
            "price": domain_info["price"],
            "provider": self.active_provider
        }

    def search_cheap_domains(self, tlds: Optional[List[str]] = None,
                             max_price: float = 5.0,
                             limit: int = 5,
                             max_attempts_per_result: int = 3) -> List[Dict]:
        """
        Search for multiple cheap available domains without purchasing them.
        """
        tlds = tlds or ["xyz", "club", "online", "site", "website"]
        results: List[Dict] = []
        seen_domains = set()

        attempts = max(limit * max_attempts_per_result, 1)
        for _ in range(attempts):
            info = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=tlds
            )
            if not info:
                continue
            if info["domain"] in seen_domains:
                continue
            seen_domains.add(info["domain"])
            results.append(info)
            if len(results) >= limit:
                break

        return results
    
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
            "domains_owned": len(self.owned_domains)
        }

    @staticmethod
    def _serialize_dt(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def _deserialize_dt(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value
        return value

    def serialize_state(self) -> Dict:
        """Serialize manager runtime state for JSON storage."""
        serialized_domains = []
        for item in self.owned_domains:
            serialized = dict(item)
            serialized["purchased_at"] = self._serialize_dt(item.get("purchased_at"))
            serialized["expires_at"] = self._serialize_dt(item.get("expires_at"))
            serialized_domains.append(serialized)

        return {
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "active_provider": self.active_provider,
            "monthly_budget": self.monthly_budget
        }

    def load_state(self, state: Dict):
        """Load manager runtime state from serialized JSON structure."""
        self.current_spending = float(state.get("current_spending", 0.0))
        self.active_domain = state.get("active_domain")
        self.active_provider = state.get("active_provider", self.active_provider)
        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))

        loaded_domains = []
        for item in state.get("owned_domains", []):
            domain_item = dict(item)
            domain_item["purchased_at"] = self._deserialize_dt(item.get("purchased_at"))
            domain_item["expires_at"] = self._deserialize_dt(item.get("expires_at"))
            loaded_domains.append(domain_item)
        self.owned_domains = loaded_domains


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
