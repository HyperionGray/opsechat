"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

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
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0):
        self.api_client = None
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.primary_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False

        if api_client:
            self.set_api_client(api_client)
    
    def set_api_client(self, api_client: DomainAPIClient, provider_name: str = "default",
                       make_primary: bool = True):
        """Set (or replace) a domain API client"""
        self.api_clients[provider_name] = api_client
        if make_primary or not self.primary_provider or not self.api_client:
            self.primary_provider = provider_name
            self.api_client = api_client

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient,
                       make_primary: bool = False):
        """Add an additional provider for fallback/rotation"""
        if not provider_name:
            raise ValueError("provider_name is required")
        self.set_api_client(api_client, provider_name=provider_name, make_primary=make_primary)

    def set_primary_provider(self, provider_name: str) -> bool:
        """Set the default provider used first during domain rotation"""
        if provider_name not in self.api_clients:
            return False
        self.primary_provider = provider_name
        self.api_client = self.api_clients[provider_name]
        return True

    def set_test_mode(self, enabled: bool = True):
        """Enable dry-run purchases for safer validation"""
        self.test_mode = enabled

    @staticmethod
    def _normalize_price(price: Any) -> Optional[float]:
        """Normalize price payloads from APIs into float values"""
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

    @staticmethod
    def _parse_timestamp(value: Any) -> Any:
        """Parse persisted timestamps into datetime where possible"""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value
        return value

    def _provider_order(self, provider_name: Optional[str] = None) -> List[str]:
        """Get ordered provider names for lookup and fallback"""
        if provider_name:
            return [provider_name]

        if not self.api_clients and self.api_client:
            self.api_clients["default"] = self.api_client
            if not self.primary_provider:
                self.primary_provider = "default"

        if not self.api_clients:
            return []

        if self.primary_provider and self.primary_provider in self.api_clients:
            return [self.primary_provider] + [
                name for name in self.api_clients if name != self.primary_provider
            ]
        return list(self.api_clients.keys())

    def _resolve_provider(
        self, provider_name: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[DomainAPIClient]]:
        """Resolve provider/client for a request"""
        ordered = self._provider_order(provider_name)
        if not ordered:
            return None, None
        selected = ordered[0]
        return selected, self.api_clients.get(selected)

    def configure(self, api_key: str, secret_key: Optional[str] = None,
                  api_secret: Optional[str] = None, monthly_budget: Optional[float] = None,
                  provider_name: str = "porkbun") -> Dict:
        """
        Configure a Porkbun client on the manager.
        Supports both secret_key and api_secret parameter names for compatibility.
        """
        resolved_secret = api_secret or secret_key
        if not api_key or not resolved_secret:
            return {"success": False, "error": "API key and secret are required"}

        if monthly_budget is not None:
            try:
                parsed_budget = float(monthly_budget)
            except (TypeError, ValueError):
                return {"success": False, "error": "Invalid monthly budget"}
            if parsed_budget <= 0:
                return {"success": False, "error": "Monthly budget must be greater than 0"}
            self.monthly_budget = parsed_budget

        client = PorkbunAPIClient(api_key=api_key, api_secret=resolved_secret)
        self.set_api_client(client, provider_name=provider_name, make_primary=True)
        return {
            "success": True,
            "provider": provider_name,
            "monthly_budget": self.monthly_budget
        }

    def get_config(self) -> Dict:
        """Get current non-secret manager configuration"""
        return {
            "configured": bool(self.api_client),
            "providers": self._provider_order(),
            "primary_provider": self.primary_provider,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode
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
                                    max_attempts: int = 10,
                                    tlds: Optional[List[str]] = None,
                                    provider_name: Optional[str] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        selected_provider, client = self._resolve_provider(provider_name)
        if not client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        
        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = client.search_domain(domain)
            
            if result.get("available"):
                price = self._normalize_price(result.get("price"))
                if price is None:
                    continue
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": selected_provider
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float,
                                         provider_name: Optional[str] = None) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        selected_provider, client = self._resolve_provider(provider_name)
        if not client:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        if self.test_mode:
            result = {"success": True, "message": "test_mode purchase simulated"}
        else:
            result = client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": selected_provider,
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
        result = self.rotate_to_new_domain()
        if result.get("success"):
            return result.get("domain")
        return None

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict:
        """
        Rotate to a new domain with provider fallback.
        Returns a structured response for API/route usage.
        """
        provider_errors: List[Dict[str, str]] = []
        providers = self._provider_order()

        if not providers:
            logger.error("Could not rotate domain: no providers configured")
            return {"success": False, "error": "No provider configured"}

        for provider_name in providers:
            domain_info = self.find_cheap_available_domain(
                max_price=max_price,
                provider_name=provider_name
            )
            if not domain_info:
                provider_errors.append(
                    {"provider": provider_name, "error": "No available domain within budget"}
                )
                continue

            success = self.purchase_domain_if_budget_allows(
                domain_info["domain"],
                domain_info["price"],
                provider_name=provider_name
            )
            if success:
                self.active_domain = domain_info["domain"]
                return {
                    "success": True,
                    "domain": self.active_domain,
                    "cost": domain_info["price"],
                    "provider": provider_name
                }

            provider_errors.append(
                {"provider": provider_name, "error": "Purchase failed or budget exceeded"}
            )

        logger.error("Could not find and purchase an available cheap domain")
        return {
            "success": False,
            "error": "Could not find and purchase an available cheap domain",
            "attempted_providers": provider_errors
        }

    def search_cheap_domains(self, tlds: Optional[List[str]] = None, max_price: float = 5.0,
                             limit: int = 5, provider_name: Optional[str] = None) -> List[Dict]:
        """Search for a list of cheap available domains"""
        results: List[Dict] = []
        seen = set()
        providers = self._provider_order(provider_name)
        if not providers:
            return results

        per_provider_limit = max(1, limit)
        for provider in providers:
            attempts = 0
            while len(results) < limit and attempts < per_provider_limit * 3:
                attempts += 1
                domain_info = self.find_cheap_available_domain(
                    max_price=max_price,
                    max_attempts=1,
                    tlds=tlds,
                    provider_name=provider
                )
                if not domain_info:
                    continue
                domain_name = domain_info.get("domain")
                if domain_name in seen:
                    continue
                seen.add(domain_name)
                results.append(domain_info)

        return results[:limit]

    def generate_random_domain_name(self, tld: str = "xyz", length: int = 8) -> str:
        """Backward-compatible alias"""
        return self.generate_random_domain(tld=tld, length=length)
    
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
        """Export JSON-safe state for persistence"""
        serialized_domains = []
        for domain in self.owned_domains:
            item = domain.copy()
            purchased_at = item.get("purchased_at")
            expires_at = item.get("expires_at")
            if isinstance(purchased_at, datetime):
                item["purchased_at"] = purchased_at.isoformat()
            if isinstance(expires_at, datetime):
                item["expires_at"] = expires_at.isoformat()
            serialized_domains.append(item)

        return {
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "monthly_budget": self.monthly_budget,
            "primary_provider": self.primary_provider,
            "test_mode": self.test_mode
        }

    def import_state(self, state: Optional[Dict]):
        """Load persisted state and normalize datetime fields"""
        if not state:
            return

        try:
            self.current_spending = float(state.get("current_spending", 0.0))
        except (TypeError, ValueError):
            self.current_spending = 0.0

        self.active_domain = state.get("active_domain")
        self.test_mode = bool(state.get("test_mode", False))

        if state.get("monthly_budget") is not None:
            try:
                self.monthly_budget = float(state.get("monthly_budget"))
            except (TypeError, ValueError):
                pass

        stored_primary = state.get("primary_provider")
        if isinstance(stored_primary, str):
            self.primary_provider = stored_primary
            if stored_primary in self.api_clients:
                self.api_client = self.api_clients[stored_primary]

        self.owned_domains = []
        for domain in state.get("owned_domains", []):
            item = domain.copy()
            item["purchased_at"] = self._parse_timestamp(item.get("purchased_at"))
            item["expires_at"] = self._parse_timestamp(item.get("expires_at"))
            self.owned_domains.append(item)


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
