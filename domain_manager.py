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
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.spending_period = datetime.utcnow().strftime("%Y-%m")
        self._api_key_suffix: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """Convert values to float safely."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace("€", "")
            try:
                return float(cleaned)
            except ValueError:
                return default
        return default

    @staticmethod
    def _safe_parse_datetime(value: Any, fallback: datetime) -> datetime:
        """Parse datetime values from either datetime objects or ISO strings."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return fallback
        return fallback

    def _normalize_owned_domain_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize owned-domain records loaded from external state."""
        now = datetime.now()
        purchased_at = self._safe_parse_datetime(entry.get("purchased_at"), now)
        expires_at = self._safe_parse_datetime(
            entry.get("expires_at"),
            purchased_at + timedelta(days=365),
        )
        return {
            "domain": str(entry.get("domain", "")),
            "price": self._safe_float(entry.get("price"), default=0.0),
            "purchased_at": purchased_at,
            "expires_at": expires_at,
        }

    def _reset_budget_if_new_month(self):
        """Reset tracked spending when a new UTC month begins."""
        current_period = datetime.utcnow().strftime("%Y-%m")
        if self.spending_period != current_period:
            self.current_spending = 0.0
            self.spending_period = current_period

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> bool:
        """
        Configure registrar API credentials and budget settings.

        Returns True when credentials are applied successfully.
        """
        if not api_key or not secret_key:
            raise ValueError("Both api_key and secret_key are required")

        budget = self._safe_float(monthly_budget, default=-1.0)
        if budget <= 0:
            raise ValueError("monthly_budget must be greater than zero")

        self.set_api_client(PorkbunAPIClient(api_key, secret_key))
        self.monthly_budget = budget
        self._api_key_suffix = api_key[-4:] if len(api_key) >= 4 else api_key
        return True

    def get_config(self) -> Dict[str, Any]:
        """Return non-sensitive domain manager configuration details."""
        return {
            "configured": self.api_client is not None,
            "api_key_masked": f"{'*' * 8}{self._api_key_suffix}" if self._api_key_suffix else "",
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "spending_period": self.spending_period,
        }

    def export_state(self) -> Dict[str, Any]:
        """Export JSON-safe manager state for persistence."""
        return {
            "current_spending": self.current_spending,
            "owned_domains": [
                {
                    "domain": domain.get("domain"),
                    "price": domain.get("price"),
                    "purchased_at": domain.get("purchased_at").isoformat()
                    if isinstance(domain.get("purchased_at"), datetime)
                    else domain.get("purchased_at"),
                    "expires_at": domain.get("expires_at").isoformat()
                    if isinstance(domain.get("expires_at"), datetime)
                    else domain.get("expires_at"),
                }
                for domain in self.owned_domains
            ],
            "active_domain": self.active_domain,
            "monthly_budget": self.monthly_budget,
            "spending_period": self.spending_period,
        }

    def import_state(self, state: Dict[str, Any]):
        """Import persisted state and normalize record types."""
        if not isinstance(state, dict):
            return

        self.current_spending = self._safe_float(state.get("current_spending"), default=0.0)
        self.monthly_budget = self._safe_float(
            state.get("monthly_budget", self.monthly_budget),
            default=self.monthly_budget,
        )
        self.active_domain = state.get("active_domain") or None
        self.spending_period = str(state.get("spending_period") or self.spending_period)

        owned_domains = state.get("owned_domains", [])
        if isinstance(owned_domains, list):
            self.owned_domains = [
                self._normalize_owned_domain_entry(domain)
                for domain in owned_domains
                if isinstance(domain, dict)
            ]

        self._reset_budget_if_new_month()
    
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
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = self._safe_float(result.get("price"), default=999.0)
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
        if not self.api_client:
            logger.error("No API client configured")
            return False
        
        self._reset_budget_if_new_month()

        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
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

    def rotate_domain_with_details(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Rotate to a new domain and return structured details.
        Useful for API and web responses.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            return {
                "success": False,
                "error": "No available domain found within budget constraints",
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
        )
        if not success:
            return {
                "success": False,
                "error": "Purchase failed or exceeded monthly budget",
                "domain": domain_info["domain"],
                "price": domain_info["price"],
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "price": domain_info["price"],
            "budget_status": self.get_budget_status(),
        }
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        self._reset_budget_if_new_month()
        return self.owned_domains
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        self._reset_budget_if_new_month()
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
