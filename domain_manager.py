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
        ...
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        ...
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        ...


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
    
    STATE_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"

    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.last_budget_reset = self._current_budget_cycle()
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    @staticmethod
    def _parse_price(raw_price) -> Optional[float]:
        """Normalize registrar price values into a float."""
        if isinstance(raw_price, (int, float)):
            return float(raw_price)

        if isinstance(raw_price, str):
            normalized = raw_price.strip().replace(",", "")
            for symbol in ("$", "€", "£"):
                normalized = normalized.replace(symbol, "")

            if not normalized:
                return None

            try:
                return float(normalized)
            except ValueError:
                return None

        return None

    @staticmethod
    def _current_budget_cycle() -> str:
        """Return budget cycle key as YYYY-MM in UTC."""
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _ensure_budget_cycle(self):
        """Reset monthly spend automatically when the month changes."""
        current_cycle = self._current_budget_cycle()

        if self.last_budget_reset != current_cycle:
            logger.info(
                "Resetting monthly domain budget usage: %s -> %s",
                self.last_budget_reset,
                current_cycle
            )
            self.current_spending = 0.0
            self.last_budget_reset = current_cycle

    @classmethod
    def _serialize_datetime(cls, value: datetime) -> str:
        return value.strftime(cls.STATE_DATETIME_FORMAT)

    @classmethod
    def _deserialize_datetime(cls, value, default: Optional[datetime] = None) -> datetime:
        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
            try:
                return datetime.strptime(value, cls.STATE_DATETIME_FORMAT)
            except ValueError:
                pass

        return default or datetime.now()

    def _serialize_domain_record(self, record: Dict) -> Optional[Dict]:
        domain = str(record.get("domain", "")).strip()
        if not domain:
            return None

        price = self._parse_price(record.get("price"))
        purchased_at = self._deserialize_datetime(record.get("purchased_at"), default=datetime.now())
        expires_at = self._deserialize_datetime(
            record.get("expires_at"),
            default=purchased_at + timedelta(days=365)
        )

        serialized = {
            "domain": domain,
            "price": 0.0 if price is None else price,
            "purchased_at": self._serialize_datetime(purchased_at),
            "expires_at": self._serialize_datetime(expires_at)
        }

        order_id = record.get("order_id")
        if order_id:
            serialized["order_id"] = order_id

        return serialized

    def _deserialize_domain_record(self, record: Dict) -> Optional[Dict]:
        domain = str(record.get("domain", "")).strip()
        if not domain:
            return None

        price = self._parse_price(record.get("price"))
        purchased_at = self._deserialize_datetime(record.get("purchased_at"), default=datetime.now())
        expires_at = self._deserialize_datetime(
            record.get("expires_at"),
            default=purchased_at + timedelta(days=365)
        )

        deserialized = {
            "domain": domain,
            "price": 0.0 if price is None else price,
            "purchased_at": purchased_at,
            "expires_at": expires_at
        }

        order_id = record.get("order_id")
        if order_id:
            deserialized["order_id"] = order_id

        return deserialized

    def export_state(self) -> Dict:
        """
        Export JSON-safe state for persistence.
        """
        self._ensure_budget_cycle()
        serialized_domains = []
        for record in self.owned_domains:
            serialized = self._serialize_domain_record(record)
            if serialized:
                serialized_domains.append(serialized)

        return {
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "last_budget_reset": self.last_budget_reset
        }

    def restore_state(self, state: Optional[Dict]):
        """
        Restore manager state from persisted config.
        Handles old and mixed-format records safely.
        """
        if not state:
            return

        spending = self._parse_price(state.get("current_spending"))
        self.current_spending = 0.0 if spending is None else spending

        active_domain = state.get("active_domain")
        self.active_domain = str(active_domain).strip() if active_domain else None

        raw_cycle = state.get("last_budget_reset")
        self.last_budget_reset = str(raw_cycle) if raw_cycle else self._current_budget_cycle()

        self.owned_domains = []
        for record in (state.get("owned_domains") or []):
            if isinstance(record, dict):
                parsed = self._deserialize_domain_record(record)
                if parsed:
                    self.owned_domains.append(parsed)

        self._ensure_budget_cycle()
    
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
                price = self._parse_price(result.get("price"))
                if price is None:
                    logger.warning("Skipping %s due to unparseable price: %r", domain, result.get("price"))
                    continue
                
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
        
        normalized_price = self._parse_price(price)
        if normalized_price is None:
            logger.error("Invalid domain price: %r", price)
            return False

        self._ensure_budget_cycle()

        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            purchased_at = datetime.now()
            self.current_spending += normalized_price
            self.owned_domains.append({
                "domain": domain,
                "price": normalized_price,
                "purchased_at": purchased_at,
                "expires_at": purchased_at + timedelta(days=365),
                "order_id": result.get("order_id")
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${normalized_price}")
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
        return self.owned_domains
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        self._ensure_budget_cycle()
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
