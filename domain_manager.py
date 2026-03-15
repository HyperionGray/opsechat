"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
from abc import ABC, abstractmethod
import re
import requests
import random
import string
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
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
        self._secret_key: Optional[str] = None
        self._provider = "custom"
        self._cheap_tlds = ["xyz", "club", "online", "site", "website"]
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self._provider = api_client.__class__.__name__.replace("APIClient", "").lower() or "custom"
        # Credentials may not be available for externally supplied clients
        self._api_key = None
        self._secret_key = None

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> None:
        """
        Configure the global rotation manager with Porkbun credentials.
        This method is used by the web configuration UI.
        """
        if not api_key or not secret_key:
            raise ValueError("API key and secret key are required")
        if monthly_budget <= 0:
            raise ValueError("Monthly budget must be greater than 0")

        self.api_client = PorkbunAPIClient(api_key, secret_key)
        self._api_key = api_key
        self._secret_key = secret_key
        self._provider = "porkbun"
        self.monthly_budget = monthly_budget

    def get_config(self) -> Dict[str, Any]:
        """Return a sanitized view of domain manager configuration."""
        return {
            "configured": self.api_client is not None,
            "provider": self._provider,
            "api_key_masked": self._mask_secret(self._api_key),
            "secret_key_configured": bool(self._secret_key),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    @staticmethod
    def _mask_secret(secret: Optional[str]) -> str:
        """Mask secrets to avoid leaking credential values to templates/logs."""
        if not secret:
            return ""
        if len(secret) <= 4:
            return "*" * len(secret)
        return f"{'*' * (len(secret) - 4)}{secret[-4:]}"

    @staticmethod
    def _parse_price(value: Union[str, int, float, None]) -> Optional[float]:
        """Best-effort conversion for registrar price formats."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            match = re.search(r"[-+]?\d*\.?\d+", cleaned)
            if not match:
                return None
            try:
                return float(match.group(0))
            except ValueError:
                return None
        return None
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"
    
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
        if max_attempts <= 0:
            return None
        
        # Try cheap TLDs
        cheap_tlds = tlds or self._cheap_tlds
        if not cheap_tlds:
            return None
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = self._parse_price(result.get("price"))
                if price is not None and price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "currency": result.get("currency", "USD"),
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: Union[float, str]) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False

        normalized_price = self._parse_price(price)
        if normalized_price is None:
            logger.error("Invalid price format for domain purchase: %s", price)
            return False
        
        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += normalized_price
            self.owned_domains.append({
                "domain": domain,
                "price": normalized_price,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${normalized_price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False

    def rotate_domain_with_result(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Rotate to a new domain and return a structured result payload
        suitable for JSON APIs and template messaging.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)

        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain",
                "active_domain": self.active_domain,
                "budget": self.get_budget_status(),
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"]
        )

        if not success:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded",
                "domain": domain_info["domain"],
                "price": domain_info["price"],
                "active_domain": self.active_domain,
                "budget": self.get_budget_status(),
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": domain_info["domain"],
            "price": domain_info["price"],
            "currency": domain_info.get("currency", "USD"),
            "active_domain": self.active_domain,
            "budget": self.get_budget_status(),
        }
    
    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        result = self.rotate_domain_with_result()
        if not result.get("success"):
            logger.error(result.get("error", "Domain rotation failed"))
            return None
        return result.get("domain")
    
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
