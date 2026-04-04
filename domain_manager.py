"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import os
import requests
import random
import string
import logging
from typing import Dict, List, Optional
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
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.configured_via_env = False
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    @staticmethod
    def _coerce_price(price_value) -> Optional[float]:
        """Convert API price value to a float when possible."""
        if isinstance(price_value, (int, float)):
            return float(price_value)

        if isinstance(price_value, str):
            cleaned = price_value.strip().replace("$", "").replace("€", "")
            try:
                return float(cleaned)
            except ValueError:
                return None

        return None

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> bool:
        """
        Configure registrar credentials and budget.
        """
        if not api_key or not secret_key:
            raise ValueError("api_key and secret_key are required")

        budget = float(monthly_budget)
        if budget <= 0:
            raise ValueError("monthly_budget must be greater than zero")

        self.api_client = PorkbunAPIClient(api_key, secret_key)
        self.monthly_budget = budget
        logger.info("Domain rotation manager configured")
        return True

    def configure_from_env(self, environ: Optional[Dict[str, str]] = None) -> bool:
        """
        Configure from environment variables if credentials are present.

        Expected environment variables:
        - PORKBUN_API_KEY
        - PORKBUN_API_SECRET
        - DOMAIN_MONTHLY_BUDGET (optional, default 50.0)
        """
        env = environ or os.environ
        api_key = env.get("PORKBUN_API_KEY", "").strip()
        secret_key = env.get("PORKBUN_API_SECRET", "").strip()

        if not api_key or not secret_key:
            return False

        budget_raw = env.get("DOMAIN_MONTHLY_BUDGET", "50.0").strip()
        try:
            monthly_budget = float(budget_raw)
        except ValueError:
            logger.warning(
                "Invalid DOMAIN_MONTHLY_BUDGET value '%s'; defaulting to 50.0",
                budget_raw
            )
            monthly_budget = 50.0

        if monthly_budget <= 0:
            logger.warning(
                "Non-positive DOMAIN_MONTHLY_BUDGET value '%s'; defaulting to 50.0",
                budget_raw
            )
            monthly_budget = 50.0

        self.configure(api_key, secret_key, monthly_budget)
        self.configured_via_env = True
        logger.info("Domain rotation manager configured from environment")
        return True

    def get_config(self) -> Dict:
        """Return safe configuration and runtime status."""
        return {
            "configured": self.api_client is not None,
            "configured_via_env": self.configured_via_env,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "active_domain": self.active_domain
        }
    
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
                price = self._coerce_price(result.get("price"))
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
        result = self.rotate_domain_with_result()
        if result.get("success"):
            return result.get("domain")
        return None

    def rotate_domain_with_result(self) -> Dict:
        """
        Rotate to a new domain and return a detailed operation result.
        """
        if not self.api_client:
            return {"success": False, "error": "No API client configured"}

        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        if not domain_info:
            return {"success": False, "error": "Could not find available cheap domain"}

        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )

        if success:
            self.active_domain = domain_info["domain"]
            return {
                "success": True,
                "domain": self.active_domain,
                "price": domain_info["price"]
            }

        return {"success": False, "error": "Purchase failed or budget exceeded"}
    
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
domain_rotation_manager.configure_from_env()
