"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import logging
import random
import re
import string
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    @abstractmethod
    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search if domain is available"""
        ...
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase domain"""
        ...
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing for TLD"""
        ...


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
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
    
    def configure(
        self,
        api_key: str,
        api_secret: Optional[str] = None,
        secret_key: Optional[str] = None,
        monthly_budget: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Configure manager with Porkbun credentials and budget.
        Supports both `api_secret` and `secret_key` naming.
        """
        resolved_secret = api_secret or secret_key
        if not api_key or not resolved_secret:
            raise ValueError("Both api_key and api_secret/secret_key are required")
        
        if monthly_budget is not None:
            monthly_budget = float(monthly_budget)
            if monthly_budget <= 0:
                raise ValueError("monthly_budget must be greater than zero")
            self.monthly_budget = monthly_budget
        
        self._api_key = api_key
        self._api_secret = resolved_secret
        self.api_client = PorkbunAPIClient(api_key, resolved_secret)
        return self.get_config()
    
    def get_config(self, include_secrets: bool = False) -> Dict[str, Any]:
        """Return current domain-rotation configuration summary."""
        config: Dict[str, Any] = {
            "configured": self.api_client is not None,
            "api_key_configured": bool(self._api_key),
            "api_secret_configured": bool(self._api_secret),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }
        
        if include_secrets:
            config["api_key"] = self._api_key
            config["api_secret"] = self._api_secret
        
        return config
    
    @staticmethod
    def _parse_price(price: Any) -> Optional[float]:
        """Parse registrar price values into a float."""
        if isinstance(price, (int, float)):
            return float(price)
        
        if isinstance(price, str):
            stripped = price.strip()
            if not stripped:
                return None
            normalized = stripped.replace(",", "")
            # Keep only digits and decimal separators (e.g. "$2.99 USD" -> "2.99")
            normalized = re.sub(r"[^0-9.]", "", normalized)
            if normalized.count(".") > 1:
                return None
            try:
                return float(normalized)
            except ValueError:
                return None
        
        return None
    
    @staticmethod
    def _serialize_domain(domain_record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert datetime fields to ISO 8601 strings for persistence."""
        serialized = dict(domain_record)
        for key in ("purchased_at", "expires_at"):
            value = serialized.get(key)
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
        return serialized
    
    @staticmethod
    def _deserialize_domain(domain_record: Dict[str, Any]) -> Dict[str, Any]:
        """Parse persisted datetime strings back to datetime objects."""
        restored = dict(domain_record)
        for key in ("purchased_at", "expires_at"):
            value = restored.get(key)
            if isinstance(value, str):
                try:
                    restored[key] = datetime.fromisoformat(value)
                except ValueError:
                    logger.warning("Invalid datetime in stored domain state: %s=%s", key, value)
        return restored
    
    def export_state(self) -> Dict[str, Any]:
        """Export JSON-safe state for persistence."""
        return {
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "owned_domains": [self._serialize_domain(d) for d in self.owned_domains],
        }
    
    def load_state(self, state: Dict[str, Any]):
        """Load persisted state from a dictionary."""
        self.current_spending = float(state.get("current_spending", 0.0) or 0.0)
        self.active_domain = state.get("active_domain")
        raw_domains = state.get("owned_domains", []) or []
        if not isinstance(raw_domains, list):
            raw_domains = []
        self.owned_domains = [
            self._deserialize_domain(d)
            for d in raw_domains
            if isinstance(d, dict) and d.get("domain")
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
                price = self._parse_price(result.get("price"))
                if price is None:
                    logger.warning("Skipping domain with unparseable price: %s", result.get("price"))
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
        
        parsed_price = self._parse_price(price)
        if parsed_price is None or parsed_price <= 0:
            logger.error("Invalid purchase price for domain %s: %s", domain, price)
            return False
        
        # Check budget
        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${parsed_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
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


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
