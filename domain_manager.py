"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from abc import ABC, abstractmethod
from typing import Dict, Iterator, List, Optional, Tuple
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
    
    VALID_PROVIDER_STRATEGIES = {"priority", "cheapest"}

    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0,
                 provider_strategy: str = "priority"):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.provider_order: List[str] = []
        self.provider_strategy = "priority"
        self.set_provider_strategy(provider_strategy)
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client:
            self.add_api_client("primary", api_client, make_primary=True)

    def set_provider_strategy(self, strategy: str):
        """Set provider selection strategy."""
        if strategy not in self.VALID_PROVIDER_STRATEGIES:
            raise ValueError(
                f"Invalid provider strategy '{strategy}'. "
                f"Expected one of: {sorted(self.VALID_PROVIDER_STRATEGIES)}"
            )
        self.provider_strategy = strategy

    def set_api_client(self, api_client: DomainAPIClient):
        """Set/replace the primary domain API client."""
        self.add_api_client("primary", api_client, make_primary=True)

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient,
                       make_primary: bool = False):
        """Register an API client under a provider name."""
        normalized_name = provider_name.strip().lower()
        if not normalized_name:
            raise ValueError("provider_name must not be empty")

        self.api_clients[normalized_name] = api_client
        if normalized_name not in self.provider_order:
            self.provider_order.append(normalized_name)

        if make_primary:
            self.provider_order = [normalized_name] + [
                p for p in self.provider_order if p != normalized_name
            ]

        if self.provider_order:
            self.api_client = self.api_clients[self.provider_order[0]]

    def remove_api_client(self, provider_name: str):
        """Remove a registered API provider."""
        normalized_name = provider_name.strip().lower()
        self.api_clients.pop(normalized_name, None)
        self.provider_order = [p for p in self.provider_order if p != normalized_name]
        self.api_client = (
            self.api_clients[self.provider_order[0]]
            if self.provider_order else None
        )

    def list_api_providers(self) -> List[str]:
        """List configured domain providers in selection order."""
        return list(self.provider_order)

    def _iter_providers(self) -> Iterator[Tuple[str, DomainAPIClient]]:
        """Yield providers in configured order with legacy fallback."""
        yielded = False

        for provider_name in self.provider_order:
            client = self.api_clients.get(provider_name)
            if client:
                yielded = True
                yield provider_name, client

        if not yielded and self.api_client:
            # Backward-compatible fallback for direct assignment usage.
            yield "primary", self.api_client

    def _resolve_provider(self, provider_name: Optional[str] = None) -> Optional[Tuple[str, DomainAPIClient]]:
        """Resolve a provider by name or default to the first configured one."""
        if provider_name:
            normalized = provider_name.strip().lower()
            client = self.api_clients.get(normalized)
            if client:
                return normalized, client
            if normalized == "primary" and self.api_client:
                # Backward-compatible fallback for code that directly sets api_client.
                return "primary", self.api_client
            logger.error(f"Provider '{provider_name}' is not configured")
            return None

        return next(self._iter_providers(), None)

    @staticmethod
    def _normalize_price(value: object) -> Optional[float]:
        """Normalize registrar price values to float."""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace("€", "").replace(",", "")
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
                                    max_attempts: int = 10,
                                    tlds: Optional[List[str]] = None,
                                    provider_strategy: Optional[str] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        providers = list(self._iter_providers())
        if not providers:
            logger.error("No API client configured")
            return None

        strategy = provider_strategy or self.provider_strategy
        if strategy not in self.VALID_PROVIDER_STRATEGIES:
            logger.error(f"Unknown provider strategy: {strategy}")
            return None

        # Try cheap TLDs
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]

        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            if strategy == "cheapest":
                best_candidate: Optional[Dict] = None
                for provider_name, client in providers:
                    try:
                        result = client.search_domain(domain)
                    except Exception as exc:
                        logger.warning(
                            f"Provider '{provider_name}' search failed for {domain}: {exc}"
                        )
                        continue

                    if not result.get("available"):
                        continue

                    price = self._normalize_price(result.get("price"))
                    if price is None or price > max_price:
                        continue

                    if not best_candidate or price < best_candidate["price"]:
                        best_candidate = {
                            "domain": domain,
                            "price": price,
                            "tld": tld,
                            "provider": provider_name
                        }

                if best_candidate:
                    return best_candidate
                continue

            # priority strategy: first provider that can satisfy the request wins
            for provider_name, client in providers:
                try:
                    result = client.search_domain(domain)
                except Exception as exc:
                    logger.warning(
                        f"Provider '{provider_name}' search failed for {domain}: {exc}"
                    )
                    continue

                if not result.get("available"):
                    continue

                price = self._normalize_price(result.get("price"))
                if price is None or price > max_price:
                    continue

                return {
                    "domain": domain,
                    "price": price,
                    "tld": tld,
                    "provider": provider_name
                }

        return None

    def purchase_domain_if_budget_allows(self, domain: str, price: float,
                                         provider_name: Optional[str] = None) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        provider = self._resolve_provider(provider_name)
        if not provider:
            logger.error("No API client configured")
            return False

        active_provider_name, client = provider

        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False

        # Attempt purchase
        result = client.purchase_domain(domain, years=1)

        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": active_provider_name,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })

            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain

            logger.info(
                f"Successfully purchased domain: {domain} for ${price} "
                f"via provider '{active_provider_name}'"
            )
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False

    def rotate_domain(self, provider_strategy: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(
            provider_strategy=provider_strategy
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
