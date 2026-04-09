"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

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
        # API credentials stored internally only - not exposed via get_config()
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 50.0) -> bool:
        """Configure registrar credentials and budget."""
        self._api_key = api_key.strip() or None
        self._api_secret = secret_key.strip() or None
        self.monthly_budget = float(monthly_budget)

        if not self._api_key or not self._api_secret:
            self.api_client = None
            return False

        self.api_client = PorkbunAPIClient(self._api_key, self._api_secret)
        return True

    def get_config(self) -> Dict:
        """Return safe configuration details for UI/API use."""
        return {
            "configured": self.api_client is not None,
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            "current_spending": self.current_spending,
            "domains_owned": len(self.owned_domains),
            # API key presence intentionally omitted for security
        }

    @staticmethod
    def _normalize_price(price: Any) -> Optional[float]:
        """Normalize registrar price values into a float."""
        if isinstance(price, (int, float)):
            return float(price)

        if isinstance(price, str):
            cleaned = price.replace("$", "").replace("€", "").replace(",", "").strip()
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None

        return None

    @staticmethod
    def _serialize_datetime(value: Any) -> Optional[str]:
        """Convert datetime to ISO-8601 string if possible."""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Parse ISO-8601 strings into datetime values."""
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
        candidates = self.search_available_domains(
            max_price=max_price,
            max_attempts=max_attempts,
            max_results=1,
        )
        return candidates[0] if candidates else None

    def search_available_domains(
        self,
        max_price: float = 5.0,
        max_attempts: int = 20,
        max_results: int = 5,
        tlds: Optional[List[str]] = None,
        exclude_owned: bool = True,
    ) -> List[Dict]:
        """
        Search for multiple cheap and available domains.

        Returns a list sorted by lowest price first.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return []

        tld_pool = tlds or self.CHEAP_TLDS
        seen_domains = set()
        owned_domains = {
            item.get("domain")
            for item in self.owned_domains
            if isinstance(item, dict) and item.get("domain")
        } if exclude_owned else set()

        candidates: List[Dict] = []

        for _ in range(max_attempts):
            if len(candidates) >= max_results:
                break

            tld = random.choice(tld_pool)
            generated_domain = self.generate_random_domain(tld)
            if generated_domain in seen_domains or generated_domain in owned_domains:
                continue

            seen_domains.add(generated_domain)
            result = self.api_client.search_domain(generated_domain)
            if not result.get("available"):
                continue

            resolved_domain = result.get("domain") or generated_domain
            if resolved_domain in owned_domains:
                continue

            normalized_price = self._normalize_price(result.get("price"))
            if normalized_price is None or normalized_price > max_price:
                continue

            candidates.append({
                "domain": resolved_domain,
                "price": normalized_price,
                "tld": tld,
                "currency": result.get("currency", "USD"),
            })

        return sorted(candidates, key=lambda item: item["price"])
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> Dict:
        """
        Purchase domain if within budget
        Returns structured result
        """
        if not self.api_client:
            logger.error("No API client configured")
            return {
                "success": False,
                "domain": domain,
                "message": "No API client configured",
            }
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return {
                "success": False,
                "domain": domain,
                "message": "Budget exceeded",
                "budget_status": self.get_budget_status(),
            }
        
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
            return {
                "success": True,
                "domain": domain,
                "price": price,
                "message": "Domain purchased successfully",
                "active_domain": self.active_domain,
                "budget_status": self.get_budget_status(),
            }
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Failed to purchase domain"),
                "budget_status": self.get_budget_status(),
            }
    
    def rotate_domain(self) -> Dict:
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
                "message": "Could not find available cheap domain",
                "budget_status": self.get_budget_status(),
            }
        
        # Purchase domain
        result = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )
        
        if result.get("success"):
            self.active_domain = domain_info["domain"]
            result["active_domain"] = self.active_domain

        return result
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return self.owned_domains

    def export_state(self) -> Dict[str, Any]:
        """Export manager state in a JSON-serializable format."""
        serialized_domains = []
        for item in self.owned_domains:
            if not isinstance(item, dict):
                continue
            serialized_domains.append({
                "domain": item.get("domain"),
                "price": self._normalize_price(item.get("price")) or 0.0,
                "purchased_at": self._serialize_datetime(item.get("purchased_at")),
                "expires_at": self._serialize_datetime(item.get("expires_at")),
            })

        return {
            "monthly_budget": float(self.monthly_budget),
            "current_spending": float(self.current_spending),
            "active_domain": self.active_domain,
            "owned_domains": serialized_domains,
        }

    def load_state(self, state: Optional[Dict[str, Any]]) -> None:
        """Load manager state from a serialized dictionary."""
        if not state:
            return

        if state.get("monthly_budget") is not None:
            self.monthly_budget = float(state.get("monthly_budget"))
        if state.get("current_spending") is not None:
            self.current_spending = float(state.get("current_spending"))
        self.active_domain = state.get("active_domain") or None

        parsed_domains: List[Dict] = []
        for item in state.get("owned_domains", []) or []:
            if not isinstance(item, dict):
                continue
            parsed_domains.append({
                "domain": item.get("domain"),
                "price": self._normalize_price(item.get("price")) or 0.0,
                "purchased_at": self._parse_datetime(item.get("purchased_at")),
                "expires_at": self._parse_datetime(item.get("expires_at")),
            })

        self.owned_domains = parsed_domains

        if not self.active_domain and parsed_domains:
            # Keep state coherent if active domain wasn't stored.
            self.active_domain = parsed_domains[-1].get("domain")
    
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
