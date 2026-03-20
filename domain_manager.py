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
    
    @abstractmethod
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        ...
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        ...
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
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
        self.provider: Optional[str] = None
        self._api_key_hint: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
    
    def configure(self, api_key: str, secret_key: str,
                  monthly_budget: float = 50.0, provider: str = "porkbun"):
        """Configure domain provider credentials and budget"""
        provider_name = provider.strip().lower()
        if provider_name != "porkbun":
            raise ValueError(f"Unsupported provider: {provider}")
        if not api_key or not secret_key:
            raise ValueError("Both api_key and secret_key are required")
        
        self.set_api_client(PorkbunAPIClient(api_key, secret_key))
        self.provider = provider_name
        self._api_key_hint = api_key[-4:] if len(api_key) >= 4 else api_key
        self.monthly_budget = float(monthly_budget)
    
    def get_config(self) -> Dict[str, Any]:
        """Return current domain manager configuration metadata"""
        configured = self.api_client is not None
        budget_status = self.get_budget_status()
        provider_name = self.provider or ("porkbun" if isinstance(self.api_client, PorkbunAPIClient) else None)
        api_key_masked = f"{'*' * 8}{self._api_key_hint}" if self._api_key_hint else None
        
        return {
            "configured": configured,
            "provider": provider_name,
            "api_key_masked": api_key_masked,
            "monthly_budget": budget_status["monthly_budget"],
            "current_spending": budget_status["current_spending"],
            "remaining": budget_status["remaining"],
            "remaining_budget": budget_status["remaining"],
            "active_domain": self.active_domain,
            "domains_owned": budget_status["domains_owned"]
        }
    
    @staticmethod
    def _parse_price(price_value: Any, default: float = 999.0) -> float:
        """Parse numeric/str price formats into float"""
        if isinstance(price_value, (int, float)):
            return float(price_value)
        if isinstance(price_value, str):
            cleaned = (
                price_value.strip()
                .replace("$", "")
                .replace("€", "")
                .replace(",", "")
            )
            if not cleaned:
                return default
            try:
                return float(cleaned)
            except ValueError:
                return default
        return default
    
    def search_cheap_domains(self, tlds: Optional[List[str]] = None, max_price: float = 5.0,
                             limit: int = 5, max_attempts: int = 25) -> List[Dict[str, Any]]:
        """
        Return a list of cheap available domains without purchasing.
        """
        if not self.api_client or limit <= 0:
            return []
        
        selected_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        found_domains: List[Dict[str, Any]] = []
        seen = set()
        attempts = 0
        
        while len(found_domains) < limit and attempts < max_attempts:
            attempts += 1
            tld = random.choice(selected_tlds)
            domain = self.generate_random_domain(tld=tld)
            if domain in seen:
                continue
            seen.add(domain)
            
            result = self.api_client.search_domain(domain)
            if not result.get("available"):
                continue
            
            price = self._parse_price(result.get("price"))
            if price <= max_price:
                found_domains.append({
                    "domain": domain,
                    "price": price,
                    "tld": tld
                })
        
        return found_domains
    
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
        result = self.rotate_to_new_domain()
        if result.get("success"):
            return result.get("domain")
        return None
    
    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Rotate to a new domain and return a structured result.
        """
        if not self.api_client:
            return {
                "success": False,
                "error": "No API client configured"
            }
        
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            return {
                "success": False,
                "error": "No available domain found within price constraints"
            }
        
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"]
        )
        if not success:
            return {
                "success": False,
                "domain": domain_info["domain"],
                "price": domain_info["price"],
                "error": "Domain purchase failed or exceeded budget"
            }
        
        return {
            "success": True,
            "domain": domain_info["domain"],
            "cost": domain_info["price"],
            "active_domain": self.active_domain,
            "budget": self.get_budget_status()
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


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
