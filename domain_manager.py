"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from typing import Any, Dict, List, Optional, Union
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
        self.api_client: Optional[DomainAPIClient] = None
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False
        if api_client:
            self.set_api_client(api_client)
    
    def set_api_client(self, api_client: DomainAPIClient, provider_name: str = "default"):
        """Set the domain API client"""
        self.api_clients[provider_name] = api_client
        self.active_provider = provider_name
        self.api_client = api_client

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient,
                      set_active: bool = False):
        """Register an API client under a provider name"""
        self.api_clients[provider_name] = api_client
        if set_active or not self.api_client:
            self.active_provider = provider_name
            self.api_client = api_client

    def set_active_provider(self, provider_name: str) -> bool:
        """Set the currently active registrar provider"""
        api_client = self.api_clients.get(provider_name)
        if not api_client:
            return False
        self.active_provider = provider_name
        self.api_client = api_client
        return True

    def get_active_provider(self) -> Optional[str]:
        """Get active registrar provider name"""
        return self.active_provider

    def set_test_mode(self, enabled: bool = True):
        """
        Enable or disable test mode.
        In test mode, purchases are simulated and no API purchase call is made.
        """
        self.test_mode = enabled

    def configure(self, api_key: str, secret_key: str,
                  monthly_budget: float = 50.0,
                  provider: str = "porkbun") -> Dict:
        """
        Configure the domain manager from runtime settings.
        """
        if monthly_budget <= 0:
            raise ValueError("Monthly budget must be greater than 0")

        provider_normalized = provider.lower().strip()
        if provider_normalized != "porkbun":
            raise ValueError(f"Unsupported provider: {provider}")

        client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
        self.add_api_client("porkbun", client, set_active=True)
        self.monthly_budget = monthly_budget
        return self.get_config()

    def get_config(self) -> Dict:
        """Return current domain manager configuration snapshot"""
        return {
            "configured": self.api_client is not None,
            "active_provider": self.active_provider,
            "available_providers": sorted(self.api_clients.keys()),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode
        }
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        """Compatibility alias for docs and integrations"""
        return self.generate_random_domain(tld=tld, length=length)

    def generate_domain_from_pattern(self, pattern: str, tld: str = "xyz") -> str:
        """
        Generate a domain from pattern placeholders:
        - {timestamp}: YYYYMMDDHHMMSS
        - {random}: 4-char random suffix
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = ''.join(random.choice(string.ascii_lowercase + string.digits)
                                for _ in range(4))
        generated = pattern.replace("{timestamp}", timestamp).replace("{random}", random_suffix)
        sanitized = ''.join(ch for ch in generated.lower() if ch.isalnum() or ch == "-").strip("-")
        if not sanitized:
            sanitized = self.generate_random_domain_name(length=8, tld=tld).split(".")[0]
        return f"{sanitized}.{tld}"

    @staticmethod
    def _normalize_price(price_value: Any, fallback: float = 999.0) -> float:
        """Normalize API price values into float for budget checks"""
        if price_value is None:
            return fallback
        if isinstance(price_value, (int, float)):
            return float(price_value)
        if isinstance(price_value, str):
            cleaned = price_value.replace("$", "").replace("€", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return fallback
        return fallback

    def search_cheap_domains(self, tlds: Optional[List[str]] = None,
                            max_price: float = 5.0,
                            limit: int = 10,
                            max_attempts: int = 50) -> List[Dict]:
        """
        Search for multiple cheap available domains.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return []

        search_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        found: List[Dict] = []
        seen_domains = set()

        for _ in range(max_attempts):
            if len(found) >= limit:
                break
            tld = random.choice(search_tlds)
            domain = self.generate_random_domain(tld)
            result = self.api_client.search_domain(domain)
            price = self._normalize_price(result.get("price"))
            candidate_domain = result.get("domain", domain)

            if result.get("available") and price <= max_price and candidate_domain not in seen_domains:
                found.append({
                    "domain": candidate_domain,
                    "price": price,
                    "tld": tld
                })
                seen_domains.add(candidate_domain)

        return found
    
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
                price = self._normalize_price(result.get("price"), fallback=999.0)
                resolved_domain = result.get("domain", domain)
                
                if price <= max_price:
                    return {
                        "domain": resolved_domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None

    def _record_domain_purchase(self, domain: str, price: float):
        """Record successful domain purchase in local manager state"""
        self.current_spending += price
        self.owned_domains.append({
            "domain": domain,
            "price": price,
            "purchased_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=365)
        })
        if not self.active_domain:
            self.active_domain = domain
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False

        if self.test_mode:
            logger.info("Test mode enabled. Simulating purchase for %s", domain)
            self._record_domain_purchase(domain, price)
            self.active_domain = domain
            return True

        if not self.api_client:
            logger.error("No API client configured")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self._record_domain_purchase(domain, price)
            self.active_domain = domain
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self, return_details: bool = False) -> Union[Optional[str], Dict]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            if return_details:
                return {"success": False, "error": "Could not find available cheap domain"}
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
                    "cost": domain_info["price"],
                    "provider": self.active_provider
                }
            return self.active_domain

        if return_details:
            return {
                "success": False,
                "error": "Failed to purchase selected domain",
                "domain": domain_info["domain"],
                "cost": domain_info["price"]
            }
        return None

    def rotate_to_new_domain(self) -> Dict:
        """
        Compatibility helper returning rich result payload.
        """
        result = self.rotate_domain(return_details=True)
        if isinstance(result, dict):
            return result
        return {"success": False, "error": "Unknown rotation result"}
    
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
