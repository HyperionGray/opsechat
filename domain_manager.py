"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

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
        self.spending_period_start: datetime = self._start_of_month(self._now())

    def _now(self) -> datetime:
        """Get current UTC time (isolated for testability)."""
        return datetime.now(timezone.utc)

    @staticmethod
    def _start_of_month(ts: datetime) -> datetime:
        """Normalize datetime to month boundary in UTC."""
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _parse_datetime(value) -> Optional[datetime]:
        """Parse ISO datetime or return None for invalid values."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _normalize_price(price) -> Optional[float]:
        """Convert price variants (number or currency string) to float."""
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            cleaned = (
                price.strip()
                .replace("$", "")
                .replace("€", "")
                .replace(",", "")
            )
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _ensure_budget_period_current(self):
        """Reset spending when a new calendar month starts."""
        now = self._now()
        current_period = self._start_of_month(now)
        if self._start_of_month(self.spending_period_start) < current_period:
            logger.info(
                "Starting new monthly budget period. "
                "Previous spending: $%.2f",
                self.current_spending,
            )
            self.current_spending = 0.0
            self.spending_period_start = current_period
    
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

    def set_monthly_budget(self, amount: float):
        """Update monthly budget limit."""
        if amount <= 0:
            raise ValueError("Monthly budget must be greater than zero")
        self.monthly_budget = float(amount)
    
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
                price = self._normalize_price(result.get("price", 999))
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

        normalized_price = self._normalize_price(price)
        if normalized_price is None or normalized_price <= 0:
            logger.error("Invalid domain price: %s", price)
            return False

        self._ensure_budget_period_current()
        
        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            now = self._now()
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
        return list(self.owned_domains)
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        self._ensure_budget_period_current()
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "period_start": self.spending_period_start.isoformat()
        }

    def serialize_state(self) -> Dict:
        """Serialize manager state for JSON persistence."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "spending_period_start": self.spending_period_start.isoformat(),
            "owned_domains": [
                {
                    "domain": d.get("domain"),
                    "price": self._normalize_price(d.get("price")) or 0.0,
                    "purchased_at": (
                        self._parse_datetime(d.get("purchased_at")) or self._now()
                    ).isoformat(),
                    "expires_at": (
                        self._parse_datetime(d.get("expires_at"))
                        or ((self._parse_datetime(d.get("purchased_at")) or self._now()) + timedelta(days=365))
                    ).isoformat(),
                }
                for d in self.owned_domains
                if d.get("domain")
            ],
        }

    def load_state(self, state: Optional[Dict]):
        """Load manager state from dict (supports legacy CLI state)."""
        if not isinstance(state, dict):
            return

        budget = state.get("monthly_budget")
        if budget is not None:
            parsed_budget = self._normalize_price(budget)
            if parsed_budget and parsed_budget > 0:
                self.monthly_budget = parsed_budget

        parsed_spending = self._normalize_price(state.get("current_spending"))
        if parsed_spending is not None and parsed_spending >= 0:
            self.current_spending = parsed_spending

        active_domain = state.get("active_domain")
        if isinstance(active_domain, str) and active_domain:
            self.active_domain = active_domain

        parsed_period_start = self._parse_datetime(state.get("spending_period_start"))
        self.spending_period_start = parsed_period_start or self._start_of_month(self._now())

        loaded_domains: List[Dict] = []
        for entry in state.get("owned_domains", []):
            if not isinstance(entry, dict):
                continue
            domain = entry.get("domain")
            if not domain:
                continue

            purchased_at = self._parse_datetime(entry.get("purchased_at")) or self._now()
            expires_at = self._parse_datetime(entry.get("expires_at")) or (
                purchased_at + timedelta(days=365)
            )
            price = self._normalize_price(entry.get("price")) or 0.0

            loaded_domains.append(
                {
                    "domain": domain,
                    "price": price,
                    "purchased_at": purchased_at,
                    "expires_at": expires_at,
                }
            )

        self.owned_domains = loaded_domains
        self._ensure_budget_period_current()


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
