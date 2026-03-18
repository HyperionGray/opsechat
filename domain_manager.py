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
        self.provider = "porkbun" if api_client else None
        self.spending_period = datetime.now().strftime("%Y-%m")
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.provider = "porkbun"

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0):
        """Configure Porkbun API client and budget settings."""
        if not api_key or not api_key.strip():
            raise ValueError("api_key is required")
        if not secret_key or not secret_key.strip():
            raise ValueError("secret_key is required")

        budget = float(monthly_budget)
        if budget <= 0:
            raise ValueError("monthly_budget must be greater than zero")

        self.api_client = PorkbunAPIClient(api_key.strip(), secret_key.strip())
        self.provider = "porkbun"
        self.monthly_budget = budget
        self.reset_monthly_spending_if_needed()
        logger.info("Domain manager configured with provider=%s", self.provider)
        return True

    def get_config(self) -> Dict[str, Any]:
        """Get non-sensitive domain configuration and current status."""
        budget_status = self.get_budget_status()
        return {
            "configured": self.api_client is not None,
            "provider": self.provider,
            "monthly_budget": self.monthly_budget,
            "spending_period": self.spending_period,
            "active_domain": self.active_domain,
            "budget_status": budget_status
        }

    def reset_monthly_spending_if_needed(self, now: Optional[datetime] = None):
        """Reset spending counters when calendar month changes."""
        current_period = (now or datetime.now()).strftime("%Y-%m")
        if self.spending_period != current_period:
            logger.info("Resetting domain spending for new month: %s", current_period)
            self.current_spending = 0.0
            self.spending_period = current_period

    @staticmethod
    def _serialize_datetime(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def export_state(self) -> Dict[str, Any]:
        """Export manager state in a JSON-serializable format."""
        self.reset_monthly_spending_if_needed()
        serialized_domains = []

        for domain_entry in self.owned_domains:
            if not isinstance(domain_entry, dict):
                continue

            entry = dict(domain_entry)
            entry["purchased_at"] = self._serialize_datetime(entry.get("purchased_at"))
            entry["expires_at"] = self._serialize_datetime(entry.get("expires_at"))
            serialized_domains.append(entry)

        return {
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "spending_period": self.spending_period
        }

    def import_state(self, state: Optional[Dict[str, Any]]):
        """Import previously persisted manager state."""
        if not state:
            return

        try:
            self.current_spending = float(state.get("current_spending", 0.0) or 0.0)
        except (TypeError, ValueError):
            self.current_spending = 0.0

        spending_period = state.get("spending_period")
        if isinstance(spending_period, str) and spending_period:
            self.spending_period = spending_period

        restored_domains: List[Dict[str, Any]] = []
        for domain_entry in state.get("owned_domains", []):
            if not isinstance(domain_entry, dict):
                continue

            entry = dict(domain_entry)
            parsed_purchased = self._parse_datetime(entry.get("purchased_at"))
            parsed_expires = self._parse_datetime(entry.get("expires_at"))

            if parsed_purchased:
                entry["purchased_at"] = parsed_purchased
            if parsed_expires:
                entry["expires_at"] = parsed_expires

            restored_domains.append(entry)

        self.owned_domains = restored_domains

        active_domain = state.get("active_domain")
        self.active_domain = active_domain if isinstance(active_domain, str) else None
        self.reset_monthly_spending_if_needed()

    def cleanup_expired_domains(self, now: Optional[datetime] = None) -> int:
        """Remove expired domains from local state and return removal count."""
        reference_time = now or datetime.now()
        retained_domains: List[Dict[str, Any]] = []
        removed_count = 0

        for domain_entry in self.owned_domains:
            if not isinstance(domain_entry, dict):
                continue

            expires_at = self._parse_datetime(domain_entry.get("expires_at"))
            if expires_at and expires_at <= reference_time:
                removed_count += 1
                continue

            if expires_at:
                domain_entry["expires_at"] = expires_at
            retained_domains.append(domain_entry)

        self.owned_domains = retained_domains

        if self.active_domain and not any(
            d.get("domain") == self.active_domain for d in self.owned_domains
        ):
            self.active_domain = self.owned_domains[-1]["domain"] if self.owned_domains else None

        return removed_count
    
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
                    try:
                        price = float(price.replace("$", "").replace("€", ""))
                    except ValueError:
                        logger.warning("Could not parse domain price: %s", price)
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
        
        self.reset_monthly_spending_if_needed()

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
        self.reset_monthly_spending_if_needed()
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
