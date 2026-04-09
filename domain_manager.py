"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from typing import Dict, List, Optional
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
        # API credentials stored internally only - not exposed via get_config()
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> bool:
        """Configure registrar credentials and budget."""
        self._api_key = api_key.strip() or None
        self._api_secret = secret_key.strip() or None
        self.monthly_budget = float(monthly_budget)

        if not self._api_key or not self._api_secret:
            self.api_client = None
            return False

        self.api_client = PorkbunAPIClient(self._api_key, self._api_secret)
        return True

    def get_config(self) -> Dict:
        """Return safe configuration details for UI/API use."""
        return {
            "configured": self.api_client is not None,
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            # API key presence intentionally omitted for security
        }

    @staticmethod
    def _parse_datetime(value) -> Optional[datetime]:
        """Parse datetime values from either datetime objects or ISO strings."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @classmethod
    def _normalize_owned_domain(cls, entry: Dict) -> Optional[Dict]:
        """Normalize persisted domain entries into runtime-safe records."""
        if not isinstance(entry, dict):
            return None

        domain = str(entry.get("domain", "")).strip()
        if not domain:
            return None

        try:
            price = float(entry.get("price", 0.0))
        except (TypeError, ValueError):
            price = 0.0

        purchased_at = cls._parse_datetime(entry.get("purchased_at")) or datetime.now()
        expires_at = cls._parse_datetime(entry.get("expires_at")) or (purchased_at + timedelta(days=365))

        return {
            "domain": domain,
            "price": price,
            "purchased_at": purchased_at,
            "expires_at": expires_at,
        }

    def load_state(self, state: Optional[Dict]) -> Dict:
        """
        Load persisted state from a dict.

        This accepts JSON-safe values and normalizes them for runtime use.
        """
        state = state or {}

        try:
            self.current_spending = float(state.get("current_spending", 0.0))
        except (TypeError, ValueError):
            self.current_spending = 0.0

        normalized_domains: List[Dict] = []
        for raw_entry in state.get("owned_domains", []):
            normalized = self._normalize_owned_domain(raw_entry)
            if normalized:
                normalized_domains.append(normalized)
        self.owned_domains = normalized_domains

        active = state.get("active_domain")
        self.active_domain = active.strip() if isinstance(active, str) and active.strip() else None

        return {
            "current_spending": self.current_spending,
            "domains_loaded": len(self.owned_domains),
            "active_domain": self.active_domain,
        }

    def export_state(self) -> Dict:
        """Export runtime state in JSON-safe format."""
        return {
            "current_spending": self.current_spending,
            "owned_domains": [
                {
                    "domain": entry["domain"],
                    "price": entry["price"],
                    "purchased_at": entry["purchased_at"].isoformat(),
                    "expires_at": entry["expires_at"].isoformat(),
                }
                for entry in self.owned_domains
            ],
            "active_domain": self.active_domain,
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
                price = result.get("price", 999)
                
                if isinstance(price, str):
                    # Remove currency symbols and normalize to float.
                    try:
                        price = float(price.replace("$", "").replace("€", ""))
                    except ValueError:
                        continue
                
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> Dict:
        """
        Purchase domain if within budget
        Returns structured result
        """
        if not self.api_client:
            logger.error("No API client configured")
            return {
                "success": False,
                "domain": domain,
                "message": "No API client configured",
            }
        
        # Check budget
        try:
            price = float(price)
        except (TypeError, ValueError):
            return {
                "success": False,
                "domain": domain,
                "message": "Invalid price value",
                "budget_status": self.get_budget_status(),
            }

        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return {
                "success": False,
                "domain": domain,
                "message": "Budget exceeded",
                "budget_status": self.get_budget_status(),
            }
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            now = datetime.now()
            self.current_spending += price
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
            return {
                "success": True,
                "domain": domain,
                "price": price,
                "message": "Domain purchased successfully",
                "active_domain": self.active_domain,
                "budget_status": self.get_budget_status(),
            }
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Failed to purchase domain"),
                "budget_status": self.get_budget_status(),
            }
    
    def rotate_domain(self) -> Dict:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {
                "success": False,
                "message": "Could not find available cheap domain",
                "budget_status": self.get_budget_status(),
            }
        
        # Purchase domain
        result = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )
        
        if result.get("success"):
            self.active_domain = domain_info["domain"]
            result["active_domain"] = self.active_domain

        return result
    
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
