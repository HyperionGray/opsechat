"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
from abc import ABC, abstractmethod
import requests
import random
import string
import logging
import re
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
        self.spending_month = self._current_month_key()
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    @staticmethod
    def _mask_api_key(value: Optional[str]) -> str:
        """Mask API key for safe display/logging."""
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"

    def _current_month_key(self, at_time: Optional[datetime] = None) -> str:
        """Return YYYY-MM for monthly budget tracking."""
        now = at_time or datetime.utcnow()
        return f"{now.year:04d}-{now.month:02d}"

    def _reset_monthly_spending_if_needed(self):
        """Reset spending when the month rolls over."""
        current_month = self._current_month_key()
        if self.spending_month != current_month:
            logger.info(
                "Resetting monthly domain spending from %s to %s",
                self.spending_month,
                current_month,
            )
            self.current_spending = 0.0
            self.spending_month = current_month

    @staticmethod
    def _normalize_price(raw_price: Any) -> Optional[float]:
        """Normalize API price values to float."""
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if isinstance(raw_price, str):
            match = re.search(r"\d+(?:\.\d+)?", raw_price.replace(",", ""))
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    return None
        return None

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0):
        """Configure Porkbun credentials and budget."""
        if not api_key or not secret_key:
            raise ValueError("Both api_key and secret_key are required")

        budget_value = float(monthly_budget)
        if budget_value <= 0:
            raise ValueError("monthly_budget must be greater than 0")

        self.api_client = PorkbunAPIClient(api_key, secret_key)
        self.monthly_budget = budget_value
        self._reset_monthly_spending_if_needed()

    def get_config(self) -> Dict:
        """Return safe domain rotation configuration/status."""
        self._reset_monthly_spending_if_needed()
        api_key = self.api_client.api_key if self.api_client else None
        return {
            "configured": bool(self.api_client),
            "provider": self.api_client.__class__.__name__ if self.api_client else None,
            "api_key_masked": self._mask_api_key(api_key),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "spending_month": self.spending_month,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def export_state(self) -> Dict:
        """Export serializable manager state."""
        self._reset_monthly_spending_if_needed()

        serialized_domains: List[Dict] = []
        for domain in self.owned_domains:
            purchased_at = domain.get("purchased_at")
            expires_at = domain.get("expires_at")
            serialized_domains.append(
                {
                    "domain": domain.get("domain"),
                    "price": domain.get("price"),
                    "purchased_at": (
                        purchased_at.isoformat() if isinstance(purchased_at, datetime) else purchased_at
                    ),
                    "expires_at": (
                        expires_at.isoformat() if isinstance(expires_at, datetime) else expires_at
                    ),
                }
            )

        return {
            "current_spending": self.current_spending,
            "spending_month": self.spending_month,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
        }

    def import_state(self, state: Dict):
        """Import manager state (supports serialized datetime strings)."""
        if not state:
            return

        self.current_spending = float(state.get("current_spending", 0.0))
        self.spending_month = state.get("spending_month", self._current_month_key())
        self.active_domain = state.get("active_domain")

        imported_domains: List[Dict] = []
        for domain in state.get("owned_domains", []):
            purchased_at = domain.get("purchased_at")
            expires_at = domain.get("expires_at")

            if isinstance(purchased_at, str):
                try:
                    purchased_at = datetime.fromisoformat(purchased_at)
                except ValueError:
                    purchased_at = datetime.utcnow()

            if isinstance(expires_at, str):
                try:
                    expires_at = datetime.fromisoformat(expires_at)
                except ValueError:
                    expires_at = datetime.utcnow() + timedelta(days=365)

            imported_domains.append(
                {
                    "domain": domain.get("domain"),
                    "price": domain.get("price"),
                    "purchased_at": purchased_at,
                    "expires_at": expires_at,
                }
            )

        self.owned_domains = imported_domains
        self._reset_monthly_spending_if_needed()
    
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
        self._reset_monthly_spending_if_needed()

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
            now = datetime.utcnow()
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
    
    def rotate_domain(self, return_details: bool = False):
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            if return_details:
                return {"success": False, "error": "Could not find available cheap domain"}
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
                    "price": domain_info["price"],
                    "tld": domain_info["tld"],
                }
            return self.active_domain
        
        if return_details:
            return {
                "success": False,
                "error": "Failed to purchase domain",
                "domain": domain_info["domain"],
                "price": domain_info["price"],
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
        self._reset_monthly_spending_if_needed()
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "spending_month": self.spending_month,
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
