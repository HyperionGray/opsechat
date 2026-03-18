"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
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
        raise NotImplementedError("Subclasses must implement search_domain")
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("Subclasses must implement purchase_domain")
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError("Subclasses must implement get_pricing")


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
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        if api_client:
            self.add_api_client("default", api_client, make_active=True)
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.add_api_client("default", api_client, make_active=True)

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient,
                       make_active: bool = False):
        """Add or replace a provider-specific API client."""
        self.api_clients[provider_name] = api_client
        if make_active or not self.active_provider:
            self.active_provider = provider_name
            self.api_client = api_client

    def list_api_clients(self) -> List[str]:
        """Return configured provider names."""
        return sorted(self.api_clients.keys())

    def set_active_provider(self, provider_name: str) -> bool:
        """Switch active provider if configured."""
        api_client = self.api_clients.get(provider_name)
        if not api_client:
            return False
        self.active_provider = provider_name
        self.api_client = api_client
        return True

    def _iter_clients(self) -> List[tuple]:
        """Yield configured clients, preferring active provider first."""
        if self.active_provider and self.active_provider in self.api_clients:
            ordered = [(self.active_provider, self.api_clients[self.active_provider])]
            for name, client in self.api_clients.items():
                if name != self.active_provider:
                    ordered.append((name, client))
            return ordered

        if self.api_client:
            return [("default", self.api_client)]
        return []

    @staticmethod
    def _normalize_price(raw_price) -> Optional[float]:
        """Normalize API price output to float."""
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if isinstance(raw_price, str):
            cleaned = (
                raw_price.replace("$", "")
                .replace("€", "")
                .replace("£", "")
                .replace(",", "")
                .strip()
            )
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
    
    def find_cheap_available_domain(self, max_price: float = 5.0,
                                   max_attempts: int = 10,
                                   tlds: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        clients = self._iter_clients()
        if not clients:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for provider_name, client in clients:
                result = client.search_domain(domain)

                if result.get("available"):
                    price = self._normalize_price(result.get("price"))

                    if price is not None and price <= max_price:
                        return {
                            "domain": domain,
                            "price": price,
                            "tld": tld,
                            "provider": provider_name
                        }
        
        return None

    def search_cheap_domains(self, tlds: Optional[List[str]] = None, max_price: float = 5.0,
                             limit: int = 5, max_attempts: int = 25) -> List[Dict]:
        """Search for multiple cheap available domains."""
        results: List[Dict] = []
        seen = set()
        attempts = 0

        while len(results) < limit and attempts < max_attempts:
            attempts += 1
            domain_info = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=tlds,
            )
            if not domain_info:
                continue
            if domain_info["domain"] in seen:
                continue
            seen.add(domain_info["domain"])
            results.append(domain_info)

        return results
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float,
                                         provider_name: Optional[str] = None) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        api_client = None
        provider_to_use = provider_name
        if provider_to_use:
            api_client = self.api_clients.get(provider_to_use)
        else:
            provider_to_use = self.active_provider or "default"
            api_client = self.api_client

        if not api_client:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": provider_to_use,
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
        if result["success"]:
            return result["domain"]
        return None

    def rotate_to_new_domain(self, max_price: float = 5.0,
                             max_attempts: int = 10) -> Dict:
        """
        Rotate to a new domain with structured status details.
        """
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=max_attempts,
        )

        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {
                "success": False,
                "domain": None,
                "cost": 0.0,
                "provider": None,
                "error": "Could not find available cheap domain",
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider_name=domain_info.get("provider"),
        )

        if success:
            self.active_domain = domain_info["domain"]
            return {
                "success": True,
                "domain": self.active_domain,
                "cost": domain_info["price"],
                "provider": domain_info.get("provider"),
            }

        return {
            "success": False,
            "domain": domain_info["domain"],
            "cost": domain_info["price"],
            "provider": domain_info.get("provider"),
            "error": "Purchase failed or budget exceeded",
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

    def set_monthly_budget(self, amount: float):
        """Update monthly budget ceiling."""
        if amount < 0:
            raise ValueError("Budget amount cannot be negative")
        self.monthly_budget = amount

    def reset_monthly_spending(self):
        """Reset tracked monthly spending."""
        self.current_spending = 0.0

    def serialize_owned_domains(self) -> List[Dict]:
        """Return JSON-serializable owned domain records."""
        serialized = []
        for domain in self.owned_domains:
            item = dict(domain)
            purchased_at = item.get("purchased_at")
            expires_at = item.get("expires_at")
            if isinstance(purchased_at, datetime):
                item["purchased_at"] = purchased_at.isoformat()
            if isinstance(expires_at, datetime):
                item["expires_at"] = expires_at.isoformat()
            serialized.append(item)
        return serialized

    def load_owned_domains(self, records: List[Dict]):
        """Load owned domain records from JSON-compatible dictionaries."""
        loaded = []
        for record in records:
            item = dict(record)
            for field in ("purchased_at", "expires_at"):
                value = item.get(field)
                if isinstance(value, str):
                    try:
                        item[field] = datetime.fromisoformat(value)
                    except ValueError:
                        # Keep original value if it is not ISO-formatted.
                        pass
            loaded.append(item)
        self.owned_domains = loaded


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
