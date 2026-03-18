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
        self.api_provider = "porkbun" if isinstance(api_client, PorkbunAPIClient) else None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.last_budget_reset_month = self._current_month_key()
        self._api_key: Optional[str] = None
        self._secret_key: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.api_provider = "porkbun" if isinstance(api_client, PorkbunAPIClient) else "custom"

    @staticmethod
    def _current_month_key() -> str:
        """Return current month key for budget tracking (UTC)."""
        return datetime.utcnow().strftime("%Y-%m")

    @staticmethod
    def _mask_secret(value: Optional[str]) -> Optional[str]:
        """Mask secrets for safe display in UI responses."""
        if not value:
            return None
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * (len(value) - 4)}{value[-4:]}"

    def _reset_budget_if_new_month(self):
        """Reset spending when the calendar month changes."""
        current_month = self._current_month_key()
        if self.last_budget_reset_month != current_month:
            logger.info(
                "Resetting domain budget spending from %s to %s",
                self.last_budget_reset_month,
                current_month,
            )
            self.current_spending = 0.0
            self.last_budget_reset_month = current_month

    @staticmethod
    def _parse_price(value: Any) -> Optional[float]:
        """Parse registrar price values that may include currency symbols."""
        if value is None:
            return None
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
                return None
        return None

    @staticmethod
    def _serialize_domain_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert datetime values to ISO strings for JSON storage."""
        serialized = dict(record)
        for field in ("purchased_at", "expires_at"):
            value = serialized.get(field)
            if isinstance(value, datetime):
                serialized[field] = value.isoformat()
        return serialized

    @staticmethod
    def _deserialize_domain_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Parse stored ISO datetime values back into datetime objects."""
        parsed = dict(record)
        for field in ("purchased_at", "expires_at"):
            value = parsed.get(field)
            if isinstance(value, str):
                try:
                    parsed[field] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep original value if format is unknown/corrupt.
                    pass
        return parsed

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 10.0,
        provider: str = "porkbun",
    ) -> Dict[str, Any]:
        """
        Configure domain rotation API and budget.
        Returns a UI-safe configuration summary.
        """
        provider_normalized = provider.lower().strip()
        if provider_normalized != "porkbun":
            raise ValueError(f"Unsupported domain provider: {provider}")

        self.api_client = PorkbunAPIClient(api_key, secret_key)
        self.api_provider = provider_normalized
        self._api_key = api_key
        self._secret_key = secret_key
        self.monthly_budget = float(monthly_budget)
        self._reset_budget_if_new_month()
        return self.get_config()

    def get_config(self, include_secrets: bool = False) -> Dict[str, Any]:
        """
        Return current manager configuration.
        Secrets are masked unless include_secrets=True.
        """
        config = {
            "provider": self.api_provider,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "last_budget_reset_month": self.last_budget_reset_month,
            "has_api_client": self.api_client is not None,
            "api_key": self._api_key if include_secrets else self._mask_secret(self._api_key),
            "secret_key": self._secret_key if include_secrets else self._mask_secret(self._secret_key),
        }
        return config

    def export_state(self) -> Dict[str, Any]:
        """Export JSON-safe manager state."""
        return {
            "current_spending": self.current_spending,
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            "last_budget_reset_month": self.last_budget_reset_month,
            "api_provider": self.api_provider,
            "owned_domains": [
                self._serialize_domain_record(domain)
                for domain in self.owned_domains
            ],
        }

    def import_state(self, state: Dict[str, Any]):
        """Import manager state previously created by export_state()."""
        if not state:
            return

        self.current_spending = float(state.get("current_spending", self.current_spending))
        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))
        self.active_domain = state.get("active_domain", self.active_domain)
        self.last_budget_reset_month = state.get(
            "last_budget_reset_month",
            self.last_budget_reset_month,
        )
        self.api_provider = state.get("api_provider", self.api_provider)

        owned_domains = state.get("owned_domains", [])
        if isinstance(owned_domains, list):
            self.owned_domains = [
                self._deserialize_domain_record(domain)
                for domain in owned_domains
                if isinstance(domain, dict)
            ]
    
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
                price = self._parse_price(result.get("price", 999))
                if price is None:
                    logger.warning("Could not parse price for domain %s", domain)
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
        
        self._reset_budget_if_new_month()

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
        self._reset_budget_if_new_month()
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "budget_month": self.last_budget_reset_month,
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
