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
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.active_provider: str = "porkbun"
        self.test_mode = False
        self._config: Dict[str, Any] = {
            "provider": self.active_provider,
            "api_key": None,
            "secret_key": None
        }
        if api_client:
            self.api_clients[self.active_provider] = api_client
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.api_clients[self.active_provider] = api_client

    def add_api_client(self, name: str, api_client: DomainAPIClient):
        """Register an API client under a provider name"""
        if not name:
            raise ValueError("Provider name is required")
        self.api_clients[name] = api_client
        # Keep currently active provider unless no client is active yet
        if self.api_client is None:
            self.active_provider = name
            self.api_client = api_client

    def set_active_provider(self, name: str) -> bool:
        """Switch active provider when a registered client exists"""
        if name not in self.api_clients:
            return False
        self.active_provider = name
        self.api_client = self.api_clients[name]
        self._config["provider"] = name
        return True

    def set_test_mode(self, enabled: bool):
        """Enable simulated purchases without registrar charges"""
        self.test_mode = bool(enabled)

    def configure(self, api_key: str, secret_key: Optional[str] = None,
                  api_secret: Optional[str] = None,
                  monthly_budget: Optional[float] = None,
                  provider: str = "porkbun") -> bool:
        """
        Configure registrar credentials and budget.
        Keeps credentials in memory only.
        """
        effective_secret = secret_key or api_secret
        if not api_key or not effective_secret:
            raise ValueError("Both api_key and secret_key are required")
        if provider != "porkbun":
            raise ValueError(f"Unsupported provider: {provider}")

        client = PorkbunAPIClient(api_key=api_key, api_secret=effective_secret)
        self.active_provider = provider
        self.api_client = client
        self.api_clients[provider] = client

        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        self._config = {
            "provider": provider,
            "api_key": api_key,
            "secret_key": effective_secret
        }
        return True

    def get_config(self) -> Dict[str, Any]:
        """Get current domain manager configuration (masked for display)"""
        api_key = self._config.get("api_key")
        secret_key = self._config.get("secret_key")
        return {
            "provider": self.active_provider,
            "configured": self.api_client is not None,
            "api_key_masked": self._mask_secret(api_key),
            "secret_key_masked": self._mask_secret(secret_key),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode
        }

    @staticmethod
    def _mask_secret(value: Optional[str]) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * (len(value) - 4)}{value[-4:]}"

    @staticmethod
    def _normalize_price(price: Any) -> Optional[float]:
        """Parse registrar price values like '$2.99' into float."""
        if price is None:
            return None
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            cleaned = price.strip().replace("$", "").replace("€", "").replace(",", "")
            if not cleaned:
                return None
            try:
                return float(cleaned)
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
                price = self._normalize_price(result.get("price"))
                if price is None:
                    continue
                if price <= max_price:
                    return {
                        "domain": result.get("domain", domain),
                        "price": price,
                        "tld": tld
                    }
        
        return None

    def search_cheap_domains(self, tlds: Optional[List[str]] = None,
                             max_price: float = 5.0, limit: int = 5,
                             max_attempts: int = 30) -> List[Dict]:
        """
        Search for multiple available cheap domains without purchasing.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return []
        if limit <= 0:
            return []

        candidate_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        seen = set()
        matches: List[Dict] = []
        attempts = 0

        while attempts < max_attempts and len(matches) < limit:
            attempts += 1
            tld = random.choice(candidate_tlds)
            domain = self.generate_random_domain(tld)
            if domain in seen:
                continue
            seen.add(domain)

            result = self.api_client.search_domain(domain)
            if not result.get("available"):
                continue

            price = self._normalize_price(result.get("price"))
            if price is None or price > max_price:
                continue

            matches.append({
                "domain": result.get("domain", domain),
                "price": price,
                "tld": tld
            })

        return sorted(matches, key=lambda item: item["price"])
    
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
    
    def rotate_domain(self, max_price: float = 5.0) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        
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

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Public API used by docs/routes: rotate and return structured result.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain"
            }

        if self.test_mode:
            self.active_domain = domain_info["domain"]
            return {
                "success": True,
                "domain": domain_info["domain"],
                "cost": domain_info["price"],
                "message": "Test mode enabled; no purchase performed"
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"]
        )
        if not success:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded",
                "domain": domain_info["domain"],
                "cost": domain_info["price"]
            }

        return {
            "success": True,
            "domain": domain_info["domain"],
            "cost": domain_info["price"]
        }
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return list(self.owned_domains)
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }

    def configure_domain_dns(self, domain: str, mx_records: Optional[List[Dict]] = None,
                             a_records: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Placeholder DNS integration hook.
        DNS writes are provider-specific and not yet implemented.
        """
        if not domain:
            return {"success": False, "error": "Domain is required"}
        if self.api_client is None:
            return {"success": False, "error": "No API client configured"}
        return {
            "success": False,
            "error": "DNS configuration is not supported by current provider implementation",
            "domain": domain,
            "mx_records": mx_records or [],
            "a_records": a_records or []
        }

    def export_state(self) -> Dict[str, Any]:
        """Export a JSON-safe state snapshot for CLI persistence."""
        exported_domains = []
        for record in self.owned_domains:
            exported = dict(record)
            purchased_at = exported.get("purchased_at")
            expires_at = exported.get("expires_at")
            if isinstance(purchased_at, datetime):
                exported["purchased_at"] = purchased_at.isoformat()
            if isinstance(expires_at, datetime):
                exported["expires_at"] = expires_at.isoformat()
            exported_domains.append(exported)

        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "owned_domains": exported_domains
        }

    def import_state(self, state: Dict[str, Any]):
        """Load previously exported state from JSON-safe data."""
        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))
        self.current_spending = float(state.get("current_spending", 0.0))
        self.active_domain = state.get("active_domain")

        restored_domains = []
        for record in state.get("owned_domains", []):
            if not isinstance(record, dict):
                continue
            restored = dict(record)
            for key in ("purchased_at", "expires_at"):
                value = restored.get(key)
                if isinstance(value, str):
                    try:
                        restored[key] = datetime.fromisoformat(value)
                    except ValueError:
                        restored[key] = datetime.now()
            restored_domains.append(restored)

        self.owned_domains = restored_domains


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
