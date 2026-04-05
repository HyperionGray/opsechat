"""
Domain management and API integration.
Supports automated domain purchasing for burner email rotation.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
import random
import re
import string
from typing import Dict, Iterable, List, Optional

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """Base class for domain registrar API clients."""

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    def search_domain(self, domain: str) -> Dict:
        """Search whether a domain is available."""

    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase a domain."""

    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for a TLD."""


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
        """Make API request."""
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
        """Check if a domain is available."""
        result = self._make_request("domain/check", {"domain": domain})
        availability = result.get("isAvailable", False)
        is_available = availability in (True, "true", "TRUE", 1, "1")

        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and is_available,
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
        """Get pricing for TLD."""
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
        """List owned domains."""
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
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        if api_client:
            self.set_api_client(api_client)

    @staticmethod
    def _normalize_provider_name(provider_name: str) -> str:
        return provider_name.strip().lower()

    def _provider_order(self, provider_name: Optional[str] = None) -> Iterable[str]:
        """Yield providers in preferred search/purchase order."""
        if provider_name:
            normalized = self._normalize_provider_name(provider_name)
            if normalized in self.api_clients:
                yield normalized
            return

        if self.active_provider and self.active_provider in self.api_clients:
            yield self.active_provider

        for name in self.api_clients:
            if name != self.active_provider:
                yield name

    @staticmethod
    def _parse_price(value, default: float = 999.0) -> float:
        """Normalize API price values into floats."""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = re.sub(r"[^0-9.]", "", value)
            if not cleaned:
                return default
            try:
                return float(cleaned)
            except ValueError:
                return default
        return default

    def set_api_client(self, api_client: DomainAPIClient, provider_name: str = "primary"):
        """Backward-compatible helper to set/register an API client."""
        self.add_api_client(provider_name, api_client, set_active=(self.active_provider is None))

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient,
                       set_active: bool = False):
        """Register an additional API client provider."""
        normalized = self._normalize_provider_name(provider_name)
        self.api_clients[normalized] = api_client
        if self.active_provider is None or set_active:
            self.active_provider = normalized

    def configure(self, api_key: str, secret_key: str, monthly_budget: float = 10.0,
                  provider_name: str = "porkbun") -> Dict:
        """
        Configure and activate a registrar provider from web/API settings.
        Currently supports Porkbun.
        """
        normalized = self._normalize_provider_name(provider_name)
        if normalized != "porkbun":
            raise ValueError(f"Unsupported provider: {provider_name}")
        if not api_key or not secret_key:
            raise ValueError("Both api_key and secret_key are required")

        client = PorkbunAPIClient(api_key, secret_key)
        self.add_api_client("porkbun", client, set_active=True)
        self.monthly_budget = float(monthly_budget)
        return self.get_config()

    def get_config(self) -> Dict:
        """Return safe, non-secret runtime configuration state."""
        return {
            "configured": bool(self.api_clients),
            "providers": list(self.api_clients.keys()),
            "active_provider": self.active_provider,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains)
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
                                    provider_name: Optional[str] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_clients:
            logger.error("No API clients configured")
            return None

        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]

        provider_candidates = list(self._provider_order(provider_name))
        if not provider_candidates:
            logger.error("No matching API providers available for search")
            return None

        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for provider in provider_candidates:
                try:
                    result = self.api_clients[provider].search_domain(domain)
                except Exception as exc:
                    logger.warning("Provider %s search failed for %s: %s", provider, domain, exc)
                    continue

                if not result.get("available"):
                    continue

                price = self._parse_price(result.get("price"), default=999.0)
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider
                    }

        return None

    def purchase_domain_if_budget_allows(self, domain: str, price: float,
                                         provider_name: Optional[str] = None) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_clients:
            logger.error("No API clients configured")
            return False

        normalized_price = self._parse_price(price, default=999.0)

        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                           f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False

        providers = list(self._provider_order(provider_name))
        if not providers:
            logger.error("No matching API providers available for purchase")
            return False

        for provider in providers:
            result = self.api_clients[provider].purchase_domain(domain, years=1)
            if not result.get("success"):
                logger.error("Provider %s failed to purchase %s: %s",
                             provider, domain, result.get("message"))
                continue

            now = datetime.now()
            self.current_spending += normalized_price
            self.owned_domains.append({
                "domain": domain,
                "provider": provider,
                "price": normalized_price,
                "purchased_at": now.isoformat(),
                "expires_at": (now + timedelta(days=365)).isoformat(),
                "order_id": result.get("order_id")
            })

            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain

            # Keep provider that worked as active for subsequent requests.
            self.active_provider = provider
            logger.info("Successfully purchased domain: %s for $%s via %s",
                        domain, normalized_price, provider)
            return True

        return False

    def rotate_domain(self, max_price: float = 5.0, max_attempts: int = 10,
                      provider_name: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        remaining_budget = max(self.monthly_budget - self.current_spending, 0.0)
        effective_max_price = min(max_price, remaining_budget) if remaining_budget else 0.0
        if effective_max_price <= 0:
            logger.error("No remaining budget available for domain rotation")
            return None

        # Find cheap domain
        domain_info = self.find_cheap_available_domain(
            max_price=effective_max_price,
            max_attempts=max_attempts,
            provider_name=provider_name
        )

        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None

        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider_name=domain_info.get("provider")
        )

        if success:
            self.active_domain = domain_info["domain"]
            return self.active_domain

        return None

    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain."""
        return self.active_domain

    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains."""
        return self.owned_domains

    def get_budget_status(self) -> Dict:
        """Get budget information."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
