"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _normalize_price(value: Any, default: float = 999.0) -> float:
    """Normalize registrar price values to float."""
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace("€", "").replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return default

    return default


def _parse_datetime(value: Any, fallback: Optional[datetime] = None) -> datetime:
    """Parse ISO datetimes from persisted state."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return fallback or datetime.now()


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
        pass
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        pass
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        pass


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
        self.provider: str = "porkbun"
        self.test_mode: bool = False
        self._api_key_last4: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
    
    def set_test_mode(self, enabled: bool):
        """Enable/disable simulation mode for safe testing."""
        self.test_mode = bool(enabled)
    
    def configure(self, api_key: str, secret_key: str,
                  monthly_budget: float = 50.0, provider: str = "porkbun"):
        """Configure domain registrar client and budget."""
        if not api_key or not secret_key:
            raise ValueError("API key and secret key are required")
        if monthly_budget <= 0:
            raise ValueError("Monthly budget must be greater than 0")
        normalized_provider = provider.lower().strip()
        if normalized_provider != "porkbun":
            raise ValueError(f"Unsupported registrar provider: {provider}")
        
        self.provider = normalized_provider
        self.monthly_budget = float(monthly_budget)
        self.api_client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
        self._api_key_last4 = api_key[-4:]
    
    def get_config(self) -> Dict[str, Any]:
        """Return current domain rotation configuration snapshot."""
        return {
            "provider": self.provider,
            "configured": self.api_client is not None,
            "api_key_masked": f"****{self._api_key_last4}" if self._api_key_last4 else None,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode
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
        if not self.api_client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = _normalize_price(result.get("price", 999))
                
                if price <= max_price:
                    return {
                        "domain": result.get("domain", domain),
                        "price": price,
                        "tld": tld
                    }
        
        return None
    
    def search_cheap_domains(self, tlds: Optional[List[str]] = None,
                            max_price: float = 5.0, limit: int = 5,
                            max_attempts_per_result: int = 3) -> List[Dict]:
        """
        Search for multiple cheap available domains.
        Useful for previewing options before purchasing.
        """
        if limit <= 0:
            return []
        
        results: List[Dict] = []
        seen = set()
        total_attempts = max(limit * max_attempts_per_result, limit)
        
        for _ in range(total_attempts):
            if len(results) >= limit:
                break
            domain_info = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=tlds
            )
            if not domain_info:
                continue
            domain_name = domain_info["domain"]
            if domain_name in seen:
                continue
            seen.add(domain_name)
            results.append(domain_info)
        
        return results
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False
        
        normalized_price = _normalize_price(price, default=-1.0)
        if normalized_price < 0:
            logger.error(f"Invalid price for domain purchase: {price}")
            return False
        
        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            purchased_at = datetime.now()
            self.current_spending += normalized_price
            self.owned_domains.append({
                "domain": domain,
                "price": normalized_price,
                "order_id": result.get("order_id"),
                "purchased_at": purchased_at,
                "expires_at": purchased_at + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${normalized_price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Rotate to a new domain with structured success/error output.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price, max_attempts=20)
        
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find an available cheap domain",
                "domain": None
            }
        
        if self.test_mode:
            self.active_domain = domain_info["domain"]
            return {
                "success": True,
                "domain": self.active_domain,
                "cost": domain_info["price"],
                "test_mode": True
            }
        
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"]
        )
        if not success:
            return {
                "success": False,
                "error": "Failed to purchase domain or budget exceeded",
                "domain": None
            }
        
        return {
            "success": True,
            "domain": domain_info["domain"],
            "cost": domain_info["price"],
            "test_mode": False
        }
    
    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        result = self.rotate_to_new_domain()
        if result.get("success"):
            return result.get("domain")
        logger.error(result.get("error"))
        return None
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return deepcopy(self.owned_domains)
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }
    
    def export_state(self) -> Dict[str, Any]:
        """Export serializable state for persistence."""
        owned_domains: List[Dict[str, Any]] = []
        for domain in self.owned_domains:
            purchased_at = _parse_datetime(domain.get("purchased_at"))
            expires_at = _parse_datetime(
                domain.get("expires_at"),
                fallback=purchased_at + timedelta(days=365)
            )
            owned_domains.append({
                "domain": domain.get("domain"),
                "price": _normalize_price(domain.get("price", 0.0), default=0.0),
                "order_id": domain.get("order_id"),
                "purchased_at": purchased_at.isoformat(),
                "expires_at": expires_at.isoformat()
            })
        
        return {
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "owned_domains": owned_domains,
            "monthly_budget": self.monthly_budget,
            "provider": self.provider
        }
    
    def load_state(self, state: Optional[Dict[str, Any]] = None):
        """Load manager state from persisted data."""
        if not state:
            return
        
        self.current_spending = float(state.get("current_spending", self.current_spending))
        self.active_domain = state.get("active_domain", self.active_domain)
        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))
        self.provider = state.get("provider", self.provider)
        
        loaded_domains = []
        for domain in state.get("owned_domains", []):
            purchased_at = _parse_datetime(domain.get("purchased_at"))
            expires_at = _parse_datetime(
                domain.get("expires_at"),
                fallback=purchased_at + timedelta(days=365)
            )
            loaded_domains.append({
                "domain": domain.get("domain"),
                "price": _normalize_price(domain.get("price", 0.0), default=0.0),
                "order_id": domain.get("order_id"),
                "purchased_at": purchased_at,
                "expires_at": expires_at
            })
        
        self.owned_domains = loaded_domains


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
