"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
from abc import ABC, abstractmethod
import requests
import random
import re
import string
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainBudgetManager:
    """
    Lightweight compatibility wrapper for budget methods referenced in docs.
    """

    def __init__(self, parent: "DomainRotationManager"):
        self._parent = parent

    @property
    def monthly_budget(self) -> float:
        return self._parent.monthly_budget

    def set_monthly_budget(self, amount: float):
        self._parent.monthly_budget = float(amount)

    def get_month_spending(self) -> float:
        return self._parent.current_spending

    def get_remaining_budget(self) -> float:
        return self._parent.monthly_budget - self._parent.current_spending


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
        pass

    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        pass

    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        pass


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
        raw_available = result.get("isAvailable", False)
        available = (
            raw_available if isinstance(raw_available, bool)
            else str(raw_available).strip().lower() in {"1", "true", "yes"}
        )

        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and available,
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
        if api_client:
            self.api_clients["default"] = api_client
            self.active_api_client_name = "default"
        else:
            self.active_api_client_name = ""
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False
        self.provider_name = "porkbun"

    @property
    def budget_manager(self):
        """
        Backward-compatible budget facade used by older docs/examples.
        """
        return DomainBudgetManager(self)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.add_api_client("default", api_client, make_default=True)

    def add_api_client(self, name: str, api_client: DomainAPIClient, make_default: bool = False):
        """Register an additional API client provider"""
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("Provider name cannot be empty")
        self.api_clients[normalized] = api_client
        if make_default or not self.active_api_client_name:
            self.active_api_client_name = normalized
            self.api_client = api_client

    def set_active_api_client(self, name: str) -> bool:
        """Set active API client by registered provider name"""
        normalized = name.strip().lower()
        if normalized not in self.api_clients:
            return False
        self.active_api_client_name = normalized
        self.api_client = self.api_clients[normalized]
        return True

    def get_api_clients(self) -> List[str]:
        """List configured API client names"""
        return sorted(self.api_clients.keys())

    def _get_client(self) -> Optional[DomainAPIClient]:
        """Return active API client"""
        if self.api_client:
            return self.api_client
        if self.active_api_client_name and self.active_api_client_name in self.api_clients:
            return self.api_clients[self.active_api_client_name]
        return None

    @staticmethod
    def _mask_secret(value: str) -> str:
        """Mask API secret values for safe display"""
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:2]}{'*' * (len(value) - 6)}{value[-4:]}"

    @staticmethod
    def _parse_price(value: Any) -> Optional[float]:
        """Normalize registrar price data into float"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = re.sub(r"[^0-9.]", "", value)
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        provider: str = "porkbun"
    ) -> Dict[str, Any]:
        """
        Configure a provider and budget from web/API configuration flow.
        """
        resolved_secret = secret_key or api_secret
        provider_name = provider.strip().lower()
        if provider_name != "porkbun":
            return {"success": False, "error": f"Unsupported provider: {provider}"}
        if not api_key or not resolved_secret:
            return {"success": False, "error": "API key and secret are required"}

        try:
            client = PorkbunAPIClient(api_key, resolved_secret)
            self.add_api_client(provider_name, client, make_default=True)
            self.provider_name = provider_name
            if monthly_budget is not None:
                self.monthly_budget = float(monthly_budget)
            return {"success": True, "provider": provider_name}
        except Exception as exc:
            logger.exception("Failed to configure domain manager")
            return {"success": False, "error": str(exc)}

    def get_config(self) -> Dict[str, Any]:
        """Get current non-sensitive configuration status"""
        client = self._get_client()
        api_key = client.api_key if client else ""
        return {
            "provider": self.active_api_client_name or self.provider_name,
            "api_key": self._mask_secret(api_key),
            "configured": client is not None,
            "monthly_budget": self.monthly_budget,
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

    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        """Compatibility alias for docs/examples"""
        return self.generate_random_domain(tld=tld, length=length)

    def generate_domain_from_pattern(self, pattern: str, tld: str = "xyz") -> str:
        """
        Generate a domain from a simple token pattern.
        Supported tokens: {timestamp}, {random}
        """
        random_part = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))
        rendered = (
            pattern.replace("{timestamp}", datetime.utcnow().strftime("%Y%m%d%H%M%S"))
            .replace("{random}", random_part)
            .strip()
            .lower()
        )
        safe_name = re.sub(r"[^a-z0-9-]", "-", rendered).strip("-")
        safe_name = re.sub(r"-{2,}", "-", safe_name)
        return f"{safe_name or random_part}.{tld}"
    
    def find_cheap_available_domain(self, max_price: float = 5.0, 
                                   max_attempts: int = 10) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        api_client = self._get_client()
        if not api_client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = api_client.search_domain(domain)
            
            if result.get("available"):
                price = self._parse_price(result.get("price"))
                
                if price is not None and price <= max_price:
                    return {
                        "domain": domain,
                        "name": domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 10,
        max_attempts: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Return multiple currently available cheap domains.
        """
        api_client = self._get_client()
        if not api_client:
            logger.error("No API client configured")
            return []

        selected_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        results: List[Dict[str, Any]] = []
        seen: set = set()
        attempts = 0

        while len(results) < limit and attempts < max_attempts:
            attempts += 1
            tld = random.choice(selected_tlds)
            domain = self.generate_random_domain(tld)
            if domain in seen:
                continue
            seen.add(domain)

            record = api_client.search_domain(domain)
            if not record.get("available"):
                continue

            price = self._parse_price(record.get("price"))
            if price is None or price > max_price:
                continue

            results.append({
                "domain": domain,
                "name": domain,
                "price": price,
                "tld": tld,
                "currency": record.get("currency", "USD")
            })

        return results
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        api_client = self._get_client()
        if not api_client:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        if self.test_mode:
            result = {"success": True, "domain": domain, "message": "test mode"}
        else:
            # Attempt purchase
            result = api_client.purchase_domain(domain, years=1)

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
        Compatibility wrapper that returns structured JSON-safe result.
        """
        new_domain = self.rotate_domain(max_price=max_price)
        if not new_domain:
            return {
                "success": False,
                "error": "Could not rotate domain within current budget/availability constraints"
            }

        purchased = next(
            (item for item in reversed(self.owned_domains) if item.get("domain") == new_domain),
            {}
        )
        return {
            "success": True,
            "domain": new_domain,
            "cost": purchased.get("price"),
            "active_domain": self.active_domain
        }

    def set_test_mode(self, enabled: bool):
        """Enable/disable dry-run mode for purchases"""
        self.test_mode = bool(enabled)

    def set_monthly_budget(self, amount: float):
        """Set monthly budget limit"""
        self.monthly_budget = float(amount)

    def get_month_spending(self) -> float:
        """Get current month spending total"""
        return self.current_spending

    def get_remaining_budget(self) -> float:
        """Get remaining available budget"""
        return self.monthly_budget - self.current_spending

    def serialize_owned_domains(self) -> List[Dict[str, Any]]:
        """Convert in-memory domain records to JSON-safe dictionaries"""
        serialized: List[Dict[str, Any]] = []
        for item in self.owned_domains:
            normalized = dict(item)
            for key in ("purchased_at", "expires_at"):
                value = normalized.get(key)
                if isinstance(value, datetime):
                    normalized[key] = value.isoformat()
            serialized.append(normalized)
        return serialized

    def load_owned_domains(self, domain_records: List[Dict[str, Any]]):
        """Load domain records from JSON-safe dictionaries"""
        loaded: List[Dict[str, Any]] = []
        for item in domain_records or []:
            normalized = dict(item)
            for key in ("purchased_at", "expires_at"):
                value = normalized.get(key)
                if isinstance(value, str):
                    try:
                        normalized[key] = datetime.fromisoformat(value)
                    except ValueError:
                        pass
            loaded.append(normalized)
        self.owned_domains = loaded

    def export_state(self) -> Dict[str, Any]:
        """Export manager state for persistence"""
        return {
            "current_spending": self.current_spending,
            "owned_domains": self.serialize_owned_domains(),
            "active_domain": self.active_domain
        }

    def load_state(self, state: Dict[str, Any]):
        """Load manager state from persisted dictionary"""
        self.current_spending = float(state.get("current_spending", 0.0) or 0.0)
        self.load_owned_domains(state.get("owned_domains", []))
        self.active_domain = state.get("active_domain")

    def configure_domain_dns(
        self,
        domain: str,
        mx_records: Optional[List[Dict[str, Any]]] = None,
        a_records: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        DNS configuration shim for future multi-provider support.
        """
        _ = (mx_records, a_records)
        return {
            "success": False,
            "error": f"DNS management not supported by provider '{self.active_api_client_name or self.provider_name}'",
            "domain": domain
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
