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

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> Dict[str, Any]:
        """Configure registrar credentials and budget."""
        if not api_key or not secret_key:
            raise ValueError("API key and secret key are required")

        parsed_budget = self._parse_price(monthly_budget)
        if parsed_budget is None or parsed_budget <= 0:
            raise ValueError("Monthly budget must be a positive number")

        self.api_client = PorkbunAPIClient(api_key, secret_key)
        self.monthly_budget = parsed_budget

        return {
            "configured": True,
            "monthly_budget": self.monthly_budget,
        }

    def get_config(self) -> Dict[str, Any]:
        """Return current domain rotation configuration summary."""
        has_client = isinstance(self.api_client, DomainAPIClient)
        api_key_tail = ""
        if has_client and getattr(self.api_client, "api_key", None):
            api_key_tail = str(self.api_client.api_key)[-4:]

        return {
            "configured": has_client,
            "api_key_hint": f"***{api_key_tail}" if api_key_tail else "",
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

    @staticmethod
    def _parse_price(price: Any) -> Optional[float]:
        """Normalize API price values to float."""
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            try:
                return float(
                    price.strip()
                    .replace("$", "")
                    .replace("€", "")
                    .replace(",", "")
                )
            except ValueError:
                return None
        return None

    @staticmethod
    def _serialize_datetime(value: Any) -> Optional[str]:
        """Serialize datetime values for JSON persistence."""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _deserialize_datetime(value: Any) -> Optional[datetime]:
        """Deserialize ISO datetime strings from persisted state."""
        if isinstance(value, datetime):
            return value
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _serialize_domain_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize owned domain record into JSON-safe shape."""
        return {
            "domain": record.get("domain"),
            "price": record.get("price"),
            "purchased_at": self._serialize_datetime(record.get("purchased_at")),
            "expires_at": self._serialize_datetime(record.get("expires_at")),
        }

    def _deserialize_domain_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Deserialize owned domain record from persisted config."""
        if not isinstance(record, dict):
            return None

        domain = record.get("domain")
        if not isinstance(domain, str) or not domain.strip():
            return None

        parsed_price = self._parse_price(record.get("price"))
        purchased_at = self._deserialize_datetime(record.get("purchased_at")) or datetime.now()
        expires_at = self._deserialize_datetime(record.get("expires_at")) or (purchased_at + timedelta(days=365))

        return {
            "domain": domain,
            "price": parsed_price if parsed_price is not None else 0.0,
            "purchased_at": purchased_at,
            "expires_at": expires_at,
        }
    
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

    def export_state(self) -> Dict[str, Any]:
        """Export manager state in a JSON-serializable format."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "owned_domains": [self._serialize_domain_record(record) for record in self.owned_domains],
        }

    def import_state(self, state: Dict[str, Any]) -> None:
        """Restore manager state from persisted JSON data."""
        if not isinstance(state, dict):
            return

        monthly_budget = state.get("monthly_budget")
        if monthly_budget is not None:
            parsed_budget = self._parse_price(monthly_budget)
            if parsed_budget is not None and parsed_budget > 0:
                self.monthly_budget = parsed_budget

        current_spending = state.get("current_spending")
        if current_spending is not None:
            parsed_spending = self._parse_price(current_spending)
            if parsed_spending is not None and parsed_spending >= 0:
                self.current_spending = parsed_spending

        records: List[Dict[str, Any]] = []
        for record in state.get("owned_domains", []):
            parsed_record = self._deserialize_domain_record(record)
            if parsed_record:
                records.append(parsed_record)
        self.owned_domains = records

        active_domain = state.get("active_domain")
        self.active_domain = active_domain if isinstance(active_domain, str) else None
        if self.active_domain and not any(d.get("domain") == self.active_domain for d in self.owned_domains):
            self.active_domain = None

    def cleanup_expired_domains(self, now: Optional[datetime] = None) -> int:
        """Remove expired domains from local state."""
        reference_time = now or datetime.now()
        kept: List[Dict[str, Any]] = []
        removed = 0

        for record in self.owned_domains:
            expires_at = record.get("expires_at")
            if isinstance(expires_at, datetime) and expires_at <= reference_time:
                removed += 1
                continue
            kept.append(record)

        self.owned_domains = kept
        if self.active_domain and not any(d.get("domain") == self.active_domain for d in self.owned_domains):
            self.active_domain = self.owned_domains[-1]["domain"] if self.owned_domains else None

        return removed

# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
