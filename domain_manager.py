"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
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
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        ...
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        ...
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        ...


class MultiProviderDomainClient(DomainAPIClient):
    """
    Fallback client that fans out across multiple registrars.
    """
    
    def __init__(self, providers: List[DomainAPIClient], provider_names: Optional[List[str]] = None):
        super().__init__(api_key="", api_secret=None)
        
        if not providers:
            raise ValueError("At least one provider client is required")
        
        if provider_names and len(provider_names) != len(providers):
            raise ValueError("provider_names length must match providers length")
        
        self.providers: List[Dict[str, Any]] = []
        for idx, provider in enumerate(providers):
            provider_name = provider_names[idx] if provider_names else provider.__class__.__name__.lower()
            self.providers.append({"name": provider_name, "client": provider})
        
        self._preferred_purchase_provider: Dict[str, str] = {}
    
    @staticmethod
    def _parse_price(price: object) -> float:
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            try:
                return float(price.replace("$", "").replace("€", "").strip())
            except ValueError:
                return float("inf")
        return float("inf")
    
    def _provider_order(self, preferred_provider: Optional[str] = None) -> List[Dict[str, Any]]:
        if not preferred_provider:
            return self.providers
        
        preferred = [p for p in self.providers if p["name"] == preferred_provider]
        remaining = [p for p in self.providers if p["name"] != preferred_provider]
        return preferred + remaining
    
    def search_domain(self, domain: str) -> Dict:
        """Search all providers and return first available result."""
        attempts: List[Dict] = []
        
        for provider in self.providers:
            name = provider["name"]
            client = provider["client"]
            result = client.search_domain(domain) or {}
            attempts.append({"provider": name, "result": result})
            
            if result.get("available"):
                self._preferred_purchase_provider[domain] = name
                available_result = dict(result)
                available_result.setdefault("domain", domain)
                available_result["provider"] = name
                available_result["provider_attempts"] = attempts
                return available_result
        
        # No provider reported availability; keep first response shape for compatibility.
        if attempts:
            first_result = dict(attempts[0]["result"] or {})
            first_result.setdefault("domain", domain)
            first_result["available"] = bool(first_result.get("available", False))
            first_result["provider"] = attempts[0]["provider"]
            first_result["provider_attempts"] = attempts
            return first_result
        
        return {"domain": domain, "available": False, "provider_attempts": attempts}
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase from the provider that found availability first, then fallback."""
        preferred_provider = self._preferred_purchase_provider.get(domain)
        provider_order = self._provider_order(preferred_provider)
        provider_errors: List[Dict[str, str]] = []
        
        for provider in provider_order:
            name = provider["name"]
            client = provider["client"]
            result = client.purchase_domain(domain, years=years) or {}
            success = bool(result.get("success"))
            
            purchase_result = dict(result)
            purchase_result.setdefault("domain", domain)
            purchase_result["provider"] = name
            
            if success:
                self._preferred_purchase_provider[domain] = name
                return purchase_result
            
            provider_errors.append({
                "provider": name,
                "message": str(result.get("message", "purchase failed"))
            })
        
        return {
            "success": False,
            "domain": domain,
            "message": "All providers failed to purchase domain",
            "provider_errors": provider_errors
        }
    
    def get_pricing(self, tld: str) -> Dict:
        """Return the cheapest registration pricing across providers."""
        pricing_options: List[Dict] = []
        
        for provider in self.providers:
            name = provider["name"]
            client = provider["client"]
            result = client.get_pricing(tld) or {}
            if result:
                option = dict(result)
                option["provider"] = name
                pricing_options.append(option)
        
        if not pricing_options:
            return {}
        
        best_option = min(
            pricing_options,
            key=lambda option: self._parse_price(option.get("registration"))
        )
        best_pricing = dict(best_option)
        best_pricing["provider_options"] = pricing_options
        return best_pricing


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
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
    
    @staticmethod
    def _parse_price(price: object) -> Optional[float]:
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            try:
                return float(price.replace("$", "").replace("€", "").strip())
            except ValueError:
                return None
        return None
    
    @staticmethod
    def _coerce_datetime(value: object) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
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
    
    def find_cheap_available_domain(self, max_price: float = 5.0, 
                                   max_attempts: int = 10) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                parsed_price = self._parse_price(result.get("price", 999))
                if parsed_price is None:
                    continue
                
                if parsed_price <= max_price:
                    return {
                        "domain": domain,
                        "price": parsed_price,
                        "tld": tld,
                        "provider": result.get("provider")
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float, provider: Optional[str] = None) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            purchased_provider = result.get("provider", provider)
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365),
                "provider": purchased_provider
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
            domain_info["price"],
            domain_info.get("provider")
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
    
    def prune_expired_domains(self, reference_time: Optional[datetime] = None) -> int:
        """
        Remove expired domains from in-memory state.
        Returns number of removed domains.
        """
        now = reference_time or datetime.now()
        before_count = len(self.owned_domains)
        
        kept_domains: List[Dict] = []
        for domain_info in self.owned_domains:
            expires_at = self._coerce_datetime(domain_info.get("expires_at"))
            if expires_at is None or expires_at > now:
                kept_domains.append(domain_info)
        
        self.owned_domains = kept_domains
        removed_count = before_count - len(self.owned_domains)
        
        # Keep active_domain consistent with current ownership.
        current_domains = {entry.get("domain") for entry in self.owned_domains}
        if self.active_domain and self.active_domain not in current_domains:
            self.active_domain = self.owned_domains[-1]["domain"] if self.owned_domains else None
        
        return removed_count
    
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
