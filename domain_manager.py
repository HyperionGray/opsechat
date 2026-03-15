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
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
    
    @staticmethod
    def _mask_secret(value: Optional[str]) -> str:
        """Mask sensitive values while keeping a short suffix for verification."""
        if not value:
            return ""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * 8}{value[-4:]}"
    
    @staticmethod
    def _parse_price(price: Any) -> Optional[float]:
        """
        Parse registrar pricing values into float.
        Accepts float/int values and common string formats like "$2.99".
        """
        if isinstance(price, (int, float)):
            return float(price)
        
        if isinstance(price, str):
            normalized = (
                price.strip()
                .replace("$", "")
                .replace("€", "")
                .replace(",", "")
            )
            try:
                return float(normalized)
            except ValueError:
                return None
        
        return None
    
    @staticmethod
    def _serialize_domain_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert domain record into JSON-safe structure."""
        serialized = dict(record)
        for key in ("purchased_at", "expires_at"):
            value = serialized.get(key)
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
        return serialized
    
    @staticmethod
    def _deserialize_domain_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert persisted domain record into runtime structure."""
        deserialized = dict(record)
        for key in ("purchased_at", "expires_at"):
            value = deserialized.get(key)
            if isinstance(value, str):
                try:
                    deserialized[key] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep unparseable values as-is for forward compatibility.
                    pass
        return deserialized
    
    def export_state(self) -> Dict[str, Any]:
        """Export manager state to a JSON-serializable dictionary."""
        return {
            "current_spending": self.current_spending,
            "owned_domains": [
                self._serialize_domain_record(record)
                for record in self.owned_domains
            ],
            "active_domain": self.active_domain,
        }
    
    def import_state(self, state: Dict[str, Any]):
        """Import state from a dictionary produced by export_state()."""
        self.current_spending = float(state.get("current_spending", 0.0) or 0.0)
        
        owned_domains = state.get("owned_domains", [])
        if isinstance(owned_domains, list):
            self.owned_domains = [
                self._deserialize_domain_record(record)
                for record in owned_domains
                if isinstance(record, dict)
            ]
        else:
            self.owned_domains = []
        
        active_domain = state.get("active_domain")
        self.active_domain = active_domain if isinstance(active_domain, str) else None
    
    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0):
        """
        Configure manager for Porkbun-backed domain rotation.
        Used by the web API and CLI setup flows.
        """
        if not api_key or not secret_key:
            raise ValueError("api_key and secret_key are required")
        if monthly_budget <= 0:
            raise ValueError("monthly_budget must be greater than zero")
        
        self._api_key = api_key
        self._api_secret = secret_key
        self.monthly_budget = float(monthly_budget)
        self.api_client = PorkbunAPIClient(api_key, secret_key)
    
    def get_config(self) -> Dict[str, Any]:
        """Return current configuration and budget status for UI/API views."""
        return {
            "configured": self.api_client is not None,
            "api_key_masked": self._mask_secret(self._api_key),
            "api_secret_masked": self._mask_secret(self._api_secret),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
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
                    logger.warning(
                        "Skipping domain %s due to unparseable price: %r",
                        domain,
                        result.get("price"),
                    )
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
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain_result(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Rotate to a new domain and return a structured result payload.
        This is useful for API handlers and CLI integrations.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain",
                "budget_status": self.get_budget_status(),
            }
        
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"]
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            return {
                "success": True,
                "domain": self.active_domain,
                "price": domain_info["price"],
                "budget_status": self.get_budget_status(),
            }
        
        return {
            "success": False,
            "error": "Domain purchase failed or budget exceeded",
            "budget_status": self.get_budget_status(),
        }
    
    def rotate_domain(self, max_price: float = 5.0) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        result = self.rotate_domain_result(max_price=max_price)
        if result.get("success"):
            return result.get("domain")
        logger.error(result.get("error", "Domain rotation failed"))
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
