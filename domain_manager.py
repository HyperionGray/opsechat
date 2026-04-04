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


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        # Backward-compatibility alias used by some legacy checks/docs.
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
        if api_client:
            self._api_key = getattr(api_client, "api_key", None)
            self._api_secret = getattr(api_client, "api_secret", None)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self._api_key = getattr(api_client, "api_key", None)
        self._api_secret = getattr(api_client, "api_secret", None)

    def set_monthly_budget(self, amount: float):
        """Update monthly budget limit"""
        if amount <= 0:
            raise ValueError("Monthly budget must be greater than zero")
        self.monthly_budget = float(amount)

    @property
    def budget_manager(self):
        """Compatibility shim for older docs/examples."""
        return self

    def get_month_spending(self) -> float:
        """Compatibility accessor for current monthly spending."""
        return self.current_spending

    def get_remaining_budget(self) -> float:
        """Compatibility accessor for remaining monthly budget."""
        return self.monthly_budget - self.current_spending

    def _parse_price(self, price: Any) -> Optional[float]:
        """Parse registrar price values into float USD values"""
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            stripped = (
                price.replace("$", "")
                .replace("€", "")
                .replace(",", "")
                .strip()
            )
            try:
                return float(stripped)
            except ValueError:
                logger.warning("Could not parse domain price value: %s", price)
                return None
        return None

    def _normalize_domain_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize persisted domain records back into runtime types"""
        normalized = dict(record)
        for dt_field in ("purchased_at", "expires_at"):
            value = normalized.get(dt_field)
            if isinstance(value, str):
                try:
                    normalized[dt_field] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep original string if it's not ISO format.
                    pass
        return normalized

    def _serialize_domain_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize runtime records into JSON-safe dictionaries"""
        serialized = dict(record)
        for dt_field in ("purchased_at", "expires_at"):
            value = serialized.get(dt_field)
            if isinstance(value, datetime):
                serialized[dt_field] = value.isoformat()
        return serialized

    def _mask_secret(self, value: Optional[str]) -> str:
        """Return masked values suitable for UI rendering"""
        if not value:
            return ""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * (len(value) - 4)}{value[-4:]}"
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def generate_domain_name(self, tld: str = "xyz", length: int = 8) -> str:
        """Backward-compatible alias for random domain generation"""
        return self.generate_random_domain(tld=tld, length=length)

    def check_availability(self, domain: str) -> Dict[str, Any]:
        """Check if a specific domain is available for registration"""
        if not self.api_client:
            return {"domain": domain, "available": False, "error": "No API client configured"}

        result = self.api_client.search_domain(domain)
        parsed_price = self._parse_price(result.get("price"))
        if parsed_price is not None:
            result["price"] = parsed_price
        return result
    
    def find_cheap_available_domain(self, max_price: float = 5.0, 
                                   max_attempts: int = 10,
                                   tlds: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                parsed_price = self._parse_price(result.get("price"))
                if parsed_price is None:
                    continue

                if parsed_price <= max_price:
                    return {
                        "domain": domain,
                        "price": parsed_price,
                        "tld": tld
                    }
        
        return None

    def search_cheap_domains(self, tlds: Optional[List[str]] = None,
                            max_price: float = 5.0, limit: int = 5) -> List[Dict[str, Any]]:
        """Search multiple cheap domains without purchasing them"""
        domains: List[Dict[str, Any]] = []
        seen = set()
        attempts = max(limit * 3, limit)

        for _ in range(attempts):
            if len(domains) >= limit:
                break

            candidate = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=tlds,
            )
            if not candidate:
                continue

            if candidate["domain"] in seen:
                continue

            seen.add(candidate["domain"])
            domains.append(candidate)

        return domains
    
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

    def rotate_to_new_domain(self) -> Dict[str, Any]:
        """Compatibility wrapper returning structured rotate results"""
        new_domain = self.rotate_domain()
        if not new_domain:
            return {"success": False, "error": "No domain could be rotated into service"}

        purchased = next(
            (d for d in reversed(self.owned_domains) if d.get("domain") == new_domain),
            {},
        )
        return {
            "success": True,
            "domain": new_domain,
            "cost": purchased.get("price"),
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
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }

    def configure(self, api_key: str, secret_key: Optional[str] = None,
                  api_secret: Optional[str] = None,
                  monthly_budget: Optional[float] = None) -> bool:
        """Configure registrar credentials and optional budget"""
        selected_secret = api_secret or secret_key
        if not api_key or not selected_secret:
            logger.error("Domain API key/secret were not provided")
            return False

        try:
            self.set_api_client(PorkbunAPIClient(api_key, selected_secret))
            if monthly_budget is not None:
                self.set_monthly_budget(float(monthly_budget))
            return True
        except Exception as exc:
            logger.error("Failed to configure domain rotation manager: %s", exc)
            return False

    def get_config(self) -> Dict[str, Any]:
        """Return safe-to-display domain manager configuration details"""
        return {
            "api_key_configured": bool(self._api_key),
            "secret_key_configured": bool(self._api_secret),
            "api_key_masked": self._mask_secret(self._api_key),
            "secret_key_masked": self._mask_secret(self._api_secret),
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
        }

    def load_state(self, state: Dict[str, Any]):
        """Load persisted manager state from a dictionary"""
        if "monthly_budget" in state:
            self.monthly_budget = float(state["monthly_budget"])
        if "current_spending" in state:
            self.current_spending = float(state["current_spending"])
        if "owned_domains" in state and isinstance(state["owned_domains"], list):
            self.owned_domains = [
                self._normalize_domain_record(domain)
                for domain in state["owned_domains"]
                if isinstance(domain, dict)
            ]
        if "active_domain" in state:
            self.active_domain = state["active_domain"]

    def export_state(self) -> Dict[str, Any]:
        """Export manager state into JSON-serializable data"""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": [
                self._serialize_domain_record(domain)
                for domain in self.owned_domains
            ],
            "active_domain": self.active_domain,
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
