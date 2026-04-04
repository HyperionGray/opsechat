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
    
    DEFAULT_CHEAP_TLDS = ["xyz", "club", "online", "site", "website"]

    class BudgetManager:
        """Small helper to preserve the historical budget_manager API."""

        def __init__(self, manager: "DomainRotationManager"):
            self._manager = manager

        @property
        def monthly_budget(self) -> float:
            return self._manager.monthly_budget

        def set_monthly_budget(self, amount: float):
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError("monthly budget must be greater than 0")
            self._manager.monthly_budget = amount_float

        def get_month_spending(self) -> float:
            return self._manager.current_spending

        def get_remaining_budget(self) -> float:
            return max(0.0, self._manager.monthly_budget - self._manager.current_spending)

    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.monthly_budget = float(monthly_budget)
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False
        self.budget_manager = self.BudgetManager(self)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    @staticmethod
    def _coerce_price(value: Any, default: Optional[float] = None) -> Optional[float]:
        """Parse a domain price from API values like '$1.99'."""
        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            cleaned = (
                value.strip()
                .replace("$", "")
                .replace("€", "")
                .replace(",", "")
            )
            try:
                return float(cleaned)
            except ValueError:
                return default

        return default

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.now()

    @staticmethod
    def _serialize_datetime(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return datetime.now().isoformat()
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    # Compatibility alias used in docs and older code.
    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        return self.generate_random_domain(tld=tld, length=length)

    def set_test_mode(self, enabled: bool):
        """Enable/disable test mode where purchases are simulated."""
        self.test_mode = bool(enabled)

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        monthly_budget: Optional[float] = None
    ) -> Dict:
        """
        Configure Porkbun credentials and optional budget.
        Accepts secret_key/api_secret for backwards compatibility.
        """
        secret = api_secret or secret_key
        if not api_key or not secret:
            raise ValueError("Both api_key and secret key are required")

        self.set_api_client(PorkbunAPIClient(api_key, secret))
        if monthly_budget is not None:
            self.budget_manager.set_monthly_budget(monthly_budget)

        return self.get_config()

    def get_config(self) -> Dict:
        """Return non-sensitive domain rotation configuration details."""
        configured = self.api_client is not None
        api_key_last4 = None
        if configured and getattr(self.api_client, "api_key", None):
            api_key_last4 = self.api_client.api_key[-4:]

        return {
            "configured": configured,
            "provider": self.api_client.__class__.__name__ if configured else None,
            "api_key_last4": api_key_last4,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": max(0.0, self.monthly_budget - self.current_spending),
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode
        }

    def export_state(self) -> Dict:
        """Export JSON-safe runtime state for CLI persistence."""
        return {
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "owned_domains": [
                {
                    "domain": entry.get("domain"),
                    "price": float(entry.get("price", 0.0)),
                    "purchased_at": self._serialize_datetime(entry.get("purchased_at")),
                    "expires_at": self._serialize_datetime(entry.get("expires_at"))
                }
                for entry in self.owned_domains
                if entry.get("domain")
            ]
        }

    def load_state(
        self,
        owned_domains: Optional[List[Dict]] = None,
        current_spending: Optional[float] = None,
        active_domain: Optional[str] = None
    ):
        """Load persisted runtime state and normalize date types."""
        if current_spending is not None:
            self.current_spending = float(current_spending)

        if active_domain is not None:
            self.active_domain = active_domain

        normalized_domains: List[Dict] = []
        for entry in owned_domains or []:
            domain = entry.get("domain")
            if not domain:
                continue
            price = self._coerce_price(entry.get("price"), default=0.0)
            normalized_domains.append({
                "domain": domain,
                "price": price if price is not None else 0.0,
                "purchased_at": self._parse_datetime(entry.get("purchased_at")),
                "expires_at": self._parse_datetime(entry.get("expires_at"))
            })

        self.owned_domains = normalized_domains

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search and return multiple available domains under max_price.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return []

        search_tlds = tlds or list(self.DEFAULT_CHEAP_TLDS)
        available: List[Dict] = []
        seen_domains = set()
        attempts = max(limit * 2, 10)

        for _ in range(attempts):
            if len(available) >= limit:
                break

            tld = random.choice(search_tlds)
            domain = self.generate_random_domain(tld=tld)
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            result = self.api_client.search_domain(domain)
            if not result.get("available"):
                continue

            price = self._coerce_price(result.get("price"), default=max_price + 1)
            if price is None or price > max_price:
                continue

            available.append({
                "domain": domain,
                "price": price,
                "tld": tld,
                "currency": result.get("currency", "USD")
            })

        return sorted(available, key=lambda d: d["price"])
    
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
        cheap_tlds = list(self.DEFAULT_CHEAP_TLDS)
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = self._coerce_price(result.get("price"), default=999.0)

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
        parsed_price = self._coerce_price(price)
        if parsed_price is None:
            logger.error("Invalid price value: %r", price)
            return False

        if not self.api_client and not self.test_mode:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${parsed_price}, Budget: ${self.monthly_budget}")
            return False

        # Attempt purchase (or simulate in test mode)
        if self.test_mode:
            result = {"success": True, "message": "Simulated purchase (test mode)"}
        else:
            result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += parsed_price
            self.owned_domains.append({
                "domain": domain,
                "price": parsed_price,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${parsed_price}")
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

    def rotate_to_new_domain(self) -> Dict:
        """Structured rotate response for UI/API callers."""
        previous_domain = self.active_domain
        new_domain = self.rotate_domain()

        if not new_domain:
            return {
                "success": False,
                "error": "Could not rotate domain",
                "active_domain": previous_domain
            }

        purchase_record = next(
            (d for d in reversed(self.owned_domains) if d.get("domain") == new_domain),
            {}
        )
        return {
            "success": True,
            "domain": new_domain,
            "previous_domain": previous_domain,
            "cost": purchase_record.get("price"),
            "budget_status": self.get_budget_status()
        }
    
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
            "remaining": max(0.0, self.monthly_budget - self.current_spending),
            "domains_owned": len(self.owned_domains)
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
