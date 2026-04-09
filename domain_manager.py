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
        raise NotImplementedError("Subclasses must implement search_domain()")
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("Subclasses must implement purchase_domain()")
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError("Subclasses must implement get_pricing()")


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
        # API credentials stored internally only - not exposed via get_config()
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> bool:
        """Configure registrar credentials and budget."""
        self._api_key = api_key.strip() or None
        self._api_secret = secret_key.strip() or None
        self.monthly_budget = float(monthly_budget)

        if not self._api_key or not self._api_secret:
            self.api_client = None
            return False

        self.api_client = PorkbunAPIClient(self._api_key, self._api_secret)
        return True

    def get_config(self) -> Dict:
        """Return safe configuration details for UI/API use."""
        return {
            "configured": self.api_client is not None,
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            # API key presence intentionally omitted for security
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
    def _normalize_price(price: Any) -> Optional[float]:
        """Convert registrar price values into a float, if possible."""
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            cleaned = price.strip().replace("$", "").replace("€", "").replace(",", "")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None
    
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
                        "tld": tld,
                        "currency": result.get("currency", "USD"),
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> Dict:
        """
        Purchase domain if within budget
        Returns structured result
        """
        if not self.api_client:
            logger.error("No API client configured")
            return {
                "success": False,
                "domain": domain,
                "message": "No API client configured",
            }
        
        parsed_price = self._normalize_price(price)
        if parsed_price is None:
            return {
                "success": False,
                "domain": domain,
                "message": "Invalid domain price",
                "budget_status": self.get_budget_status(),
            }

        # Check budget
        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${parsed_price}, Budget: ${self.monthly_budget}")
            return {
                "success": False,
                "domain": domain,
                "message": "Budget exceeded",
                "budget_status": self.get_budget_status(),
            }
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            purchased_at = datetime.now()
            self.current_spending += parsed_price
            self.owned_domains.append({
                "domain": domain,
                "price": parsed_price,
                "purchased_at": purchased_at,
                "expires_at": purchased_at + timedelta(days=365),
                "order_id": result.get("order_id"),
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return {
                "success": True,
                "domain": domain,
                "price": parsed_price,
                "message": "Domain purchased successfully",
                "active_domain": self.active_domain,
                "budget_status": self.get_budget_status(),
                "order_id": result.get("order_id"),
            }
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Failed to purchase domain"),
                "budget_status": self.get_budget_status(),
            }
    
    def rotate_domain(self) -> Dict:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {
                "success": False,
                "message": "Could not find available cheap domain",
                "budget_status": self.get_budget_status(),
            }
        
        # Purchase domain
        result = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )
        
        if result.get("success"):
            self.active_domain = domain_info["domain"]
            result["active_domain"] = self.active_domain

        return result
    
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

    def export_state(self) -> Dict:
        """
        Export manager state into JSON-safe primitives.
        Useful for CLI persistence between runs.
        """
        owned_domains: List[Dict] = []
        for entry in self.owned_domains:
            if not isinstance(entry, dict):
                continue
            normalized = dict(entry)
            for field in ("purchased_at", "expires_at"):
                value = normalized.get(field)
                if isinstance(value, datetime):
                    normalized[field] = value.isoformat()
            owned_domains.append(normalized)

        return {
            "state_version": 1,
            "current_spending": self.current_spending,
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            "owned_domains": owned_domains,
        }

    def load_state(self, state: Optional[Dict]) -> None:
        """
        Load state from persisted data.
        Datetime fields are accepted as ISO strings.
        """
        if not state or not isinstance(state, dict):
            return

        monthly_budget = state.get("monthly_budget")
        if monthly_budget is not None:
            try:
                self.monthly_budget = float(monthly_budget)
            except (TypeError, ValueError):
                pass

        current_spending = state.get("current_spending")
        if current_spending is not None:
            try:
                self.current_spending = float(current_spending)
            except (TypeError, ValueError):
                self.current_spending = 0.0

        active_domain = state.get("active_domain")
        self.active_domain = active_domain if isinstance(active_domain, str) and active_domain else None

        owned_domains: List[Dict] = []
        for raw_entry in state.get("owned_domains", []):
            if not isinstance(raw_entry, dict):
                continue
            entry = dict(raw_entry)
            for field in ("purchased_at", "expires_at"):
                value = entry.get(field)
                if isinstance(value, str):
                    try:
                        entry[field] = datetime.fromisoformat(value)
                    except ValueError:
                        # Leave as-is if unparsable; consumers handle display fallback.
                        pass
            owned_domains.append(entry)
        self.owned_domains = owned_domains


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
