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
        # Backward-compatible direct client reference (kept in sync with active provider)
        self.api_client: Optional[DomainAPIClient] = None
        # Multi-provider support for registrar fallback/expansion
        self.providers: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False

        if api_client is not None:
            self.set_api_client(api_client)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set a default API client (backward-compatible helper)."""
        self.add_api_client("default", api_client, make_active=True)

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient,
                       make_active: bool = False):
        """Register a named API client provider."""
        if not provider_name:
            raise ValueError("provider_name is required")
        provider_key = provider_name.strip().lower()
        self.providers[provider_key] = api_client
        if self.active_provider is None or make_active:
            self.active_provider = provider_key
        self.api_client = self.providers.get(self.active_provider)

    def set_active_provider(self, provider_name: str) -> bool:
        """Set active provider by name."""
        provider_key = (provider_name or "").strip().lower()
        if provider_key not in self.providers:
            return False
        self.active_provider = provider_key
        self.api_client = self.providers[provider_key]
        return True

    def list_providers(self) -> List[str]:
        """List currently configured registrar providers."""
        return sorted(self.providers.keys())

    def get_config(self) -> Dict[str, Any]:
        """Return non-secret runtime configuration for UI/status pages."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "providers": self.list_providers(),
            "active_provider": self.active_provider
        }

    def configure(self, api_key: str, secret_key: str,
                  monthly_budget: float = 50.0,
                  provider_name: str = "porkbun") -> Dict[str, Any]:
        """
        Configure and activate a registrar client.

        Currently supports provider_name='porkbun'. Additional providers can be
        added by extending DomainAPIClient and registering via add_api_client().
        """
        provider_key = (provider_name or "").strip().lower()
        if not api_key or not secret_key:
            raise ValueError("api_key and secret_key are required")

        if provider_key == "porkbun":
            client = PorkbunAPIClient(api_key, secret_key)
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

        self.add_api_client(provider_key, client, make_active=True)
        self.monthly_budget = float(monthly_budget)
        return self.get_config()

    def set_test_mode(self, enabled: bool):
        """Enable/disable dry-run mode for safe testing."""
        self.test_mode = bool(enabled)

    def _get_current_client(self) -> Optional[DomainAPIClient]:
        """Get active API client (supports legacy self.api_client fallback)."""
        if self.active_provider and self.active_provider in self.providers:
            return self.providers[self.active_provider]
        return self.api_client

    def _parse_datetime(self, value: Any, default: Optional[datetime] = None) -> datetime:
        """Parse datetime values from runtime objects or persisted JSON strings."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return default or datetime.now()

    def _normalize_owned_domain_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize persisted domain records into runtime-safe structure."""
        now = datetime.now()
        normalized = dict(record)
        normalized["domain"] = str(record.get("domain", ""))
        raw_price = record.get("price", 0.0)
        if isinstance(raw_price, str):
            raw_price = raw_price.replace("$", "").replace("€", "").strip()
        normalized["price"] = float(raw_price)
        normalized["purchased_at"] = self._parse_datetime(record.get("purchased_at"), default=now)
        normalized["expires_at"] = self._parse_datetime(
            record.get("expires_at"),
            default=normalized["purchased_at"] + timedelta(days=365)
        )
        return normalized

    def _serialize_owned_domain_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize runtime domain record into JSON-safe dict."""
        normalized = self._normalize_owned_domain_record(record)
        return {
            "domain": normalized["domain"],
            "price": normalized["price"],
            "purchased_at": normalized["purchased_at"].isoformat(),
            "expires_at": normalized["expires_at"].isoformat()
        }

    def load_state(self, state: Dict[str, Any]):
        """Load persisted manager state from a JSON-compatible dict."""
        if not isinstance(state, dict):
            return
        self.current_spending = float(state.get("current_spending", 0.0))
        self.active_domain = state.get("active_domain")
        owned = state.get("owned_domains", [])
        if isinstance(owned, list):
            self.owned_domains = [self._normalize_owned_domain_record(item)
                                  for item in owned if isinstance(item, dict)]

    def export_state(self) -> Dict[str, Any]:
        """Export manager state in JSON-safe format."""
        return {
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "owned_domains": [
                self._serialize_owned_domain_record(record)
                for record in self.owned_domains
            ],
            "monthly_budget": self.monthly_budget
        }

    def search_cheap_domains(self, tlds: Optional[List[str]] = None,
                             max_price: float = 5.0, limit: int = 5,
                             max_attempts: int = 20) -> List[Dict[str, Any]]:
        """
        Search for available low-cost domains.

        Returns at most `limit` unique domains that are available and <= max_price.
        """
        client = self._get_current_client()
        if not client:
            logger.error("No API client configured")
            return []

        tld_candidates = tlds or ["xyz", "club", "online", "site", "website"]
        found: List[Dict[str, Any]] = []
        seen = set()

        for _ in range(max_attempts):
            if len(found) >= limit:
                break
            tld = random.choice(tld_candidates)
            candidate = self.generate_random_domain(tld)
            if candidate in seen:
                continue
            seen.add(candidate)

            result = client.search_domain(candidate)
            if not result.get("available"):
                continue

            try:
                raw_price = result.get("price", 999)
                if isinstance(raw_price, str):
                    raw_price = float(raw_price.replace("$", "").replace("€", ""))
                price = float(raw_price)
            except (TypeError, ValueError):
                continue

            if price <= max_price:
                found.append({"domain": candidate, "price": price, "tld": tld})

        return found
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"
    
    def find_cheap_available_domain(self, max_price: float = 5.0, 
                                   max_attempts: int = 10) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        api_client = self._get_current_client()
        if not api_client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = api_client.search_domain(domain)
            
            if result.get("available"):
                price = result.get("price", 999)
                if isinstance(price, str):
                    price = float(price.replace("$", "").replace("€", ""))
                price = float(price)
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
        api_client = self._get_current_client()
        if not api_client:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        if self.test_mode:
            result = {"success": True, "domain": domain, "message": "test mode"}
        else:
            result = api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            now = datetime.now()
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365)
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

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Rotate to a new domain and return structured status.
        This wrapper is friendlier for API/CLI callers.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            return {"success": False, "error": "No available domain found"}

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], domain_info["price"]
        )
        if not success:
            return {"success": False, "error": "Purchase failed or budget exceeded"}

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "cost": domain_info["price"],
            "provider": self.active_provider
        }
    
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


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
