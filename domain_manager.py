"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
from abc import ABC, abstractmethod
import requests
import random
import string
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _normalize_price(value: Any) -> Optional[float]:
    """Convert registrar price values to float when possible."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace("€", "").replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def _isoformat_utc(dt: datetime) -> str:
    """Return an ISO8601 timestamp with explicit UTC suffix."""
    return dt.replace(microsecond=0).isoformat() + "Z"


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        # Backward-compat alias used by older scripts/tests.
        self.secret_key = api_secret
    
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
        price = _normalize_price(result.get("price"))
        available = result.get("status") == "SUCCESS" and str(
            result.get("isAvailable", False)
        ).lower() in {"true", "1", "yes"}
        
        return {
            "domain": domain,
            "available": available,
            "price": price if price is not None else result.get("price"),
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
        self.monthly_budget = float(monthly_budget)
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.spending_period = self._get_current_period()
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def set_monthly_budget(self, amount: float):
        """Update monthly budget with basic validation."""
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Monthly budget must be greater than 0")
        self.monthly_budget = amount

    # Backward-compatible alias used by older scripts.
    def generate_domain_name(self, tld: str = "xyz", length: int = 8) -> str:
        """Generate domain name alias for older callers."""
        return self.generate_random_domain(tld=tld, length=length)

    def configure(
        self,
        api_key: str = "",
        secret_key: str = "",
        monthly_budget: Optional[float] = None,
    ) -> Dict:
        """Configure API credentials and budget for web/CLI callers."""
        if monthly_budget is not None:
            self.set_monthly_budget(monthly_budget)

        if api_key and secret_key:
            self.set_api_client(PorkbunAPIClient(api_key=api_key, api_secret=secret_key))

        return self.get_config()

    def get_config(self) -> Dict:
        """Return lightweight non-secret configuration for templates/routes."""
        return {
            "configured": self.api_client is not None,
            "has_api_client": self.api_client is not None,
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            "budget_status": self.get_budget_status(),
        }

    def _get_current_period(self) -> str:
        """Get current spending period in YYYY-MM format."""
        return datetime.utcnow().strftime("%Y-%m")

    def _sync_budget_period(self):
        """Reset monthly spending when moving into a new month."""
        current = self._get_current_period()
        if self.spending_period != current:
            logger.info(
                "New month detected. Resetting domain budget spending (%s -> %s).",
                self.spending_period,
                current,
            )
            self.current_spending = 0.0
            self.spending_period = current
    
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
        
        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = _normalize_price(result.get("price"))
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

        self._sync_budget_period()
        normalized_price = _normalize_price(price)
        if normalized_price is None:
            logger.error("Invalid price received for domain %s: %s", domain, price)
            return False
        
        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            now = datetime.utcnow()
            self.current_spending += normalized_price
            self.owned_domains.append({
                "domain": domain,
                "price": normalized_price,
                "purchased_at": _isoformat_utc(now),
                "expires_at": _isoformat_utc(now + timedelta(days=365))
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
        budget_status = self.get_budget_status()
        if budget_status["remaining"] <= 0:
            logger.warning("Cannot rotate domain: no budget remaining this month.")
            return None

        domain_info = self.find_cheap_available_domain(max_price=min(5.0, budget_status["remaining"]))
        
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

    def rotate_domain_with_result(self) -> Dict:
        """Rotate domain and return detailed result payload."""
        budget_status = self.get_budget_status()
        if budget_status["remaining"] <= 0:
            return {
                "success": False,
                "error": "No budget remaining for current month",
                "budget_status": budget_status,
            }

        domain_info = self.find_cheap_available_domain(
            max_price=min(5.0, budget_status["remaining"])
        )
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain",
                "budget_status": budget_status,
            }

        if not self.purchase_domain_if_budget_allows(
            domain_info["domain"], domain_info["price"]
        ):
            return {
                "success": False,
                "error": "Domain purchase failed or exceeded budget",
                "candidate_domain": domain_info["domain"],
                "budget_status": self.get_budget_status(),
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": domain_info["domain"],
            "price": domain_info["price"],
            "budget_status": self.get_budget_status(),
        }
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return self.owned_domains
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        self._sync_budget_period()
        remaining = max(0.0, self.monthly_budget - self.current_spending)
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": remaining,
            "domains_owned": len(self.owned_domains),
            "spending_period": self.spending_period,
        }

    def export_state(self) -> Dict:
        """Export a JSON-safe snapshot of manager state."""
        return {
            "current_spending": self.current_spending,
            "monthly_budget": self.monthly_budget,
            "owned_domains": [self._normalize_domain_record(d) for d in self.owned_domains],
            "active_domain": self.active_domain,
            "spending_period": self.spending_period,
        }

    def load_state(self, state: Optional[Dict]):
        """Load persisted JSON-safe state."""
        if not state:
            return

        monthly_budget = state.get("monthly_budget")
        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        spending = state.get("current_spending")
        if spending is not None:
            self.current_spending = float(spending)

        self.active_domain = state.get("active_domain") or None

        loaded_domains = state.get("owned_domains") or []
        self.owned_domains = [self._normalize_domain_record(d) for d in loaded_domains]

        self.spending_period = state.get("spending_period") or self._get_current_period()
        self._sync_budget_period()

    def _normalize_domain_record(self, domain_record: Dict) -> Dict:
        """Normalize domain records so timestamps are always JSON-safe strings."""
        normalized = dict(domain_record)

        for key in ("purchased_at", "expires_at"):
            value = normalized.get(key)
            if isinstance(value, datetime):
                normalized[key] = _isoformat_utc(value)
            elif value is None:
                normalized[key] = ""
            else:
                normalized[key] = str(value)

        if "price" in normalized:
            price = _normalize_price(normalized.get("price"))
            if price is not None:
                normalized["price"] = price

        return normalized


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
