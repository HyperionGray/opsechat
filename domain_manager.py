"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
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
        raise NotImplementedError
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError
    
    @abstractmethod
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


class MockDomainAPIClient(DomainAPIClient):
    """
    In-memory mock registrar client for local testing.
    Never performs network requests or real purchases.
    """

    _BASE_PRICES = {
        "xyz": 0.99,
        "club": 1.99,
        "online": 2.99,
        "site": 2.49,
        "website": 2.99,
        "com": 8.99,
    }

    def __init__(self, api_key: str = "mock-key", api_secret: Optional[str] = None):
        super().__init__(api_key=api_key, api_secret=api_secret)
        self._purchased: List[str] = []

    def _price_for_tld(self, tld: str) -> float:
        return self._BASE_PRICES.get(tld.lower(), 4.99)

    def search_domain(self, domain: str) -> Dict:
        tld = domain.rsplit(".", 1)[-1].lower()
        # Keep behavior deterministic-ish while looking realistic:
        # reserved domains look unavailable; others available.
        blocked_prefixes = ("admin", "mail", "root", "support")
        label = domain.split(".", 1)[0].lower()
        available = not label.startswith(blocked_prefixes) and domain not in self._purchased

        return {
            "domain": domain,
            "available": available,
            "price": self._price_for_tld(tld),
            "currency": "USD",
            "mock": True,
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        if domain in self._purchased:
            return {
                "success": False,
                "domain": domain,
                "message": "Domain already purchased in mock mode",
                "order_id": None,
                "mock": True,
            }

        self._purchased.append(domain)
        return {
            "success": True,
            "domain": domain,
            "message": f"Mock purchase successful for {years} year(s)",
            "order_id": f"mock-{len(self._purchased):06d}",
            "mock": True,
        }

    def get_pricing(self, tld: str) -> Dict:
        price = self._price_for_tld(tld)
        return {
            "tld": tld,
            "registration": f"{price:.2f}",
            "renewal": f"{(price * 1.5):.2f}",
            "transfer": f"{price:.2f}",
            "currency": "USD",
            "mock": True,
        }


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
        self._provider = "custom" if api_client else "unconfigured"
        self._api_key_preview: Optional[str] = self._mask_key(
            getattr(api_client, "api_key", None)
        ) if api_client else None
    
    def set_api_client(self, api_client: DomainAPIClient, provider: str = "custom"):
        """Set the domain API client"""
        self.api_client = api_client
        self._provider = provider
        self._api_key_preview = self._mask_key(getattr(api_client, "api_key", None))

    @staticmethod
    def _mask_key(key: Optional[str]) -> Optional[str]:
        if not key:
            return None
        key = str(key)
        if len(key) <= 4:
            return "*" * len(key)
        return f"{'*' * (len(key) - 4)}{key[-4:]}"

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _serialize_datetime(value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _coerce_price(value: Any, default: float = 999.0) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = value.replace("$", "").replace("€", "").strip()
            try:
                return float(normalized)
            except ValueError:
                return default
        return default

    def configure(self, api_key: str = "", secret_key: str = "",
                  monthly_budget: float = 50.0, provider: str = "porkbun",
                  use_mock: bool = False) -> Dict:
        """
        Configure domain API integration.
        Supports real Porkbun credentials or mock mode for testing.
        """
        self.monthly_budget = float(monthly_budget)

        if use_mock or provider.lower() == "mock":
            self.set_api_client(MockDomainAPIClient(api_key or "mock-key"), provider="mock")
            return {
                "success": True,
                "provider": "mock",
                "monthly_budget": self.monthly_budget,
                "message": "Configured mock registrar mode",
            }

        if not api_key or not secret_key:
            raise ValueError("API key and secret key are required for Porkbun configuration")

        self.set_api_client(PorkbunAPIClient(api_key, secret_key), provider="porkbun")
        return {
            "success": True,
            "provider": "porkbun",
            "monthly_budget": self.monthly_budget,
            "message": "Configured Porkbun API client",
        }

    def get_config(self) -> Dict:
        """Get non-sensitive configuration status."""
        return {
            "configured": self.api_client is not None,
            "provider": self._provider,
            "api_key_preview": self._api_key_preview,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def set_owned_domains(self, domains: List[Dict]):
        """
        Load owned domains from persisted state.
        Accepts datetime objects or ISO8601 strings for dates.
        """
        normalized: List[Dict] = []
        for record in domains or []:
            if not isinstance(record, dict):
                continue
            purchased_at = self._parse_datetime(record.get("purchased_at")) or datetime.now()
            expires_at = self._parse_datetime(record.get("expires_at")) or (purchased_at + timedelta(days=365))
            normalized.append({
                "domain": record.get("domain"),
                "price": self._coerce_price(record.get("price"), default=0.0),
                "purchased_at": purchased_at,
                "expires_at": expires_at,
            })
        self.owned_domains = normalized
    
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
                price = self._coerce_price(result.get("price", 999))
                
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
        price = self._coerce_price(price, default=float("inf"))
        if price == float("inf"):
            logger.error(f"Invalid price for domain purchase: {price}")
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
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return [
            {
                "domain": d.get("domain"),
                "price": d.get("price"),
                "purchased_at": self._serialize_datetime(d.get("purchased_at")),
                "expires_at": self._serialize_datetime(d.get("expires_at")),
            }
            for d in self.owned_domains
        ]
    
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
