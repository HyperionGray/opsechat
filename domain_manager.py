"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
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
        raise NotImplementedError("Subclasses must implement search_domain")
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("Subclasses must implement purchase_domain")
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError("Subclasses must implement get_pricing")


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
    def _normalize_price(raw_price: Any) -> Optional[float]:
        """Convert price to float when possible."""
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if isinstance(raw_price, str):
            cleaned = raw_price.strip().replace("$", "").replace("€", "")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_datetime(raw_value: Any) -> Optional[datetime]:
        """Parse datetime from known formats."""
        if raw_value is None:
            return None
        if isinstance(raw_value, datetime):
            return raw_value
        if isinstance(raw_value, str):
            try:
                return datetime.fromisoformat(raw_value)
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
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = self._normalize_price(result.get("price"))

                if price is not None and price <= max_price:
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
        
        normalized_price = self._normalize_price(price)
        if normalized_price is None:
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
            now = datetime.now()
            self.current_spending += normalized_price
            self.owned_domains.append({
                "domain": domain,
                "price": normalized_price,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${normalized_price}")
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
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return self.owned_domains

    def export_state(self) -> Dict[str, Any]:
        """Export manager state in a JSON-serializable format."""
        serialized_domains = []
        for entry in self.owned_domains:
            domain = entry.get("domain")
            if not domain:
                continue
            purchased_at = self._parse_datetime(entry.get("purchased_at"))
            expires_at = self._parse_datetime(entry.get("expires_at"))
            serialized_domains.append({
                "domain": domain,
                "price": self._normalize_price(entry.get("price")),
                "purchased_at": purchased_at.isoformat() if purchased_at else None,
                "expires_at": expires_at.isoformat() if expires_at else None,
            })

        return {
            "current_spending": float(self.current_spending),
            "active_domain": self.active_domain,
            "owned_domains": serialized_domains,
        }

    def import_state(self, state: Optional[Dict[str, Any]]) -> None:
        """Import manager state from persisted JSON data."""
        if not state:
            return

        try:
            self.current_spending = float(state.get("current_spending", 0.0) or 0.0)
        except (TypeError, ValueError):
            self.current_spending = 0.0

        self.active_domain = state.get("active_domain")
        restored_domains: List[Dict] = []

        for entry in state.get("owned_domains", []):
            if not isinstance(entry, dict):
                continue
            domain = entry.get("domain")
            if not domain:
                continue

            price = self._normalize_price(entry.get("price"))
            purchased_at = self._parse_datetime(entry.get("purchased_at"))
            expires_at = self._parse_datetime(entry.get("expires_at"))

            if purchased_at is None:
                purchased_at = datetime.now()
            if expires_at is None:
                expires_at = purchased_at + timedelta(days=365)

            restored_domains.append({
                "domain": domain,
                "price": price if price is not None else 0.0,
                "purchased_at": purchased_at,
                "expires_at": expires_at,
            })

        self.owned_domains = restored_domains

        if self.active_domain and all(d["domain"] != self.active_domain for d in self.owned_domains):
            self.active_domain = self.owned_domains[0]["domain"] if self.owned_domains else None

    def cleanup_expired_domains(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Remove expired domains and keep active domain consistent."""
        now = now or datetime.now()
        removed_domains: List[str] = []
        remaining_domains: List[Dict] = []

        for domain_entry in self.owned_domains:
            expires_at = self._parse_datetime(domain_entry.get("expires_at"))
            if expires_at and expires_at <= now:
                removed_domains.append(domain_entry.get("domain", "unknown"))
                continue

            if expires_at is None:
                # If expiry is missing or malformed, preserve the domain and set a safe default.
                purchased_at = self._parse_datetime(domain_entry.get("purchased_at")) or now
                domain_entry["expires_at"] = purchased_at + timedelta(days=365)
            else:
                domain_entry["expires_at"] = expires_at

            purchased_at = self._parse_datetime(domain_entry.get("purchased_at")) or now
            domain_entry["purchased_at"] = purchased_at
            remaining_domains.append(domain_entry)

        self.owned_domains = remaining_domains

        if self.active_domain in removed_domains:
            self.active_domain = self.owned_domains[0]["domain"] if self.owned_domains else None

        return {
            "removed_domains": removed_domains,
            "removed_count": len(removed_domains),
            "remaining_count": len(self.owned_domains),
            "active_domain": self.active_domain,
        }
    
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
