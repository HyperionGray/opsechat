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

    @staticmethod
    def _normalize_price(price: Any) -> Optional[float]:
        """Normalize registrar price values to float."""
        if isinstance(price, (int, float)):
            return float(price)

        if isinstance(price, str):
            cleaned = (
                price.strip()
                .replace("$", "")
                .replace("€", "")
                .replace(",", "")
            )
            try:
                return float(cleaned)
            except ValueError:
                return None

        return None

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Parse datetime from persisted values."""
        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
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
                price = self._normalize_price(result.get("price", 999))
                if price is None:
                    logger.warning("Invalid price returned for domain %s", domain)
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

        normalized_price = self._normalize_price(price)
        if normalized_price is None:
            logger.error("Invalid purchase price for %s: %r", domain, price)
            return False
        price = normalized_price
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            now = datetime.now()
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

    def rotate_domain_with_details(self) -> Dict:
        """
        Rotate to a new domain and return structured result details.
        """
        domain_info = self.find_cheap_available_domain()

        if not domain_info:
            return {
                "success": False,
                "domain": None,
                "error": "Could not find available cheap domain",
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"]
        )

        if not success:
            return {
                "success": False,
                "domain": domain_info["domain"],
                "price": domain_info["price"],
                "error": "Purchase failed or budget exceeded",
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "price": domain_info["price"],
        }

    def prune_expired_domains(self, reference_time: Optional[datetime] = None) -> int:
        """
        Remove expired domains from local state.
        Returns the number of pruned domains.
        """
        now = reference_time or datetime.now()
        remaining_domains: List[Dict] = []
        removed_count = 0

        for domain in self.owned_domains:
            normalized = dict(domain)
            purchased_at = self._parse_datetime(normalized.get("purchased_at"))
            expires_at = self._parse_datetime(normalized.get("expires_at"))

            if purchased_at:
                normalized["purchased_at"] = purchased_at
            if expires_at:
                normalized["expires_at"] = expires_at

            if expires_at and expires_at <= now:
                removed_count += 1
                continue

            remaining_domains.append(normalized)

        self.owned_domains = remaining_domains

        if self.active_domain and not any(
            d.get("domain") == self.active_domain for d in self.owned_domains
        ):
            self.active_domain = (
                self.owned_domains[-1].get("domain") if self.owned_domains else None
            )

        return removed_count
    
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

    def export_state(self) -> Dict:
        """Export manager state in JSON-serializable format."""
        serialized_domains = []
        for domain in self.owned_domains:
            item = dict(domain)
            purchased_at = self._parse_datetime(item.get("purchased_at"))
            expires_at = self._parse_datetime(item.get("expires_at"))

            if purchased_at:
                item["purchased_at"] = purchased_at.isoformat()
            if expires_at:
                item["expires_at"] = expires_at.isoformat()

            serialized_domains.append(item)

        return {
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain
        }

    def load_state(self, state: Dict) -> None:
        """Load manager state from persisted JSON-compatible data."""
        if not isinstance(state, dict):
            return

        spending = self._normalize_price(state.get("current_spending", 0.0))
        if spending is not None:
            self.current_spending = spending

        parsed_domains: List[Dict] = []
        for domain in state.get("owned_domains", []):
            if not isinstance(domain, dict):
                continue

            item = dict(domain)
            purchased_at = self._parse_datetime(item.get("purchased_at"))
            expires_at = self._parse_datetime(item.get("expires_at"))
            price = self._normalize_price(item.get("price"))

            if purchased_at:
                item["purchased_at"] = purchased_at
            if expires_at:
                item["expires_at"] = expires_at
            if price is not None:
                item["price"] = price

            parsed_domains.append(item)

        self.owned_domains = parsed_domains

        active_domain = state.get("active_domain")
        if isinstance(active_domain, str) and active_domain:
            self.active_domain = active_domain
        else:
            self.active_domain = None

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> Dict:
        """Configure registrar credentials and budget."""
        if not api_key or not secret_key:
            raise ValueError("API key and secret key are required")

        self.api_client = PorkbunAPIClient(api_key, secret_key)
        self.monthly_budget = float(monthly_budget)
        return self.get_config()

    def get_config(self) -> Dict:
        """Get safe configuration metadata (no secrets)."""
        budget = self.get_budget_status()
        return {
            "configured": self.api_client is not None,
            "monthly_budget": budget["monthly_budget"],
            "current_spending": budget["current_spending"],
            "remaining": budget["remaining"],
            "domains_owned": budget["domains_owned"],
            "active_domain": self.active_domain
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
