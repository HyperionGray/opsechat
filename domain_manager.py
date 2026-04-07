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

    @staticmethod
    def _coerce_datetime(value: Optional[object]) -> Optional[datetime]:
        """Convert persisted datetime values to datetime objects."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                logger.warning("Invalid datetime string in domain state: %s", value)
                return None
        return None

    @staticmethod
    def _datetime_to_iso(value: Optional[datetime]) -> Optional[str]:
        """Convert datetime to ISO8601 string for JSON persistence."""
        if value is None:
            return None
        return value.isoformat()

    def _mark_active_domain(self, domain: Optional[str]) -> None:
        """Synchronize per-domain active flags with active_domain pointer."""
        self.active_domain = domain
        for entry in self.owned_domains:
            entry["active"] = bool(domain and entry.get("domain") == domain)

    def _is_domain_expired(self, domain_entry: Dict, now: Optional[datetime] = None) -> bool:
        """Return True when a domain record is expired."""
        expires_at = self._coerce_datetime(domain_entry.get("expires_at"))
        if expires_at is None:
            return False
        current_time = now or datetime.now()
        return expires_at <= current_time

    def serialize_state(self) -> Dict:
        """
        Export a JSON-serializable manager state dictionary.
        """
        serialized_domains: List[Dict] = []
        for domain in self.owned_domains:
            serialized_domains.append({
                "domain": domain.get("domain"),
                "price": domain.get("price"),
                "purchased_at": self._datetime_to_iso(
                    self._coerce_datetime(domain.get("purchased_at"))
                ),
                "expires_at": self._datetime_to_iso(
                    self._coerce_datetime(domain.get("expires_at"))
                ),
                "active": bool(domain.get("active", False)),
            })

        return {
            "current_spending": float(self.current_spending),
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
        }

    def load_state(self, state: Optional[Dict]) -> None:
        """
        Load manager state from a persisted dictionary.
        """
        state = state or {}

        try:
            self.current_spending = float(state.get("current_spending", 0.0))
        except (TypeError, ValueError):
            logger.warning("Invalid current_spending in domain state, defaulting to 0")
            self.current_spending = 0.0

        loaded_domains: List[Dict] = []
        for raw in state.get("owned_domains", []) or []:
            if not isinstance(raw, dict):
                continue
            domain_name = raw.get("domain")
            if not domain_name:
                continue
            loaded_domains.append({
                "domain": domain_name,
                "price": raw.get("price", 0.0),
                "purchased_at": self._coerce_datetime(raw.get("purchased_at")),
                "expires_at": self._coerce_datetime(raw.get("expires_at")),
                "active": bool(raw.get("active", False)),
            })

        self.owned_domains = loaded_domains

        persisted_active = state.get("active_domain")
        if persisted_active and any(d.get("domain") == persisted_active for d in self.owned_domains):
            self._mark_active_domain(persisted_active)
        else:
            active_from_record = next(
                (d.get("domain") for d in self.owned_domains if d.get("active")),
                None,
            )
            self._mark_active_domain(active_from_record)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> None:
        """
        Configure manager with Porkbun credentials and monthly budget.
        """
        self.set_api_client(PorkbunAPIClient(api_key, secret_key))
        self.monthly_budget = float(monthly_budget)

    def get_config(self) -> Dict:
        """
        Return non-sensitive configuration details for UI display.
        """
        api_key_suffix = ""
        if self.api_client and getattr(self.api_client, "api_key", ""):
            api_key_suffix = str(self.api_client.api_key)[-4:]
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "api_key_suffix": api_key_suffix,
            "configured": self.api_client is not None,
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
                "expires_at": datetime.now() + timedelta(days=365),
                "active": False,
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self._mark_active_domain(domain)
            
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False

    def activate_domain(self, domain: str) -> bool:
        """Set an owned domain as active if it exists and is not expired."""
        exists = False
        for owned_domain in self.owned_domains:
            if owned_domain.get("domain") == domain:
                exists = True
                if self._is_domain_expired(owned_domain):
                    logger.warning("Cannot activate expired domain: %s", domain)
                    return False
                self._mark_active_domain(domain)
                return True

        if not exists:
            logger.warning("Cannot activate unknown domain: %s", domain)
        return False

    def deactivate_domain(self, domain: str) -> bool:
        """
        Deactivate a domain.

        If the domain is currently active, this will promote the newest non-expired
        remaining domain if one exists, or clear active_domain otherwise.
        """
        if not any(item.get("domain") == domain for item in self.owned_domains):
            logger.warning("Cannot deactivate unknown domain: %s", domain)
            return False

        for item in self.owned_domains:
            if item.get("domain") == domain:
                item["active"] = False

        if self.active_domain != domain:
            return True

        candidate_domains = [
            d.get("domain")
            for d in self.owned_domains
            if d.get("domain") != domain and not self._is_domain_expired(d)
        ]
        self._mark_active_domain(candidate_domains[-1] if candidate_domains else None)
        return True

    def cleanup_expired_domains(self) -> List[str]:
        """
        Remove expired domains from owned list and return removed domain names.
        """
        now = datetime.now()
        removed: List[str] = []
        remaining: List[Dict] = []

        for domain_entry in self.owned_domains:
            if self._is_domain_expired(domain_entry, now=now):
                removed.append(domain_entry.get("domain", ""))
            else:
                remaining.append(domain_entry)

        self.owned_domains = remaining

        if self.active_domain and not any(d.get("domain") == self.active_domain for d in remaining):
            self._mark_active_domain(None)
        elif self.active_domain:
            self._mark_active_domain(self.active_domain)

        return [domain for domain in removed if domain]
    
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
            self._mark_active_domain(domain_info["domain"])
            return self.active_domain
        
        return None
    
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
