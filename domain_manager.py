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

    def list_domains(self) -> List[str]:
        """List owned domains if the registrar supports it"""
        return []


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
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
    
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
        return self.owned_domains
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Parse datetime values from runtime objects or ISO strings."""
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            return None

        candidate = value.strip()
        if not candidate:
            return None

        # Accept both explicit offsets and trailing "Z" UTC notation.
        if candidate.endswith("Z"):
            candidate = f"{candidate[:-1]}+00:00"

        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None

    @staticmethod
    def _serialize_datetime(value: Any) -> Optional[str]:
        """Convert datetime-like values to ISO strings for JSON storage."""
        parsed = DomainRotationManager._parse_datetime(value)
        return parsed.isoformat() if parsed else None

    def export_state(self) -> Dict[str, Any]:
        """
        Export manager state as JSON-serializable data.
        Datetime values are normalized to ISO 8601 strings.
        """
        serialized_domains: List[Dict[str, Any]] = []
        for domain_info in self.owned_domains:
            if not isinstance(domain_info, dict):
                continue
            record = dict(domain_info)
            record["purchased_at"] = self._serialize_datetime(record.get("purchased_at"))
            record["expires_at"] = self._serialize_datetime(record.get("expires_at"))
            serialized_domains.append(record)

        return {
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain
        }

    def load_state(self, state: Optional[Dict[str, Any]]) -> None:
        """
        Load persisted manager state.
        Handles both ISO datetime strings and in-memory datetime objects.
        """
        if not isinstance(state, dict):
            return

        current_spending = state.get("current_spending", 0.0)
        try:
            self.current_spending = float(current_spending)
        except (TypeError, ValueError):
            self.current_spending = 0.0

        loaded_domains: List[Dict[str, Any]] = []
        for item in state.get("owned_domains", []) or []:
            if not isinstance(item, dict):
                continue
            domain_name = item.get("domain")
            if not domain_name:
                continue

            record = dict(item)
            record["purchased_at"] = self._parse_datetime(record.get("purchased_at"))
            record["expires_at"] = self._parse_datetime(record.get("expires_at"))

            price = record.get("price")
            if isinstance(price, str):
                try:
                    record["price"] = float(price.replace("$", "").replace("€", "").strip())
                except ValueError:
                    pass

            loaded_domains.append(record)

        self.owned_domains = loaded_domains

        active_domain = state.get("active_domain")
        self.active_domain = active_domain if isinstance(active_domain, str) else None

        domain_names = {d.get("domain") for d in self.owned_domains if isinstance(d, dict)}
        if self.active_domain and self.active_domain not in domain_names:
            self.active_domain = None
        if not self.active_domain and self.owned_domains:
            self.active_domain = self.owned_domains[0].get("domain")

    def cleanup_expired_domains(self, reference_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Remove locally tracked domains that have expired.
        Returns a summary with removed domain names and remaining totals.
        """
        now = reference_time or datetime.now()
        kept_domains: List[Dict[str, Any]] = []
        removed_domains: List[str] = []

        for domain_info in self.owned_domains:
            if not isinstance(domain_info, dict):
                continue

            expires_at = self._parse_datetime(domain_info.get("expires_at"))
            expired = False
            if expires_at:
                # Handle mixed tz-aware / tz-naive values safely.
                if (expires_at.tzinfo is None) == (now.tzinfo is None):
                    expired = expires_at <= now
                else:
                    expired = expires_at.timestamp() <= now.timestamp()

            if expired:
                name = domain_info.get("domain")
                if name:
                    removed_domains.append(name)
                continue

            normalized = dict(domain_info)
            normalized["purchased_at"] = self._parse_datetime(normalized.get("purchased_at"))
            normalized["expires_at"] = expires_at
            kept_domains.append(normalized)

        self.owned_domains = kept_domains

        if self.active_domain in removed_domains:
            self.active_domain = kept_domains[0]["domain"] if kept_domains else None

        return {
            "removed_count": len(removed_domains),
            "removed_domains": removed_domains,
            "remaining_count": len(self.owned_domains),
            "active_domain": self.active_domain
        }

    def sync_owned_domains(self) -> Dict[str, Any]:
        """
        Sync local owned-domain state with the registrar account.
        Adds newly discovered remote domains to local state.
        """
        if not self.api_client:
            return {"success": False, "message": "No API client configured", "added_domains": []}

        if not hasattr(self.api_client, "list_domains"):
            return {
                "success": False,
                "message": "Configured API client does not support domain listing",
                "added_domains": []
            }

        try:
            remote_domains = self.api_client.list_domains()
        except Exception as exc:
            logger.error(f"Failed to sync domains: {exc}")
            return {"success": False, "message": str(exc), "added_domains": []}

        if not isinstance(remote_domains, list):
            return {
                "success": False,
                "message": "Registrar returned an invalid domain list",
                "added_domains": []
            }

        existing_domains = {
            item.get("domain")
            for item in self.owned_domains
            if isinstance(item, dict) and item.get("domain")
        }
        added_domains: List[str] = []

        for domain in remote_domains:
            if not isinstance(domain, str) or not domain.strip():
                continue
            normalized_domain = domain.strip()
            if normalized_domain in existing_domains:
                continue
            self.owned_domains.append({
                "domain": normalized_domain,
                "price": None,
                "purchased_at": None,
                "expires_at": None,
                "source": "remote_sync"
            })
            existing_domains.add(normalized_domain)
            added_domains.append(normalized_domain)

        if not self.active_domain and self.owned_domains:
            self.active_domain = self.owned_domains[0].get("domain")

        return {
            "success": True,
            "remote_total": len(remote_domains),
            "added_count": len(added_domains),
            "added_domains": added_domains,
            "local_total": len(self.owned_domains),
            "active_domain": self.active_domain
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
