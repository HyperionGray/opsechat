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
from datetime import datetime, timedelta, timezone

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
        self.budget_cycle = self._current_budget_cycle()

    @staticmethod
    def _current_budget_cycle(now: Optional[datetime] = None) -> str:
        now = now or datetime.now(timezone.utc)
        return now.strftime("%Y-%m")

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
        parsed = DomainRotationManager._parse_datetime(value)
        if not parsed:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()

    @staticmethod
    def _normalize_domain_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        domain = record.get("domain")
        if not isinstance(domain, str) or not domain:
            return None

        try:
            price = float(record.get("price", 0.0))
        except (TypeError, ValueError):
            price = 0.0

        purchased_at = DomainRotationManager._parse_datetime(record.get("purchased_at"))
        expires_at = DomainRotationManager._parse_datetime(record.get("expires_at"))

        if not purchased_at:
            purchased_at = datetime.now(timezone.utc)
        if not expires_at:
            expires_at = purchased_at + timedelta(days=365)

        if purchased_at.tzinfo is None:
            purchased_at = purchased_at.replace(tzinfo=timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return {
            "domain": domain,
            "price": price,
            "purchased_at": purchased_at,
            "expires_at": expires_at,
        }
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def reset_budget_if_new_cycle(self, now: Optional[datetime] = None) -> bool:
        """
        Reset spending when entering a new monthly budget cycle.
        Returns True when a reset occurs.
        """
        current_cycle = self._current_budget_cycle(now)
        if self.budget_cycle != current_cycle:
            self.current_spending = 0.0
            self.budget_cycle = current_cycle
            logger.info(f"Budget cycle advanced to {current_cycle}; spending reset.")
            return True
        return False
    
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
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False

        self.reset_budget_if_new_cycle()
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            now = datetime.now(timezone.utc)
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365)
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
        return list(self.owned_domains)
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        self.reset_budget_if_new_cycle()
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "budget_cycle": self.budget_cycle,
        }

    def prune_expired_domains(self, now: Optional[datetime] = None) -> List[str]:
        """
        Remove expired domains from local state.
        Returns a list of removed domain names.
        """
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        removed_domains: List[str] = []
        kept_domains: List[Dict] = []

        for record in self.owned_domains:
            normalized = self._normalize_domain_record(record)
            if not normalized:
                continue
            if normalized["expires_at"] < now:
                removed_domains.append(normalized["domain"])
                continue
            kept_domains.append(normalized)

        self.owned_domains = kept_domains

        if self.active_domain and self.active_domain in removed_domains:
            self.active_domain = self.owned_domains[-1]["domain"] if self.owned_domains else None

        return removed_domains

    def to_state(self) -> Dict[str, Any]:
        """
        Return JSON-serializable manager state for persistence.
        """
        serialized_domains: List[Dict[str, Any]] = []
        for record in self.owned_domains:
            normalized = self._normalize_domain_record(record)
            if not normalized:
                continue
            serialized_domains.append({
                "domain": normalized["domain"],
                "price": normalized["price"],
                "purchased_at": self._serialize_datetime(normalized["purchased_at"]),
                "expires_at": self._serialize_datetime(normalized["expires_at"]),
            })

        return {
            "current_spending": float(self.current_spending),
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "budget_cycle": self.budget_cycle,
        }

    def load_state(self, state: Optional[Dict[str, Any]]) -> None:
        """
        Load manager state from persisted JSON-compatible dictionary.
        Invalid records are ignored.
        """
        if not state:
            return

        try:
            self.current_spending = float(state.get("current_spending", 0.0))
        except (TypeError, ValueError):
            self.current_spending = 0.0

        loaded_domains: List[Dict[str, Any]] = []
        for record in state.get("owned_domains", []):
            if not isinstance(record, dict):
                continue
            normalized = self._normalize_domain_record(record)
            if normalized:
                loaded_domains.append(normalized)

        self.owned_domains = loaded_domains

        active = state.get("active_domain")
        self.active_domain = active if isinstance(active, str) and active else None

        budget_cycle = state.get("budget_cycle")
        if isinstance(budget_cycle, str) and budget_cycle:
            self.budget_cycle = budget_cycle
        else:
            self.budget_cycle = self._current_budget_cycle()


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
