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


def _parse_price(price: Any) -> Optional[float]:
    """Parse registrar price values into float USD values."""
    if isinstance(price, (int, float)):
        return float(price)
    if isinstance(price, str):
        cleaned = (
            price.replace("$", "")
            .replace("€", "")
            .replace(",", "")
            .strip()
        )
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _mask_secret(secret: Optional[str]) -> str:
    """Mask a secret value for safe display."""
    if not secret:
        return ""
    if len(secret) <= 4:
        return "*" * len(secret)
    return f"{'*' * (len(secret) - 4)}{secret[-4:]}"


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
                 monthly_budget: float = 50.0,
                 max_domain_price: float = 5.0,
                 cheap_tlds: Optional[List[str]] = None):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.max_domain_price = max_domain_price
        self.cheap_tlds = cheap_tlds or ["xyz", "club", "online", "site", "website"]
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def configure(self, api_key: str, secret_key: str,
                  monthly_budget: float = 50.0,
                  max_domain_price: Optional[float] = None,
                  cheap_tlds: Optional[List[str]] = None) -> Dict:
        """
        Configure registrar credentials and domain policy.
        Returns structured success/error details for route handlers.
        """
        if not api_key or not secret_key:
            return {"success": False, "error": "API key and secret key are required"}

        parsed_budget = _parse_price(monthly_budget)
        if parsed_budget is None or parsed_budget <= 0:
            return {"success": False, "error": "Monthly budget must be a positive number"}

        self.monthly_budget = parsed_budget

        if max_domain_price is not None:
            parsed_max_price = _parse_price(max_domain_price)
            if parsed_max_price is None or parsed_max_price <= 0:
                return {"success": False, "error": "Max domain price must be positive"}
            self.max_domain_price = parsed_max_price

        if cheap_tlds is not None:
            normalized_tlds = [
                tld.strip().lstrip(".").lower()
                for tld in cheap_tlds
                if isinstance(tld, str) and tld.strip()
            ]
            if normalized_tlds:
                self.cheap_tlds = normalized_tlds

        self.set_api_client(PorkbunAPIClient(api_key, secret_key))
        return {"success": True, "config": self.get_config(mask_secrets=True)}

    def get_config(self, mask_secrets: bool = True) -> Dict:
        """Return current domain rotation configuration state."""
        api_key = getattr(self.api_client, "api_key", "")
        api_secret = getattr(self.api_client, "api_secret", "")
        if mask_secrets:
            api_key = _mask_secret(api_key)
            api_secret = _mask_secret(api_secret)

        return {
            "api_configured": self.api_client is not None,
            "api_key": api_key or "",
            "api_secret": api_secret or "",
            "monthly_budget": self.monthly_budget,
            "max_domain_price": self.max_domain_price,
            "cheap_tlds": list(self.cheap_tlds),
            "active_domain": self.active_domain,
            "budget_status": self.get_budget_status(),
        }
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"
    
    def find_cheap_available_domain(self, max_price: Optional[float] = None,
                                   max_attempts: int = 10,
                                   tlds: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_client:
            logger.error("No API client configured")
            return None
        
        max_price = self.max_domain_price if max_price is None else max_price
        parsed_max_price = _parse_price(max_price)
        if parsed_max_price is None:
            logger.error("Invalid max price configured for domain search")
            return None

        candidate_tlds = tlds or self.cheap_tlds
        candidate_tlds = [tld.lstrip(".").lower() for tld in candidate_tlds if tld]
        if not candidate_tlds:
            candidate_tlds = ["xyz", "club", "online", "site", "website"]
        
        for _ in range(max_attempts):
            tld = random.choice(candidate_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = _parse_price(result.get("price"))
                if price is None:
                    logger.warning("Registrar returned unparseable price for %s", domain)
                    continue

                if price <= parsed_max_price:
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
        
        parsed_price = _parse_price(price)
        if parsed_price is None:
            logger.error("Invalid purchase price for domain %s", domain)
            return False

        # Check budget
        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${parsed_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += parsed_price
            self.owned_domains.append({
                "domain": domain,
                "price": parsed_price,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${parsed_price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self, max_price: Optional[float] = None,
                      max_attempts: int = 10,
                      return_details: bool = False):
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        previous_domain = self.active_domain

        # Find cheap domain
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=max_attempts
        )
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            if return_details:
                return {
                    "success": False,
                    "error": "Could not find available cheap domain"
                }
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            if return_details:
                return {
                    "success": True,
                    "domain": self.active_domain,
                    "previous_domain": previous_domain,
                    "price": domain_info["price"],
                    "remaining_budget": self.get_budget_status()["remaining"]
                }
            return self.active_domain
        
        if return_details:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded",
                "domain": domain_info["domain"],
                "price": domain_info["price"]
            }
        return None
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return self.owned_domains
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        remaining = max(self.monthly_budget - self.current_spending, 0.0)
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": remaining,
            "domains_owned": len(self.owned_domains)
        }

    def export_state(self) -> Dict[str, Any]:
        """Export serializable state for persistence."""
        serialized_domains = []
        for domain in self.owned_domains:
            serialized = dict(domain)
            for key in ("purchased_at", "expires_at"):
                if isinstance(serialized.get(key), datetime):
                    serialized[key] = serialized[key].isoformat()
            serialized_domains.append(serialized)

        return {
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "monthly_budget": self.monthly_budget,
            "max_domain_price": self.max_domain_price,
            "cheap_tlds": list(self.cheap_tlds),
        }

    def import_state(self, state: Dict[str, Any]):
        """Load persisted state, accepting both legacy and normalized formats."""
        if not isinstance(state, dict):
            return

        spending = _parse_price(state.get("current_spending"))
        if spending is not None:
            self.current_spending = spending

        budget = _parse_price(state.get("monthly_budget"))
        if budget is not None and budget > 0:
            self.monthly_budget = budget

        max_price = _parse_price(state.get("max_domain_price"))
        if max_price is not None and max_price > 0:
            self.max_domain_price = max_price

        tlds = state.get("cheap_tlds")
        if isinstance(tlds, list):
            normalized_tlds = [
                tld.strip().lstrip(".").lower()
                for tld in tlds
                if isinstance(tld, str) and tld.strip()
            ]
            if normalized_tlds:
                self.cheap_tlds = normalized_tlds

        domains = state.get("owned_domains")
        if isinstance(domains, list):
            normalized_domains: List[Dict[str, Any]] = []
            for domain in domains:
                if not isinstance(domain, dict):
                    continue
                normalized = dict(domain)
                for key in ("purchased_at", "expires_at"):
                    value = normalized.get(key)
                    if isinstance(value, str):
                        try:
                            normalized[key] = datetime.fromisoformat(value)
                        except ValueError:
                            # Keep legacy raw values rather than dropping entries.
                            pass
                normalized_domains.append(normalized)
            self.owned_domains = normalized_domains

        active_domain = state.get("active_domain")
        if isinstance(active_domain, str):
            self.active_domain = active_domain or None


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
