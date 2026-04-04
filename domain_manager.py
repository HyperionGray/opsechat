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


class _BudgetManagerAdapter:
    """Compatibility shim for older examples that expect budget_manager.* methods."""

    def __init__(self, manager: "DomainRotationManager"):
        self._manager = manager

    @property
    def monthly_budget(self) -> float:
        return self._manager.monthly_budget

    def set_monthly_budget(self, amount: float):
        self._manager.monthly_budget = float(amount)

    def get_month_spending(self) -> float:
        return self._manager.current_spending

    def get_remaining_budget(self) -> float:
        return self._manager.monthly_budget - self._manager.current_spending


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        raise NotImplementedError("search_domain() must be implemented by subclasses")
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("purchase_domain() must be implemented by subclasses")
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError("get_pricing() must be implemented by subclasses")


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
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.default_api_client_name: Optional[str] = None
        self.test_mode = False

        # Compatibility adapter used by older docs/examples.
        self.budget_manager = _BudgetManagerAdapter(self)

        if api_client:
            self.add_api_client("default", api_client)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.add_api_client("default", api_client)

    def add_api_client(self, name: str, api_client: DomainAPIClient):
        """Register an API client by name for future registrar switching."""
        self.api_clients[name] = api_client
        if not self.default_api_client_name:
            self.default_api_client_name = name
        if self.default_api_client_name == name:
            self.api_client = api_client

    def set_test_mode(self, enabled: bool = True):
        """Enable/disable simulation mode (no real purchases)."""
        self.test_mode = enabled

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 50.0
    ) -> Dict:
        """
        Configure Porkbun integration and budget.
        Returns a status dict suitable for API responses.
        """
        if not api_key or not secret_key:
            raise ValueError("Both api_key and secret_key are required")

        self.monthly_budget = float(monthly_budget)
        client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
        self.set_api_client(client)

        return {
            "success": True,
            "provider": "porkbun",
            "monthly_budget": self.monthly_budget
        }

    def get_config(self) -> Dict:
        """Return non-sensitive config/state for UI usage."""
        return {
            "configured": self.api_client is not None,
            "provider": "porkbun" if isinstance(self.api_client, PorkbunAPIClient) else None,
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            "budget_status": self.get_budget_status()
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
        """Backward-compatible alias for docs/examples."""
        return self.generate_random_domain(tld=tld, length=length)

    def generate_domain_from_pattern(self, pattern: str, tld: str = "xyz") -> str:
        """
        Generate a domain from pattern placeholders:
        - {timestamp}: UTC YYYYMMDDHHMMSS
        - {random}: 4-char random token
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        rand = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))
        domain_name = pattern.replace("{timestamp}", timestamp).replace("{random}", rand)

        # Keep only DNS-safe characters for label.
        safe = ''.join(c for c in domain_name.lower() if c.isalnum() or c == "-").strip("-")
        if not safe:
            safe = self.generate_random_domain_name(length=8, tld=tld).split(".")[0]
        return f"{safe}.{tld}"
    
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
        max_attempts: int = 25
    ) -> List[Dict]:
        """
        Search for multiple cheap domains.
        Returns up to `limit` domain info records.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return []

        tld_pool = tlds or ["xyz", "club", "online", "site", "website"]
        results: List[Dict] = []

        for _ in range(max_attempts):
            if len(results) >= limit:
                break
            tld = random.choice(tld_pool)
            domain = self.generate_random_domain(tld=tld)
            search = self.api_client.search_domain(domain)
            if not search.get("available"):
                continue

            price = search.get("price", 999)
            if isinstance(price, str):
                try:
                    price = float(price.replace("$", "").replace("€", "").strip())
                except ValueError:
                    continue

            if price <= max_price:
                results.append({
                    "domain": domain,
                    "name": domain,
                    "price": price,
                    "tld": tld,
                })

        return results
    
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

        if self.test_mode:
            logger.info(f"[TEST MODE] Simulating domain purchase: {domain} (${price})")
            result = {"success": True, "domain": domain, "order_id": "test-mode"}
        else:
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

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict:
        """
        Backward-compatible rotation method that returns a result dictionary.
        """
        budget = self.get_budget_status()
        effective_max = min(max_price, budget["remaining"])

        if effective_max <= 0:
            return {"success": False, "error": "Budget exceeded", "domain": None, "cost": 0.0}

        domain_info = self.find_cheap_available_domain(max_price=effective_max)
        if not domain_info:
            return {
                "success": False,
                "error": "No available domain found within budget",
                "domain": None,
                "cost": 0.0
            }

        success = self.purchase_domain_if_budget_allows(domain_info["domain"], domain_info["price"])
        if not success:
            return {
                "success": False,
                "error": "Purchase failed",
                "domain": None,
                "cost": 0.0
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "cost": float(domain_info["price"]),
            "remaining_budget": self.monthly_budget - self.current_spending
        }

    def configure_domain_dns(
        self,
        domain: str,
        mx_records: Optional[List[Dict]] = None,
        a_records: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Placeholder API for DNS configuration.
        Current clients in this repository don't implement DNS APIs yet.
        """
        return {
            "success": False,
            "domain": domain,
            "message": "DNS configuration API not implemented for the current registrar client",
            "mx_records_requested": len(mx_records or []),
            "a_records_requested": len(a_records or [])
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
