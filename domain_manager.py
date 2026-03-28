"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from abc import ABC, abstractmethod
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


class DomainBudgetManager:
    """
    Compatibility layer for legacy budget_manager calls documented in guides.
    """

    def __init__(self, manager: "DomainRotationManager"):
        self._manager = manager

    @property
    def monthly_budget(self) -> float:
        return self._manager.monthly_budget

    def set_monthly_budget(self, amount: float) -> None:
        self._manager.monthly_budget = max(0.0, float(amount))

    def get_month_spending(self) -> float:
        return self._manager.current_spending

    def get_remaining_budget(self) -> float:
        return max(0.0, self._manager.monthly_budget - self._manager.current_spending)


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
        self.test_mode = False
        self._api_clients: Dict[str, DomainAPIClient] = {}
        if api_client:
            self._api_clients["default"] = api_client
        self.domain_dns_records: Dict[str, Dict[str, Any]] = {}
        self.budget_manager = DomainBudgetManager(self)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self._api_clients["default"] = api_client

    def add_api_client(self, provider: str, api_client: DomainAPIClient) -> None:
        """
        Register an API client for multi-provider setups.
        """
        provider_name = provider.strip().lower()
        self._api_clients[provider_name] = api_client
        if not self.api_client:
            self.api_client = api_client

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        monthly_budget: float = 50.0,
        provider: str = "porkbun",
    ) -> Dict[str, Any]:
        """
        Configure domain rotation with registrar credentials.
        """
        selected_secret = secret_key if secret_key is not None else api_secret
        selected_provider = provider.strip().lower()

        if selected_provider != "porkbun":
            raise ValueError(f"Unsupported provider: {provider}")
        if not api_key or not selected_secret:
            raise ValueError("Both api_key and secret_key are required")

        client = PorkbunAPIClient(api_key=api_key, api_secret=selected_secret)
        self.add_api_client(selected_provider, client)
        self.set_api_client(client)
        self.monthly_budget = max(0.0, float(monthly_budget))

        return self.get_config(include_sensitive=False)

    def get_config(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Return current manager configuration and health.
        """
        configured = self.api_client is not None
        config: Dict[str, Any] = {
            "configured": configured,
            "provider": "porkbun" if configured else None,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": max(0.0, self.monthly_budget - self.current_spending),
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode,
        }
        if include_sensitive and configured:
            config["api_key"] = getattr(self.api_client, "api_key", None)
            config["api_secret"] = getattr(self.api_client, "api_secret", None)
        return config

    def set_test_mode(self, enabled: bool) -> None:
        """
        Enable/disable test mode. Test mode simulates purchases.
        """
        self.test_mode = bool(enabled)
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        """
        Backward-compatible alias used by documentation.
        """
        return self.generate_random_domain(tld=tld, length=length)
    
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
                price = result.get("price", 999)
                
                if isinstance(price, str):
                    # Remove currency symbols
                    price = float(price.replace("$", "").replace("€", ""))
                
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 5,
        name_length: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        Search for multiple cheap available domains without purchasing them.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return []

        search_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        found: List[Dict[str, Any]] = []
        attempts = max(limit * 4, 10)

        for _ in range(attempts):
            if len(found) >= limit:
                break

            tld = random.choice(search_tlds)
            domain = self.generate_random_domain(tld=tld, length=name_length)
            result = self.api_client.search_domain(domain)
            if not result.get("available"):
                continue

            price_value = result.get("price", 999)
            if isinstance(price_value, str):
                try:
                    price_value = float(price_value.replace("$", "").replace("€", ""))
                except ValueError:
                    continue

            if price_value > max_price:
                continue

            found.append(
                {
                    "domain": domain,
                    "name": domain,
                    "price": float(price_value),
                    "tld": tld,
                }
            )

        return found
    
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

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Higher-level rotation API returning structured status data.
        """
        if self.test_mode:
            domain = self.generate_random_domain()
            self.active_domain = domain
            return {
                "success": True,
                "domain": domain,
                "cost": 0.0,
                "test_mode": True,
            }

        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            return {"success": False, "error": "No cheap domain found"}

        if self.purchase_domain_if_budget_allows(domain_info["domain"], domain_info["price"]):
            return {
                "success": True,
                "domain": domain_info["domain"],
                "cost": domain_info["price"],
                "test_mode": False,
            }

        return {"success": False, "error": "Purchase failed or budget exceeded"}

    def configure_domain_dns(
        self,
        domain: str,
        mx_records: Optional[List[Dict[str, Any]]] = None,
        a_records: Optional[List[Dict[str, Any]]] = None,
        cname_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Store desired DNS records for the domain.
        This keeps a local source of truth for future registrar sync.
        """
        if not domain:
            return {"success": False, "error": "Domain is required"}

        self.domain_dns_records[domain] = {
            "mx_records": mx_records or [],
            "a_records": a_records or [],
            "cname_records": cname_records or [],
            "updated_at": datetime.now().isoformat(),
        }
        return {
            "success": True,
            "domain": domain,
            "message": "DNS records updated locally",
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
