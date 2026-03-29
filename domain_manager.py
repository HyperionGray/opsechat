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


def _parse_price(value: Any) -> Optional[float]:
    """Parse registrar price values into float USD amount."""
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        normalized = (
            value.strip()
            .replace("$", "")
            .replace("€", "")
            .replace(",", "")
        )
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None

    return None


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        raise NotImplementedError("Domain availability lookup is not implemented")
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("Domain purchase is not implemented")
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError("Domain pricing lookup is not implemented")


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

    def plan_rotation(self, max_price: Optional[float] = None) -> Optional[Dict]:
        """
        Find a purchasable domain candidate without purchasing it.

        Returns:
            Optional[Dict]: Domain info with name/price/tld if found, else None.
        """
        remaining_budget = self.monthly_budget - self.current_spending
        if remaining_budget <= 0:
            return None

        price_cap = min(5.0, remaining_budget)
        if max_price is not None:
            try:
                requested_cap = float(max_price)
                if requested_cap > 0:
                    price_cap = min(price_cap, requested_cap)
            except (TypeError, ValueError):
                pass

        return self.find_cheap_available_domain(max_price=price_cap)

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> bool:
        """
        Configure the manager with a Porkbun API client and budget.

        Returns:
            bool: True when configuration is valid and applied.
        """
        if not api_key or not secret_key:
            raise ValueError("Both api_key and secret_key are required")

        try:
            budget = float(monthly_budget)
        except (TypeError, ValueError) as exc:
            raise ValueError("monthly_budget must be a number") from exc

        if budget <= 0:
            raise ValueError("monthly_budget must be greater than 0")

        self.monthly_budget = budget
        self.set_api_client(PorkbunAPIClient(api_key, secret_key))
        return True

    def get_config(self) -> Dict:
        """Return current domain rotation configuration and status."""
        provider = None
        api_key_masked = None

        if self.api_client:
            cls_name = self.api_client.__class__.__name__
            provider = cls_name.replace("APIClient", "").lower()
            raw_api_key = getattr(self.api_client, "api_key", "")
            if raw_api_key:
                api_key_masked = f"{raw_api_key[:4]}...{raw_api_key[-4:]}" if len(raw_api_key) >= 8 else "***"

        return {
            "has_api_client": self.api_client is not None,
            "provider": provider,
            "api_key_masked": api_key_masked,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def export_state(self) -> Dict:
        """Export manager state as JSON-serializable data."""
        serialized_domains = []
        for domain in self.owned_domains:
            entry = dict(domain)
            for field in ("purchased_at", "expires_at"):
                if isinstance(entry.get(field), datetime):
                    entry[field] = entry[field].isoformat()
            serialized_domains.append(entry)

        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
        }

    def load_state(self, state: Optional[Dict]):
        """Load manager state from persisted dictionary data."""
        if not state:
            return

        budget = state.get("monthly_budget")
        if isinstance(budget, (int, float)) and budget > 0:
            self.monthly_budget = float(budget)

        spending = state.get("current_spending")
        if isinstance(spending, (int, float)) and spending >= 0:
            self.current_spending = float(spending)

        loaded_domains: List[Dict] = []
        for raw_domain in state.get("owned_domains", []):
            if not isinstance(raw_domain, dict):
                continue

            entry = dict(raw_domain)
            for field in ("purchased_at", "expires_at"):
                value = entry.get(field)
                if isinstance(value, str):
                    try:
                        entry[field] = datetime.fromisoformat(value)
                    except ValueError:
                        # Keep original string if formatting is unknown.
                        pass
            loaded_domains.append(entry)

        self.owned_domains = loaded_domains

        active_domain = state.get("active_domain")
        self.active_domain = active_domain if isinstance(active_domain, str) else None
    
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
                price = _parse_price(result.get("price"))
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
            purchased_at = datetime.now()
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "purchased_at": purchased_at,
                "expires_at": purchased_at + timedelta(days=365)
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
        if self.monthly_budget - self.current_spending <= 0:
            if return_details:
                return {
                    "success": False,
                    "error": "Monthly budget exhausted"
                }
            return None

        # Find cheap domain
        domain_info = self.plan_rotation()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            if return_details:
                return {
                    "success": False,
                    "error": "Could not find available cheap domain"
                }
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
                    "remaining_budget": self.monthly_budget - self.current_spending
                }
            return self.active_domain
        
        if return_details:
            return {
                "success": False,
                "error": "Purchase failed",
                "domain": domain_info["domain"]
            }
        return None
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return [dict(d) for d in self.owned_domains]
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
