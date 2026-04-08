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
    def _parse_price(value: Any, default: float = 999.0) -> float:
        """Convert API/domain price values to float safely."""
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            cleaned = (
                value.strip()
                .replace("$", "")
                .replace("€", "")
                .replace(",", "")
            )
            if not cleaned:
                return default
            try:
                return float(cleaned)
            except ValueError:
                return default

        return default
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
    
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
                price = self._parse_price(result.get("price"), default=999.0)
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

        price = self._parse_price(price, default=-1.0)
        if price < 0:
            logger.error(f"Invalid purchase price for domain {domain}: {price}")
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

    @staticmethod
    def _serialize_datetime(value: Any) -> Optional[str]:
        """Serialize datetimes for JSON-safe state persistence."""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _deserialize_datetime(value: Any, fallback: datetime) -> datetime:
        """Convert persisted datetime values back to datetime objects."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return fallback
        return fallback

    def serialize_owned_domains(self) -> List[Dict]:
        """Return owned domains in a JSON-serializable format."""
        serialized_domains: List[Dict] = []

        for entry in self.owned_domains:
            if isinstance(entry, str):
                serialized_domains.append({"domain": entry, "price": 0.0})
                continue

            if not isinstance(entry, dict):
                continue

            domain_name = entry.get("domain")
            if not isinstance(domain_name, str) or not domain_name:
                continue

            domain_entry: Dict[str, Any] = {
                "domain": domain_name,
                "price": self._parse_price(entry.get("price"), default=0.0),
            }

            purchased_at = self._serialize_datetime(entry.get("purchased_at"))
            expires_at = self._serialize_datetime(entry.get("expires_at"))
            if purchased_at:
                domain_entry["purchased_at"] = purchased_at
            if expires_at:
                domain_entry["expires_at"] = expires_at

            serialized_domains.append(domain_entry)

        return serialized_domains

    def load_owned_domains(self, domains: Any) -> None:
        """Load persisted owned domain state, normalizing legacy formats."""
        loaded_domains: List[Dict] = []

        if not isinstance(domains, list):
            self.owned_domains = loaded_domains
            return

        for entry in domains:
            if isinstance(entry, str):
                loaded_domains.append({
                    "domain": entry,
                    "price": 0.0,
                    "purchased_at": datetime.now(),
                    "expires_at": datetime.now() + timedelta(days=365),
                })
                continue

            if not isinstance(entry, dict):
                continue

            domain_name = entry.get("domain")
            if not isinstance(domain_name, str) or not domain_name:
                continue

            purchased_default = datetime.now()
            purchased_at = self._deserialize_datetime(
                entry.get("purchased_at"),
                fallback=purchased_default,
            )
            expires_at = self._deserialize_datetime(
                entry.get("expires_at"),
                fallback=purchased_at + timedelta(days=365),
            )

            loaded_domains.append({
                "domain": domain_name,
                "price": self._parse_price(entry.get("price"), default=0.0),
                "purchased_at": purchased_at,
                "expires_at": expires_at,
            })

        self.owned_domains = loaded_domains

    def export_state(self) -> Dict:
        """Export manager state in JSON-safe format for persistence."""
        return {
            "state_version": 1,
            "monthly_budget": float(self.monthly_budget),
            "current_spending": self._parse_price(self.current_spending, default=0.0),
            "active_domain": self.active_domain,
            "owned_domains": self.serialize_owned_domains(),
        }

    def import_state(self, state: Any) -> None:
        """Import persisted state with backward compatibility for older configs."""
        if not isinstance(state, dict):
            return

        self.monthly_budget = self._parse_price(
            state.get("monthly_budget", self.monthly_budget),
            default=self.monthly_budget,
        )
        self.current_spending = self._parse_price(
            state.get("current_spending", 0.0),
            default=0.0,
        )

        active_domain = state.get("active_domain")
        self.active_domain = active_domain if isinstance(active_domain, str) else None

        self.load_owned_domains(state.get("owned_domains", []))
    
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
