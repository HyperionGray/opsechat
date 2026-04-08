"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import re
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
    
    DEFAULT_CHEAP_TLDS = ["xyz", "club", "online", "site", "website"]

    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client:
            self.add_api_client("default", api_client, set_as_primary=True)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.add_api_client("default", api_client, set_as_primary=True)

    def add_api_client(
        self,
        provider_name: str,
        api_client: DomainAPIClient,
        set_as_primary: bool = False
    ) -> None:
        """Register an API client for a provider."""
        provider = provider_name.strip().lower()
        if not provider:
            raise ValueError("provider_name cannot be empty")

        self.api_clients[provider] = api_client

        if set_as_primary or not self.api_client:
            self.api_client = api_client
            self.active_provider = provider

    def remove_api_client(self, provider_name: str) -> bool:
        """Remove a configured API client."""
        provider = provider_name.strip().lower()
        removed = self.api_clients.pop(provider, None) is not None

        if removed and self.active_provider == provider:
            self.active_provider = None

        if removed and self.api_client and provider == "default":
            self.api_client = None

        return removed

    def _available_clients(self) -> Dict[str, DomainAPIClient]:
        if self.api_clients:
            return self.api_clients
        if self.api_client:
            return {"default": self.api_client}
        return {}

    def _resolve_client(self, provider_name: Optional[str]) -> Tuple[Optional[str], Optional[DomainAPIClient]]:
        clients = self._available_clients()
        if not clients:
            return None, None

        if provider_name:
            provider = provider_name.strip().lower()
            client = clients.get(provider)
            if client:
                return provider, client
            return None, None

        if self.active_provider and self.active_provider in clients:
            return self.active_provider, clients[self.active_provider]

        provider, client = next(iter(clients.items()))
        return provider, client

    @staticmethod
    def _parse_price(price: Any) -> Optional[float]:
        if isinstance(price, (int, float)):
            return float(price)

        if isinstance(price, str):
            cleaned = re.sub(r"[^0-9.]", "", price)
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
    
    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        provider: Optional[str] = None,
        tlds: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        clients = self._available_clients()
        if not clients:
            logger.error("No API client configured")
            return None

        if provider:
            provider_name = provider.strip().lower()
            if provider_name not in clients:
                logger.error(f"Provider not configured: {provider_name}")
                return None
            clients = {provider_name: clients[provider_name]}

        cheap_tlds = tlds or self.DEFAULT_CHEAP_TLDS
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            available_options: List[Dict[str, Any]] = []
            for provider_name, client in clients.items():
                result = client.search_domain(domain)
                if not result.get("available"):
                    continue

                price = self._parse_price(result.get("price"))
                if price is None:
                    logger.warning(f"Skipping domain with invalid price from {provider_name}: {domain}")
                    continue

                if price <= max_price:
                    available_options.append({
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider_name
                    })

            if available_options:
                return min(available_options, key=lambda option: option["price"])
        
        return None

    def search_cheap_domains(
        self,
        max_price: float = 5.0,
        limit: int = 5,
        max_attempts: int = 25,
        provider: Optional[str] = None,
        tlds: Optional[List[str]] = None
    ) -> List[Dict]:
        """Search for multiple cheap domains without purchasing."""
        found: List[Dict] = []
        seen_domains = set()

        for _ in range(max_attempts):
            domain_info = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                provider=provider,
                tlds=tlds
            )
            if not domain_info:
                continue

            domain = domain_info["domain"]
            if domain in seen_domains:
                continue

            seen_domains.add(domain)
            found.append(domain_info)

            if len(found) >= limit:
                break

        return sorted(found, key=lambda item: item["price"])

    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider: Optional[str] = None
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        provider_name, client = self._resolve_client(provider)
        if not client:
            logger.error("No API client configured")
            return False

        parsed_price = self._parse_price(price)
        if parsed_price is None:
            logger.error(f"Invalid purchase price for domain {domain}: {price}")
            return False

        # Check budget
        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${parsed_price}, Budget: ${self.monthly_budget}")
            return False

        # Attempt purchase
        result = client.purchase_domain(domain, years=1)

        if result.get("success"):
            now = datetime.now()
            self.current_spending += parsed_price
            self.owned_domains.append({
                "domain": domain,
                "price": parsed_price,
                "provider": provider_name,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365)
            })

            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            self.active_provider = provider_name

            logger.info(f"Successfully purchased domain: {domain} for ${parsed_price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False

    def rotate_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        preferred_provider: Optional[str] = None
    ) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=max_attempts,
            provider=preferred_provider
        )

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
            self.active_provider = domain_info.get("provider")
            return self.active_domain

        return None

    def rotate_to_new_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        preferred_provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Rotate domain and return detailed result payload."""
        new_domain = self.rotate_domain(
            max_price=max_price,
            max_attempts=max_attempts,
            preferred_provider=preferred_provider
        )
        if not new_domain:
            return {"success": False, "error": "Failed to rotate domain"}

        domain_info = next(
            (d for d in reversed(self.owned_domains) if d.get("domain") == new_domain),
            {}
        )
        return {
            "success": True,
            "domain": new_domain,
            "cost": domain_info.get("price"),
            "provider": domain_info.get("provider")
        }

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 10.0,
        provider: str = "porkbun"
    ) -> Dict[str, Any]:
        """Configure a provider client and budget from runtime settings."""
        provider_name = provider.strip().lower()
        if provider_name != "porkbun":
            raise ValueError(f"Unsupported provider: {provider_name}")

        client = PorkbunAPIClient(api_key, secret_key)
        self.add_api_client(provider_name, client, set_as_primary=True)
        self.monthly_budget = float(monthly_budget)
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return manager configuration and status for UI/API consumers."""
        return {
            "configured": bool(self._available_clients()),
            "providers": sorted(self._available_clients().keys()),
            "active_provider": self.active_provider,
            "active_domain": self.active_domain,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "domains_owned": len(self.owned_domains),
            "budget_status": self.get_budget_status()
        }

    @staticmethod
    def _parse_datetime(value: Any) -> Any:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value
        return value

    def serialize_owned_domains(self) -> List[Dict[str, Any]]:
        """Return owned domains with JSON-serializable datetime fields."""
        serialized: List[Dict[str, Any]] = []
        for domain in self.owned_domains:
            item = dict(domain)
            for field in ("purchased_at", "expires_at"):
                if isinstance(item.get(field), datetime):
                    item[field] = item[field].isoformat()
            serialized.append(item)
        return serialized

    def load_owned_domains(self, domains: List[Dict[str, Any]]) -> None:
        """Load domain ownership state and parse datetime fields."""
        normalized: List[Dict[str, Any]] = []
        for domain in domains or []:
            item = dict(domain)
            item["purchased_at"] = self._parse_datetime(item.get("purchased_at"))
            item["expires_at"] = self._parse_datetime(item.get("expires_at"))
            normalized.append(item)
        self.owned_domains = normalized

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
