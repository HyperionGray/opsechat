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
    
    DEFAULT_CHEAP_TLDS = ["xyz", "club", "online", "site", "website"]

    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    @staticmethod
    def _parse_price(raw_price: Any, fallback: float = 999.0) -> float:
        """Normalize price values from APIs and forms into a float."""
        if isinstance(raw_price, (int, float)):
            return float(raw_price)

        if isinstance(raw_price, str):
            # Keep only numeric characters and decimal separators.
            normalized = "".join(ch for ch in raw_price if ch.isdigit() or ch in ".-")
            if not normalized:
                return fallback
            try:
                return float(normalized)
            except ValueError:
                return fallback

        return fallback
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"
    
    def find_cheap_available_domain(self, max_price: float = 5.0,
                                    max_attempts: int = 10,
                                    tlds: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        cheap_tlds = tlds or self.DEFAULT_CHEAP_TLDS

        if not self.api_client:
            if self.test_mode:
                tld = random.choice(cheap_tlds)
                return {
                    "domain": self.generate_random_domain(tld),
                    "price": 0.0,
                    "tld": tld,
                    "simulated": True
                }
            logger.error("No API client configured")
            return None

        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            result = self.api_client.search_domain(domain)

            if result.get("available"):
                price = self._parse_price(
                    result.get("price"),
                    fallback=max_price + 1.0
                )
                if price <= max_price:
                    return {
                        "domain": result.get("domain", domain),
                        "price": price,
                        "tld": tld
                    }

        return None

    def search_cheap_domains(self, tlds: Optional[List[str]] = None,
                             max_price: float = 5.0,
                             limit: int = 10) -> List[Dict]:
        """
        Search for multiple available domains under a target price.
        Returns up to `limit` unique domain candidates.
        """
        if limit <= 0:
            return []

        results: List[Dict] = []
        seen = set()
        attempt_budget = max(limit * 6, 10)

        while len(results) < limit and attempt_budget > 0:
            candidate = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=tlds
            )
            attempt_budget -= 1

            if not candidate:
                continue

            domain_name = candidate.get("domain")
            if not domain_name or domain_name in seen:
                continue

            seen.add(domain_name)
            results.append(candidate)

        return results

    def _build_owned_domain_entry(self, domain: str, price: float,
                                  simulated: bool = False) -> Dict[str, Any]:
        purchased_at = datetime.now()
        entry: Dict[str, Any] = {
            "domain": domain,
            "price": price,
            "purchased_at": purchased_at,
            "expires_at": purchased_at + timedelta(days=365)
        }
        if simulated:
            entry["simulated"] = True
        return entry
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False
        
        price = self._parse_price(price, fallback=999.0)

        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append(self._build_owned_domain_entry(domain, price))
            
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
        Rotate to a new domain and return a structured result object.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find an available domain within budget constraints."
            }

        domain_name = domain_info["domain"]
        domain_price = self._parse_price(domain_info.get("price"), fallback=max_price + 1.0)

        if self.test_mode:
            self.owned_domains.append(
                self._build_owned_domain_entry(domain_name, domain_price, simulated=True)
            )
            self.active_domain = domain_name
            return {
                "success": True,
                "domain": domain_name,
                "cost": domain_price,
                "simulated": True,
                "message": "Domain rotation simulated in test mode."
            }

        success = self.purchase_domain_if_budget_allows(domain_name, domain_price)
        if not success:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded.",
                "domain": domain_name,
                "cost": domain_price
            }

        self.active_domain = domain_name
        return {
            "success": True,
            "domain": domain_name,
            "cost": domain_price,
            "simulated": False,
            "message": "Domain rotated successfully."
        }
    
    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        result = self.rotate_to_new_domain()
        if result.get("success"):
            return result.get("domain")
        logger.error(result.get("error", "Could not rotate domain"))
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

    def configure(self, api_key: str, secret_key: str,
                  monthly_budget: float = 50.0) -> Dict[str, Any]:
        """
        Configure the manager with Porkbun credentials and budget.
        """
        if not api_key or not secret_key:
            raise ValueError("Both api_key and secret_key are required")

        budget = float(monthly_budget)
        if budget <= 0:
            raise ValueError("monthly_budget must be greater than 0")

        self.api_client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
        self.monthly_budget = budget
        return self.get_config(mask_secrets=True)

    def get_config(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """
        Return current domain rotation configuration and status.
        """
        api_key = getattr(self.api_client, "api_key", "") if self.api_client else ""
        secret_key = getattr(self.api_client, "api_secret", "") if self.api_client else ""

        def _mask_secret(value: str) -> str:
            if not value:
                return ""
            if len(value) <= 4:
                return "*" * len(value)
            return ("*" * (len(value) - 4)) + value[-4:]

        return {
            "provider": "porkbun",
            "api_configured": bool(api_key and secret_key),
            "api_key": _mask_secret(api_key) if mask_secrets else api_key,
            "secret_key": _mask_secret(secret_key) if mask_secrets else secret_key,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode
        }

    def set_test_mode(self, enabled: bool = True):
        """Enable or disable simulation mode for purchases."""
        self.test_mode = bool(enabled)

    def get_state(self) -> Dict[str, Any]:
        """
        Export mutable manager state in JSON-serializable form.
        """
        serialized_domains = []
        for domain in self.owned_domains:
            entry = dict(domain)
            for field in ("purchased_at", "expires_at"):
                value = entry.get(field)
                if isinstance(value, datetime):
                    entry[field] = value.isoformat()
            serialized_domains.append(entry)

        return {
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain
        }

    def load_state(self, state: Optional[Dict[str, Any]]):
        """
        Load manager state exported by get_state.
        Invalid entries are ignored safely.
        """
        if not state:
            return

        self.current_spending = self._parse_price(
            state.get("current_spending", 0.0),
            fallback=0.0
        )
        self.active_domain = state.get("active_domain")

        loaded_domains: List[Dict[str, Any]] = []
        for raw_domain in state.get("owned_domains", []):
            if not isinstance(raw_domain, dict):
                continue

            entry = dict(raw_domain)
            for field in ("purchased_at", "expires_at"):
                value = entry.get(field)
                if isinstance(value, str):
                    try:
                        entry[field] = datetime.fromisoformat(value)
                    except ValueError:
                        # Keep original value if format is unknown.
                        pass
            loaded_domains.append(entry)

        self.owned_domains = loaded_domains


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
