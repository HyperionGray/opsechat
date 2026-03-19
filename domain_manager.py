"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from typing import Any, Dict, List, Optional, Tuple
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
        self.provider_order: List[str] = []
        self.active_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client:
            self.add_api_client("default", api_client, make_active=True)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Backward-compatible setter for a default API client."""
        self.add_api_client("default", api_client, make_active=True)

    def add_api_client(self, provider: str, api_client: DomainAPIClient,
                       make_active: bool = False):
        """Register a provider client."""
        normalized_provider = (provider or "default").strip().lower()
        self.api_clients[normalized_provider] = api_client
        if normalized_provider not in self.provider_order:
            self.provider_order.append(normalized_provider)

        if make_active or not self.active_provider:
            self.set_active_provider(normalized_provider)

    def set_active_provider(self, provider: str) -> bool:
        """Set the currently active provider if it exists."""
        normalized_provider = (provider or "").strip().lower()
        client = self.api_clients.get(normalized_provider)
        if not client:
            return False

        self.active_provider = normalized_provider
        self.api_client = client
        return True

    def get_active_provider(self) -> Optional[str]:
        """Return the currently active provider name."""
        return self.active_provider

    def get_provider_names(self) -> List[str]:
        """Return configured providers in deterministic order."""
        return [p for p in self.provider_order if p in self.api_clients]

    def _select_provider_clients(self, provider: Optional[str] = None) -> List[Tuple[str, DomainAPIClient]]:
        """Return provider clients in priority order."""
        if provider:
            normalized_provider = provider.strip().lower()
            client = self.api_clients.get(normalized_provider)
            return [(normalized_provider, client)] if client else []

        clients: List[Tuple[str, DomainAPIClient]] = []
        seen = set()

        if self.active_provider and self.active_provider in self.api_clients:
            clients.append((self.active_provider, self.api_clients[self.active_provider]))
            seen.add(self.active_provider)

        for provider_name in self.provider_order:
            if provider_name in seen:
                continue
            client = self.api_clients.get(provider_name)
            if client:
                clients.append((provider_name, client))
                seen.add(provider_name)

        # Preserve compatibility for code that only used self.api_client.
        if not clients and self.api_client:
            clients.append(("default", self.api_client))

        return clients

    @staticmethod
    def _parse_price(price: Any) -> Optional[float]:
        """Best-effort parse of provider price values."""
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

    @staticmethod
    def _serialize_datetime(value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _deserialize_datetime(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value

    def _serialize_domain_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        serialized = dict(record)
        serialized["purchased_at"] = self._serialize_datetime(record.get("purchased_at"))
        serialized["expires_at"] = self._serialize_datetime(record.get("expires_at"))
        return serialized

    def _deserialize_domain_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        deserialized = dict(record)
        deserialized["purchased_at"] = self._deserialize_datetime(record.get("purchased_at"))
        deserialized["expires_at"] = self._deserialize_datetime(record.get("expires_at"))
        return deserialized

    def configure(self, api_key: str, secret_key: Optional[str] = None,
                  api_secret: Optional[str] = None, monthly_budget: Optional[float] = None,
                  provider: str = "porkbun") -> Dict[str, Any]:
        """
        Configure a provider API client and optional budget.
        Currently supports Porkbun while allowing a multi-provider registry.
        """
        normalized_provider = (provider or "porkbun").strip().lower()
        resolved_secret = secret_key or api_secret

        if not api_key or not resolved_secret:
            raise ValueError("api_key and secret_key/api_secret are required")

        if normalized_provider != "porkbun":
            raise ValueError(f"Unsupported provider: {normalized_provider}")

        client = PorkbunAPIClient(api_key, resolved_secret)
        self.add_api_client(normalized_provider, client, make_active=True)

        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return safe runtime configuration details."""
        return {
            "configured": bool(self._select_provider_clients()),
            "active_provider": self.active_provider,
            "providers": self.get_provider_names(),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def export_state(self) -> Dict[str, Any]:
        """Serialize budget/domain runtime state."""
        return {
            "current_spending": self.current_spending,
            "owned_domains": [self._serialize_domain_record(d) for d in self.owned_domains],
            "active_domain": self.active_domain,
            "active_provider": self.active_provider,
        }

    def load_state(self, state: Optional[Dict[str, Any]]):
        """Load serialized state produced by export_state()."""
        if not isinstance(state, dict):
            return

        self.current_spending = float(state.get("current_spending", 0.0))
        raw_domains = state.get("owned_domains", [])
        if isinstance(raw_domains, list):
            self.owned_domains = [
                self._deserialize_domain_record(d)
                for d in raw_domains
                if isinstance(d, dict)
            ]

        active_domain = state.get("active_domain")
        if isinstance(active_domain, str) or active_domain is None:
            self.active_domain = active_domain

        state_provider = state.get("active_provider")
        if isinstance(state_provider, str):
            self.set_active_provider(state_provider)
    
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
                                    provider: Optional[str] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        provider_clients = self._select_provider_clients(provider)
        if not provider_clients:
            logger.error("No domain API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            for provider_name, client in provider_clients:
                result = client.search_domain(domain)

                if not isinstance(result, dict) or not result.get("available"):
                    continue

                price = self._parse_price(result.get("price"))
                if price is None:
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider_name,
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float,
                                         provider: Optional[str] = None) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        provider_clients = self._select_provider_clients(provider)
        if not provider_clients:
            logger.error("No API client configured")
            return False
        selected_provider, client = provider_clients[0]
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            now = datetime.now()
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": selected_provider,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            self.set_active_provider(selected_provider)
            
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self, provider: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(provider=provider)
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider=domain_info.get("provider")
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
            "domains_owned": len(self.owned_domains),
            "active_provider": self.active_provider
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
