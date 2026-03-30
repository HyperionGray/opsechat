"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from typing import Any, Dict, List, Optional, Union
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
        self._api_key_masked: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def _mask_key(self, key: str) -> str:
        """Mask API key for safe display in UI/config output."""
        if not key:
            return ""
        if len(key) <= 4:
            return "*" * len(key)
        return f"{'*' * max(len(key) - 4, 4)}{key[-4:]}"

    def _parse_price(self, value: Union[str, int, float, None], default: float = 999.0) -> float:
        """Parse registrar price strings like '$1.99' into float."""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace("€", "").replace(",", "")
            try:
                return float(cleaned)
            except ValueError:
                logger.warning("Could not parse price value: %r", value)
                return default
        return default

    def _normalize_domain_entry(self, domain_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize persisted domain entries from JSON into in-memory format.
        Supports ISO datetime strings for purchased_at/expires_at.
        """
        normalized = dict(domain_entry)
        for field in ("purchased_at", "expires_at"):
            value = normalized.get(field)
            if isinstance(value, str):
                try:
                    normalized[field] = datetime.fromisoformat(value)
                except ValueError:
                    logger.warning("Ignoring invalid datetime for %s: %r", field, value)
                    normalized[field] = None
        return normalized

    def _serialize_domain_entry(self, domain_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize in-memory domain entry into JSON-safe primitives."""
        serialized = dict(domain_entry)
        for field in ("purchased_at", "expires_at"):
            value = serialized.get(field)
            if isinstance(value, datetime):
                serialized[field] = value.isoformat()
        return serialized

    def configure(self, api_key: str, secret_key: Optional[str] = None,
                  api_secret: Optional[str] = None, monthly_budget: float = 50.0) -> Dict:
        """
        Configure the domain manager with API credentials and budget.
        Accepts either secret_key or api_secret for compatibility.
        """
        resolved_secret = secret_key or api_secret
        if not api_key or not resolved_secret:
            raise ValueError("Both api_key and secret_key/api_secret are required")

        self.set_api_client(PorkbunAPIClient(api_key, resolved_secret))
        self.monthly_budget = float(monthly_budget)
        self._api_key_masked = self._mask_key(api_key)

        return {
            "configured": True,
            "provider": "porkbun",
            "api_key_masked": self._api_key_masked,
            "monthly_budget": self.monthly_budget
        }

    def get_config(self) -> Dict:
        """Return non-sensitive domain rotation configuration details."""
        return {
            "configured": self.api_client is not None,
            "provider": "porkbun" if self.api_client else None,
            "api_key_masked": self._api_key_masked,
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain
        }

    def load_state(self, state: Optional[Dict[str, Any]]) -> None:
        """Load saved state into the manager (safe for JSON-deserialized values)."""
        if not state:
            return

        if "current_spending" in state:
            self.current_spending = float(state.get("current_spending") or 0.0)
        if "monthly_budget" in state:
            self.monthly_budget = float(state.get("monthly_budget") or self.monthly_budget)
        if "active_domain" in state:
            self.active_domain = state.get("active_domain") or None
        if "owned_domains" in state and isinstance(state["owned_domains"], list):
            self.owned_domains = [self._normalize_domain_entry(item) for item in state["owned_domains"]]
        if "api_key_masked" in state:
            self._api_key_masked = state.get("api_key_masked")

    def export_state(self) -> Dict[str, Any]:
        """Export state in JSON-safe form for persistence by callers."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": [self._serialize_domain_entry(item) for item in self.owned_domains],
            "active_domain": self.active_domain,
            "api_key_masked": self._api_key_masked
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
                price = self._parse_price(result.get("price"), default=999.0)
                
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float, years: int = 1) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False
        
        estimated_total = price * max(years, 1)

        # Check budget
        if self.current_spending + estimated_total > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${estimated_total}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=years)
        
        if result.get("success"):
            self.current_spending += estimated_total
            self.owned_domains.append({
                "domain": domain,
                "price": estimated_total,
                "price_per_year": price,
                "years": years,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365 * max(years, 1))
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self, return_details: bool = False) -> Optional[Union[str, Dict]]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        previous_domain = self.active_domain
        budget_before = self.get_budget_status()

        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            if return_details:
                return {
                    "success": False,
                    "error": "Could not find available cheap domain",
                    "active_domain": previous_domain,
                    "budget_status": budget_before
                }
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            if return_details:
                return {
                    "success": True,
                    "domain": self.active_domain,
                    "previous_domain": previous_domain,
                    "price": domain_info["price"],
                    "budget_status": self.get_budget_status()
                }
            return self.active_domain
        
        if return_details:
            return {
                "success": False,
                "error": "Purchase failed or exceeded budget",
                "candidate_domain": domain_info["domain"],
                "candidate_price": domain_info["price"],
                "active_domain": previous_domain,
                "budget_status": self.get_budget_status()
            }
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
