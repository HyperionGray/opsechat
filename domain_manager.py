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
    
    @staticmethod
    def _parse_price(price: Any) -> Optional[float]:
        """Normalize registrar price values to float."""
        if price is None:
            return None
        
        if isinstance(price, (int, float)):
            return float(price)
        
        if isinstance(price, str):
            normalized = price.strip().replace("$", "").replace("€", "")
            normalized = normalized.replace(",", "")
            try:
                return float(normalized)
            except ValueError:
                return None
        
        return None
    
    @staticmethod
    def _parse_datetime(value: Any, fallback: Optional[datetime] = None) -> datetime:
        """Parse datetime from serialized state."""
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        
        return fallback or datetime.now()
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
    
    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> Dict:
        """
        Configure manager with Porkbun credentials.
        Returns a simple status dictionary for API/UI consumers.
        """
        api_key = (api_key or "").strip()
        secret_key = (secret_key or "").strip()
        
        if not api_key or not secret_key:
            return {
                "success": False,
                "error": "API key and secret key are required"
            }
        
        if monthly_budget <= 0:
            return {
                "success": False,
                "error": "Monthly budget must be greater than 0"
            }
        
        self.api_client = PorkbunAPIClient(api_key, secret_key)
        self.monthly_budget = float(monthly_budget)
        
        return {
            "success": True,
            "provider": "porkbun",
            "monthly_budget": self.monthly_budget
        }
    
    def get_config(self) -> Dict:
        """Return non-secret runtime configuration for UI and APIs."""
        return {
            "provider": "porkbun" if self.api_client else None,
            "configured": self.api_client is not None,
            "monthly_budget": self.monthly_budget,
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
                price = self._parse_price(result.get("price"))
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
    
    def rotate_domain_with_details(self) -> Dict:
        """Rotate domain and return API-friendly result object."""
        new_domain = self.rotate_domain()
        if new_domain:
            return {
                "success": True,
                "active_domain": new_domain,
                "budget_status": self.get_budget_status()
            }
        
        return {
            "success": False,
            "error": "Could not rotate domain within current constraints",
            "budget_status": self.get_budget_status()
        }
    
    def set_active_domain(self, domain: str) -> bool:
        """Set an owned domain as active without making a new purchase."""
        target = (domain or "").strip()
        if not target:
            return False
        
        for owned in self.owned_domains:
            if owned.get("domain") == target:
                self.active_domain = target
                return True
        
        return False
    
    def cleanup_expired_domains(self, now: Optional[datetime] = None) -> int:
        """Remove expired domains from local state and return removal count."""
        current_time = now or datetime.now()
        kept_domains: List[Dict] = []
        
        for domain in self.owned_domains:
            expires_at = self._parse_datetime(domain.get("expires_at"), fallback=current_time)
            if expires_at >= current_time:
                kept_domains.append(domain)
        
        removed = len(self.owned_domains) - len(kept_domains)
        self.owned_domains = kept_domains
        
        if self.active_domain and not any(d.get("domain") == self.active_domain for d in self.owned_domains):
            self.active_domain = self.owned_domains[0]["domain"] if self.owned_domains else None
        
        return removed
    
    def export_state(self) -> Dict:
        """Export JSON-safe state for persistence."""
        serialized_domains: List[Dict] = []
        
        for domain in self.owned_domains:
            serialized = dict(domain)
            purchased_at = self._parse_datetime(serialized.get("purchased_at"))
            expires_at = self._parse_datetime(
                serialized.get("expires_at"),
                fallback=purchased_at + timedelta(days=365)
            )
            serialized["purchased_at"] = purchased_at.isoformat()
            serialized["expires_at"] = expires_at.isoformat()
            serialized["price"] = self._parse_price(serialized.get("price"))
            serialized_domains.append(serialized)
        
        return {
            "current_spending": float(self.current_spending),
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain
        }
    
    def load_state(self, state: Dict):
        """Load persisted state from a dictionary."""
        self.current_spending = float(state.get("current_spending", 0.0) or 0.0)
        self.active_domain = state.get("active_domain")
        
        loaded_domains: List[Dict] = []
        for raw_domain in state.get("owned_domains", []):
            if not isinstance(raw_domain, dict):
                continue
            
            record = dict(raw_domain)
            if not record.get("domain"):
                continue
            
            purchased_at = self._parse_datetime(record.get("purchased_at"))
            expires_at = self._parse_datetime(
                record.get("expires_at"),
                fallback=purchased_at + timedelta(days=365)
            )
            record["purchased_at"] = purchased_at
            record["expires_at"] = expires_at
            record["price"] = self._parse_price(record.get("price"))
            loaded_domains.append(record)
        
        self.owned_domains = loaded_domains
        
        # Keep state coherent if active domain is stale or absent.
        self.cleanup_expired_domains()
    
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
