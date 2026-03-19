"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from typing import Any, Dict, List, Optional
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
    
    CHEAP_TLDS = ["xyz", "club", "online", "site", "website"]

    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self._provider = "porkbun"
        self._api_key: Optional[str] = None
        self._secret_key: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    @staticmethod
    def _mask_secret(value: Optional[str]) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * (len(value) - 4)}{value[-4:]}"

    @staticmethod
    def _parse_price(value: Any) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace("€", "").replace(",", "")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 10.0,
        provider: str = "porkbun",
    ) -> Dict[str, Any]:
        """
        Configure registrar credentials and budget for route/CLI consumers.
        """
        normalized_provider = provider.strip().lower()
        if normalized_provider != "porkbun":
            raise ValueError(f"Unsupported provider: {provider}")

        normalized_key = (api_key or "").strip()
        normalized_secret = (secret_key or "").strip()
        if not normalized_key or not normalized_secret:
            raise ValueError("API key and secret key are required")

        self._provider = normalized_provider
        self._api_key = normalized_key
        self._secret_key = normalized_secret
        self.monthly_budget = float(monthly_budget)
        self.set_api_client(PorkbunAPIClient(self._api_key, self._secret_key))
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return non-sensitive domain rotation configuration."""
        return {
            "provider": self._provider,
            "configured": bool(self._api_key and self._secret_key and self.api_client),
            "api_key": self._mask_secret(self._api_key),
            "secret_key": self._mask_secret(self._secret_key),
            "monthly_budget": self.monthly_budget,
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
        """Compatibility wrapper used by older docs and scripts."""
        return self.generate_random_domain(tld=tld, length=length)
    
    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        tlds: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = tlds or self.CHEAP_TLDS
        if not cheap_tlds:
            return None
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = self._parse_price(result.get("price"))
                if price is None:
                    continue
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
        max_attempts_per_domain: int = 8,
    ) -> List[Dict[str, Any]]:
        """
        Search for multiple available cheap domains without purchasing.
        """
        if limit <= 0:
            return []

        results: List[Dict[str, Any]] = []
        seen_domains = set()
        max_attempts = max(limit * max_attempts_per_domain, max_attempts_per_domain)

        for _ in range(max_attempts):
            domain_info = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=tlds,
            )
            if not domain_info:
                continue
            domain_name = domain_info["domain"]
            if domain_name in seen_domains:
                continue
            seen_domains.add(domain_name)
            results.append(domain_info)
            if len(results) >= limit:
                break

        return results
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False
        
        normalized_price = self._parse_price(price)
        if normalized_price is None:
            logger.error(f"Invalid price value for purchase: {price}")
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
            
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Rotate to a new domain and return structured status.
        """
        remaining_budget = self.monthly_budget - self.current_spending
        if remaining_budget <= 0:
            return {
                "success": False,
                "error": "Budget exhausted",
                "domain": None,
            }

        domain_info = self.find_cheap_available_domain(
            max_price=min(max_price, remaining_budget)
        )

        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain",
                "domain": None,
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
        )

        if not success:
            return {
                "success": False,
                "error": "Failed to purchase domain",
                "domain": domain_info["domain"],
                "cost": domain_info["price"],
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "cost": domain_info["price"],
        }

    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        result = self.rotate_to_new_domain()
        if result.get("success"):
            return result.get("domain")
        return None

    def cleanup_expired_domains(self, reference_time: Optional[datetime] = None) -> List[str]:
        """
        Remove expired domains and update active domain if needed.
        Returns removed domain names.
        """
        now = reference_time or datetime.now()
        removed_domains: List[str] = []
        retained_domains: List[Dict] = []

        for domain_entry in self.owned_domains:
            expires_at = domain_entry.get("expires_at")
            if isinstance(expires_at, str):
                try:
                    expires_at = datetime.fromisoformat(expires_at)
                except ValueError:
                    expires_at = None

            if isinstance(expires_at, datetime) and expires_at <= now:
                domain_name = domain_entry.get("domain")
                if domain_name:
                    removed_domains.append(domain_name)
                continue

            retained_domains.append(domain_entry)

        self.owned_domains = retained_domains

        if self.active_domain in removed_domains:
            self.active_domain = retained_domains[-1]["domain"] if retained_domains else None

        return removed_domains
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return self.owned_domains
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        monthly_budget = self.monthly_budget
        spending_ratio = 0.0 if monthly_budget <= 0 else self.current_spending / monthly_budget
        return {
            "monthly_budget": monthly_budget,
            "current_spending": self.current_spending,
            "remaining": monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "spending_ratio": spending_ratio,
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
