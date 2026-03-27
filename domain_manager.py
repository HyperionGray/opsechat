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
        self.last_budget_reset_period = self._get_budget_period()

    @staticmethod
    def _get_budget_period(now: Optional[datetime] = None) -> str:
        """Return the YYYY-MM budget period string for a datetime."""
        reference = now or datetime.now()
        return reference.strftime("%Y-%m")

    @staticmethod
    def _parse_budget_period(period: str):
        """Parse YYYY-MM period to comparable tuple, else None."""
        if not isinstance(period, str):
            return None
        parts = period.split("-")
        if len(parts) != 2:
            return None
        try:
            year = int(parts[0])
            month = int(parts[1])
        except ValueError:
            return None
        if month < 1 or month > 12:
            return None
        return (year, month)

    @staticmethod
    def _coerce_float(value, default: float = 0.0) -> float:
        """Coerce numeric/string values to float safely."""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace("€", "")
            if not cleaned:
                return default
            try:
                return float(cleaned)
            except ValueError:
                return default
        return default

    @staticmethod
    def _coerce_datetime(value) -> Optional[datetime]:
        """Convert datetime/ISO string to datetime, or None."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            # Handle common UTC suffix form in addition to plain ISO format.
            normalized = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                return None
        return None

    def reset_monthly_budget_if_needed(self, now: Optional[datetime] = None) -> bool:
        """
        Reset monthly spending when a new month starts.

        Returns:
            bool: True when a reset occurred, otherwise False.
        """
        current_period = self._get_budget_period(now=now)
        current_parsed = self._parse_budget_period(current_period)
        last_parsed = self._parse_budget_period(self.last_budget_reset_period)

        if last_parsed is None:
            self.last_budget_reset_period = current_period
            return False

        # Reset only when state is behind the current month.
        if last_parsed < current_parsed:
            logger.info(
                "Resetting monthly domain budget tracking (%s -> %s)",
                self.last_budget_reset_period,
                current_period,
            )
            self.current_spending = 0.0
            self.last_budget_reset_period = current_period
            return True

        if last_parsed > current_parsed:
            logger.warning(
                "Budget period %s is ahead of current period %s; keeping spending as-is",
                self.last_budget_reset_period,
                current_period,
            )
        return False
    
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
                price = result.get("price", 999)
                
                if isinstance(price, str):
                    # Remove currency symbols
                    price = float(price.replace("$", "").replace("€", ""))
                
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

        # Ensure budget window is current before evaluating available funds.
        self.reset_monthly_budget_if_needed()
        
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
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return self.owned_domains
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        self.reset_monthly_budget_if_needed()
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "budget_period": self.last_budget_reset_period,
        }

    def export_state(self) -> Dict:
        """
        Export manager state in JSON-serializable form.

        Datetime values are emitted as ISO 8601 strings.
        """
        self.reset_monthly_budget_if_needed()
        serialized_domains = []
        for domain in self.owned_domains:
            if not isinstance(domain, dict):
                continue
            serialized = domain.copy()
            purchased_at = self._coerce_datetime(serialized.get("purchased_at"))
            expires_at = self._coerce_datetime(serialized.get("expires_at"))
            if purchased_at:
                serialized["purchased_at"] = purchased_at.isoformat()
            if expires_at:
                serialized["expires_at"] = expires_at.isoformat()
            if "price" in serialized:
                serialized["price"] = self._coerce_float(serialized.get("price"))
            serialized_domains.append(serialized)

        return {
            "current_spending": self._coerce_float(self.current_spending),
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "last_budget_reset_period": self.last_budget_reset_period,
        }

    def import_state(self, state: Optional[Dict]):
        """
        Import persisted state from a dict.

        Gracefully handles missing fields and malformed values.
        """
        if not isinstance(state, dict):
            return

        self.current_spending = self._coerce_float(state.get("current_spending"))
        self.active_domain = state.get("active_domain") or None

        period = state.get("last_budget_reset_period")
        if isinstance(period, str) and period:
            self.last_budget_reset_period = period
        else:
            self.last_budget_reset_period = self._get_budget_period()

        normalized_domains = []
        for domain in state.get("owned_domains", []):
            if not isinstance(domain, dict):
                continue
            normalized = domain.copy()
            normalized["price"] = self._coerce_float(normalized.get("price"))
            normalized["purchased_at"] = self._coerce_datetime(
                normalized.get("purchased_at")
            )
            normalized["expires_at"] = self._coerce_datetime(
                normalized.get("expires_at")
            )
            normalized_domains.append(normalized)
        self.owned_domains = normalized_domains

        # If the imported state is from an older month, reset now.
        self.reset_monthly_budget_if_needed()


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
