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
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        monthly_budget: Optional[float] = None
    ) -> None:
        """
        Configure domain purchasing via Porkbun credentials.

        Supports both `secret_key` and `api_secret` naming to stay compatible
        with older callers.
        """
        resolved_secret = secret_key or api_secret
        if not api_key or not resolved_secret:
            raise ValueError("Both api_key and secret_key/api_secret are required")

        self.api_client = PorkbunAPIClient(api_key, resolved_secret)

        if monthly_budget is not None:
            budget_value = float(monthly_budget)
            if budget_value <= 0:
                raise ValueError("monthly_budget must be greater than 0")
            self.monthly_budget = budget_value

    def get_config(self) -> Dict[str, Any]:
        """Return current runtime configuration and budget summary."""
        return {
            "configured": self.api_client is not None,
            "provider": self.api_client.__class__.__name__ if self.api_client else None,
            "api_key_configured": bool(getattr(self.api_client, "api_key", "")),
            "api_secret_configured": bool(getattr(self.api_client, "api_secret", "")),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "budget_status": self.get_budget_status(),
        }

    @staticmethod
    def _parse_price(value: Any) -> Optional[float]:
        """Parse registrar price values into float, if possible."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            sanitized = value.replace("$", "").replace("€", "").strip()
            if not sanitized:
                return None
            try:
                return float(sanitized)
            except ValueError:
                return None
        return None

    @staticmethod
    def _serialize_domain_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert in-memory domain record to JSON-safe format."""
        serialized = dict(record)
        for key in ("purchased_at", "expires_at"):
            value = serialized.get(key)
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
        return serialized

    @staticmethod
    def _deserialize_domain_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert persisted domain record back to in-memory format."""
        deserialized = dict(record)
        for key in ("purchased_at", "expires_at"):
            value = deserialized.get(key)
            if isinstance(value, str):
                try:
                    deserialized[key] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep legacy/unparseable values as-is instead of crashing.
                    pass
        return deserialized

    def export_state(self) -> Dict[str, Any]:
        """Export manager runtime state to a JSON-safe dictionary."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": [
                self._serialize_domain_record(record) for record in self.owned_domains
            ],
            "active_domain": self.active_domain,
        }

    def load_state(self, state: Optional[Dict[str, Any]]) -> None:
        """Load manager runtime state from persisted data."""
        if not state:
            return

        if "monthly_budget" in state:
            try:
                budget = float(state["monthly_budget"])
                if budget > 0:
                    self.monthly_budget = budget
            except (TypeError, ValueError):
                pass

        if "current_spending" in state:
            try:
                self.current_spending = float(state["current_spending"])
            except (TypeError, ValueError):
                self.current_spending = 0.0

        loaded_domains: List[Dict[str, Any]] = []
        for record in state.get("owned_domains", []):
            if isinstance(record, dict):
                loaded_domains.append(self._deserialize_domain_record(record))
        self.owned_domains = loaded_domains
        self.active_domain = state.get("active_domain")
    
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

        parsed_price = self._parse_price(price)
        if parsed_price is None:
            logger.error(f"Invalid domain price value: {price}")
            return False
        
        # Check budget
        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${parsed_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            now = datetime.now()
            self.current_spending += parsed_price
            self.owned_domains.append({
                "domain": domain,
                "price": parsed_price,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${parsed_price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False

    def rotate_domain_with_details(self) -> Dict[str, Any]:
        """
        Rotate to a new domain and return a structured status response.

        This is used by API routes that expect JSON objects instead of a string.
        """
        domain_info = self.find_cheap_available_domain()
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {
                "success": False,
                "error": "Could not find available cheap domain",
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"]
        )
        if not success:
            return {
                "success": False,
                "error": "Failed to purchase domain within current budget",
                "domain": domain_info["domain"],
                "price": domain_info["price"],
                "budget_status": self.get_budget_status(),
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "price": domain_info["price"],
            "budget_status": self.get_budget_status(),
        }
    
    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        result = self.rotate_domain_with_details()
        if result.get("success"):
            return result.get("domain")
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
