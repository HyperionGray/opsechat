"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
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
        raise NotImplementedError("search_domain must be implemented by subclasses")
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("purchase_domain must be implemented by subclasses")
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError("get_pricing must be implemented by subclasses")


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management
    https://porkbun.com/api/json/v3/documentation
    """
    
    BASE_URL = "https://porkbun.com/api/json/v3"
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        # Legacy compatibility alias used by some manual checks/scripts.
        self.secret_key = api_secret
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
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        if api_client:
            self.api_clients["default"] = api_client
            self.active_provider = "default"
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.api_key: Optional[str] = None
        self.api_secret: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.add_api_client("default", api_client, make_active=True)

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient, make_active: bool = False):
        """
        Register a named provider client.

        This allows callers to prepare multiple registrar clients and switch
        between them without recreating the manager.
        """
        provider = (provider_name or "").strip().lower()
        if not provider:
            raise ValueError("provider_name must be non-empty")

        self.api_clients[provider] = api_client
        if make_active or self.api_client is None:
            self.api_client = api_client
            self.active_provider = provider

    def use_api_client(self, provider_name: str) -> bool:
        """Switch active provider by name."""
        provider = (provider_name or "").strip().lower()
        client = self.api_clients.get(provider)
        if not client:
            return False
        self.api_client = client
        self.active_provider = provider
        return True

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> bool:
        """Configure registrar credentials and budget."""
self.api_key = api_key.strip() if api_key.strip() else None
self.api_secret = secret_key.strip() if secret_key.strip() else None
        self.set_monthly_budget(monthly_budget)

        if not self.api_key or not self.api_secret:
            self.api_client = None
            self.active_provider = None
            return False

        self.add_api_client(
            provider_name="porkbun",
            api_client=PorkbunAPIClient(self.api_key, self.api_secret),
            make_active=True,
        )
        return True

    def get_config(self) -> Dict:
        """Return safe configuration details for UI/API use."""
        return {
            "configured": self.api_client is not None,
            "has_api_key": bool(self.api_key),
            "has_secret_key": bool(self.api_secret),
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            "active_provider": self.active_provider,
            "providers": sorted(self.api_clients.keys()),
        }

    @staticmethod
    def _normalize_price(price_value) -> Optional[float]:
        """Convert API price values to float when possible."""
        if isinstance(price_value, (int, float)):
            return float(price_value)
        if isinstance(price_value, str):
            cleaned = price_value.replace("$", "").replace("€", "").strip()
            if not cleaned:
                return None
            try:
                return float(cleaned)
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

    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        """Backward-compatible alias for random domain generation."""
        return self.generate_random_domain(tld=tld, length=length)

    def generate_domain_name(self, tld: str = "xyz", length: int = 8) -> str:
        """Backward-compatible alias used by manual validation scripts."""
        return self.generate_random_domain(tld=tld, length=length)
    
    def find_cheap_available_domain(self, max_price: float = 5.0, 
                                   max_attempts: int = 10,
                                   tlds: Optional[List[str]] = None,
                                   length: int = 8) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_client:
            logger.error("No API client configured")
            return None
        
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld=tld, length=length)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = self._normalize_price(result.get("price", 999))
                if price is None:
                    continue
                
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None

    def search_cheap_domains(self, tlds: Optional[List[str]] = None, max_price: float = 5.0,
                             limit: int = 10, max_attempts: Optional[int] = None,
                             length: int = 8) -> List[Dict]:
        """
        Find multiple currently-available cheap domains without purchasing.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return []

        if limit <= 0:
            return []

attempts = max_attempts if max_attempts is not None else min(max(10, limit * 3), 100)
        seen_domains = set()
        matches: List[Dict] = []
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]

        for _ in range(attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld=tld, length=length)
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            result = self.api_client.search_domain(domain)
            if not result.get("available"):
                continue

            price = self._normalize_price(result.get("price", 999))
            if price is None or price > max_price:
                continue

            matches.append({
                "domain": domain,
                "price": price,
                "tld": tld,
            })

            if len(matches) >= limit:
                break

        return matches
    
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
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return {
                "success": False,
                "domain": domain,
                "message": "Budget exceeded",
                "budget_status": self.get_budget_status(),
            }
        
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
            return {
                "success": True,
                "domain": domain,
                "price": price,
                "message": "Domain purchased successfully",
                "active_domain": self.active_domain,
                "budget_status": self.get_budget_status(),
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
        return self.rotate_to_new_domain()

    def rotate_to_new_domain(self, max_price: float = 5.0, max_attempts: int = 10) -> Dict:
        """Backward-compatible rotation entrypoint with tunable limits."""
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=max_attempts,
        )
        
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

    def set_monthly_budget(self, amount: float) -> float:
        """Set and return monthly domain budget."""
        self.monthly_budget = max(0.0, float(amount))
        return self.monthly_budget
    
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
