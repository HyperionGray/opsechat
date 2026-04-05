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
        raise NotImplementedError()
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError()
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError()


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
    def _parse_datetime(value: Any, fallback: Optional[datetime] = None) -> datetime:
        """Parse datetime values from persisted state safely."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return fallback or datetime.now()

    @staticmethod
    def _serialize_datetime(value: Any) -> str:
        """Serialize datetime values for JSON persistence."""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return datetime.now().isoformat()
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def configure(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        monthly_budget: float = 50.0,
    ) -> Dict[str, Any]:
        """
        Configure Porkbun API client and budget settings.
        Returns a status dictionary for UI/API callers.
        """
        if not api_key or not secret_key:
            raise ValueError("API key and secret key are required")
        if monthly_budget <= 0:
            raise ValueError("Monthly budget must be greater than 0")

        self.api_client = PorkbunAPIClient(api_key, secret_key)
        self.monthly_budget = float(monthly_budget)

        return self.get_config()
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def prune_expired_domains(self, now: Optional[datetime] = None) -> int:
        """
        Remove expired domains from local state.
        Returns number of removed domains.
        """
        now = now or datetime.now()
        active_before = self.active_domain

        kept_domains: List[Dict[str, Any]] = []
        removed = 0

        for domain_info in self.owned_domains:
            expires_at = self._parse_datetime(
                domain_info.get("expires_at"),
                fallback=now + timedelta(days=365),
            )
            if expires_at <= now:
                removed += 1
                continue

            normalized = dict(domain_info)
            normalized["purchased_at"] = self._parse_datetime(
                domain_info.get("purchased_at"),
                fallback=now,
            )
            normalized["expires_at"] = expires_at
            kept_domains.append(normalized)

        self.owned_domains = kept_domains

        valid_domains = {entry.get("domain") for entry in kept_domains}
        if self.active_domain not in valid_domains:
            self.active_domain = kept_domains[-1]["domain"] if kept_domains else None

        if removed:
            logger.info(
                "Pruned %s expired domains (active before=%s, active now=%s)",
                removed,
                active_before,
                self.active_domain,
            )

        return removed

    def export_state(self) -> Dict[str, Any]:
        """Export manager state in JSON-serializable format."""
        serialized_domains = []
        for domain_info in self.owned_domains:
            entry = dict(domain_info)
            entry["purchased_at"] = self._serialize_datetime(entry.get("purchased_at"))
            entry["expires_at"] = self._serialize_datetime(entry.get("expires_at"))
            serialized_domains.append(entry)

        return {
            "monthly_budget": float(self.monthly_budget),
            "current_spending": float(self.current_spending),
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
        }

    def load_state(self, state: Optional[Dict[str, Any]], prune_expired: bool = True) -> int:
        """
        Load persisted state into the manager.
        Returns number of domains pruned as expired.
        """
        if not state:
            return 0

        monthly_budget = state.get("monthly_budget")
        if monthly_budget is not None:
            try:
                self.monthly_budget = float(monthly_budget)
            except (TypeError, ValueError):
                logger.warning("Invalid monthly_budget in state: %r", monthly_budget)

        current_spending = state.get("current_spending")
        if current_spending is not None:
            try:
                self.current_spending = float(current_spending)
            except (TypeError, ValueError):
                logger.warning("Invalid current_spending in state: %r", current_spending)
                self.current_spending = 0.0

        loaded_domains: List[Dict[str, Any]] = []
        now = datetime.now()
        for raw_entry in state.get("owned_domains", []):
            domain_name = raw_entry.get("domain")
            if not domain_name:
                continue
            entry = dict(raw_entry)
            entry["purchased_at"] = self._parse_datetime(
                raw_entry.get("purchased_at"),
                fallback=now,
            )
            entry["expires_at"] = self._parse_datetime(
                raw_entry.get("expires_at"),
                fallback=now + timedelta(days=365),
            )

            price = raw_entry.get("price", 0.0)
            try:
                entry["price"] = float(price)
            except (TypeError, ValueError):
                entry["price"] = 0.0

            loaded_domains.append(entry)

        self.owned_domains = loaded_domains
        self.active_domain = state.get("active_domain")

        pruned = self.prune_expired_domains(now=now) if prune_expired else 0
        return pruned

    def reset_monthly_spending(self):
        """Reset tracked monthly spending counter."""
        self.current_spending = 0.0

    def get_config(self) -> Dict[str, Any]:
        """Return domain manager configuration and current status."""
        budget = self.get_budget_status()
        return {
            "configured": self.api_client is not None,
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            "budget_status": budget,
        }
    
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
                    # Remove common currency symbols and whitespace
                    cleaned = price.replace("$", "").replace("€", "").strip()
                    try:
                        price = float(cleaned)
                    except ValueError:
                        logger.warning("Unexpected price format from API: %r", price)
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
    
    def rotate_domain(self) -> Dict[str, Any]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {
                "success": False,
                "error": "Could not find available cheap domain",
                "active_domain": self.active_domain,
            }
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            return {
                "success": True,
                "domain": self.active_domain,
                "price": domain_info["price"],
            }

        return {
            "success": False,
            "error": "Purchase failed or exceeded budget",
            "active_domain": self.active_domain,
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
