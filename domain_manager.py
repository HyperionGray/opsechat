"""
Domain management and API integration.
Supports automated domain purchasing for burner email rotation.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
import random
import string
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients.
    """

    provider_name = "generic"

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search if domain is available."""

    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase domain."""

    @abstractmethod
    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing for TLD."""


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management.
    https://porkbun.com/api/json/v3/documentation
    """

    provider_name = "porkbun"
    BASE_URL = "https://porkbun.com/api/json/v3"

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()

    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        except Exception as exc:
            logger.error("Porkbun API request failed: %s", exc)
            return {"status": "ERROR", "message": str(exc)}

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check if domain is available."""
        result = self._make_request("domain/check", {"domain": domain})

        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and result.get("isAvailable", False),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
            "provider": self.provider_name
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase domain.
        Note: This actually purchases the domain and charges your account.
        """
        result = self._make_request("domain/create", {
            "domain": domain,
            "years": years
        })

        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId"),
            "provider": self.provider_name
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get pricing for TLD."""
        result = self._make_request("pricing/get", {"tld": tld})

        if result.get("status") == "SUCCESS":
            pricing = result.get("pricing", {})
            return {
                "tld": tld,
                "registration": pricing.get("registration"),
                "renewal": pricing.get("renewal"),
                "transfer": pricing.get("transfer"),
                "currency": "USD",
                "provider": self.provider_name
            }

        return {}

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("domain/listAll")

        if result.get("status") == "SUCCESS":
            domains = result.get("domains", [])
            return [entry.get("domain") for entry in domains if entry.get("domain")]

        return []


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap API client for domain management.
    https://www.namecheap.com/support/api/intro/
    """

    provider_name = "namecheap"
    BASE_URL = "https://api.namecheap.com/xml.response"

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        contact_info: Optional[Dict[str, str]] = None
    ):
        super().__init__(api_key=api_key, api_secret=None)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.contact_info = contact_info or self._default_contact_info()
        self.session = requests.Session()

    def _default_contact_info(self) -> Dict[str, str]:
        """
        Default contact information used for purchase attempts.
        Callers should provide real values before production purchases.
        """
        return {
            "FirstName": "Domain",
            "LastName": "Manager",
            "Address1": "123 Privacy Street",
            "City": "Wilmington",
            "StateProvince": "DE",
            "PostalCode": "19801",
            "Country": "US",
            "Phone": "+1.5555555555",
            "EmailAddress": "domain-admin@example.com",
            "OrganizationName": "OpSecChat"
        }

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> ET.Element:
        payload = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command
        }
        if params:
            payload.update(params)

        response = self.session.get(self.BASE_URL, params=payload, timeout=30)
        response.raise_for_status()
        return ET.fromstring(response.text)

    def _extract_errors(self, root: ET.Element) -> List[str]:
        return [entry.text.strip() for entry in root.findall(".//Errors/Error") if entry.text]

    def search_domain(self, domain: str) -> Dict[str, Any]:
        try:
            root = self._make_request("namecheap.domains.check", {"DomainList": domain})
        except Exception as exc:
            logger.error("Namecheap domain search failed: %s", exc)
            return {"domain": domain, "available": False, "message": str(exc), "provider": self.provider_name}

        errors = self._extract_errors(root)
        if errors:
            return {
                "domain": domain,
                "available": False,
                "message": "; ".join(errors),
                "provider": self.provider_name
            }

        check_result = root.find(".//DomainCheckResult")
        if check_result is None:
            return {
                "domain": domain,
                "available": False,
                "message": "Namecheap response missing DomainCheckResult",
                "provider": self.provider_name
            }

        available = check_result.attrib.get("Available", "false").lower() == "true"
        price = (
            check_result.attrib.get("PremiumRegistrationPrice")
            or check_result.attrib.get("Price")
        )
        currency = check_result.attrib.get("Currency", "USD")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": currency,
            "provider": self.provider_name
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        tld = domain.rsplit(".", 1)[-1].lower()
        sld = domain[:-(len(tld) + 1)]

        payload = {
            "DomainName": domain,
            "SLD": sld,
            "TLD": tld,
            "Years": years,
        }

        # Namecheap requires contact fields for all contact roles.
        for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for key, value in self.contact_info.items():
                payload[f"{role}{key}"] = value

        try:
            root = self._make_request("namecheap.domains.create", payload)
        except Exception as exc:
            logger.error("Namecheap purchase failed: %s", exc)
            return {
                "success": False,
                "domain": domain,
                "message": str(exc),
                "provider": self.provider_name
            }

        errors = self._extract_errors(root)
        if errors:
            return {
                "success": False,
                "domain": domain,
                "message": "; ".join(errors),
                "provider": self.provider_name
            }

        domain_create_result = root.find(".//DomainCreateResult")
        success = domain_create_result is not None

        return {
            "success": success,
            "domain": domain,
            "message": "" if success else "DomainCreateResult missing",
            "provider": self.provider_name
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        params = {
            "ProductType": "DOMAIN",
            "ProductCategory": "DOMAINS",
            "ProductName": tld.upper(),
            "ActionName": "REGISTER"
        }

        try:
            root = self._make_request("namecheap.users.getPricing", params)
        except Exception as exc:
            logger.error("Namecheap pricing lookup failed: %s", exc)
            return {}

        errors = self._extract_errors(root)
        if errors:
            return {}

        registration = None
        for node in root.findall(".//ProductPrice"):
            duration = node.attrib.get("Duration")
            if duration in ("1", "12"):
                registration = node.attrib.get("YourPrice") or node.attrib.get("Price")
                break

        if registration is None:
            first_price = root.find(".//ProductPrice")
            if first_price is not None:
                registration = first_price.attrib.get("YourPrice") or first_price.attrib.get("Price")

        return {
            "tld": tld,
            "registration": registration,
            "currency": "USD",
            "provider": self.provider_name
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Supports multiple domain providers with round-robin or cheapest strategy.
    """

    VALID_STRATEGIES = {"round-robin", "cheapest"}

    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
        selection_strategy: str = "round-robin"
    ):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict[str, Any]] = []
        self.active_domain: Optional[str] = None
        self.active_provider: Optional[str] = None

        self.providers: Dict[str, DomainAPIClient] = {}
        self.provider_order: List[str] = []
        self.provider_spending: Dict[str, float] = {}
        self.provider_budgets: Dict[str, float] = {}
        self._round_robin_index = 0
        self.selection_strategy = "round-robin"
        self.set_selection_strategy(selection_strategy)

        if api_client:
            inferred_name = getattr(api_client, "provider_name", "default")
            self.set_api_client(api_client, provider_name=inferred_name)

    def _normalize_provider_name(self, provider_name: Any) -> str:
        """Normalize provider name to a stable lowercase key."""
        if isinstance(provider_name, str):
            normalized = provider_name.strip().lower()
        else:
            normalized = str(provider_name).strip().lower()
        return normalized or "default"

    def configure(
        self,
        api_key: str,
        secret_key: str = "",
        monthly_budget: float = 50.0,
        provider: str = "porkbun",
        **kwargs: Any
    ) -> bool:
        """Configure and register a provider from credentials."""
        self.monthly_budget = monthly_budget
        provider_name = provider.strip().lower()

        if provider_name == "porkbun":
            client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
        elif provider_name == "namecheap":
            api_user = kwargs.get("api_user") or kwargs.get("username")
            username = kwargs.get("username")
            client_ip = kwargs.get("client_ip", "127.0.0.1")
            if not api_user:
                raise ValueError("Namecheap configuration requires api_user or username")
            client = NamecheapAPIClient(
                api_user=api_user,
                api_key=api_key,
                username=username,
                client_ip=client_ip
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        normalized_provider = self._normalize_provider_name(provider_name)
        if not self.providers:
            self.set_api_client(client, provider_name=normalized_provider)
        else:
            self.add_provider(normalized_provider, client, monthly_budget=monthly_budget)
        self.provider_budgets[normalized_provider] = monthly_budget
        return True

    def get_config(self) -> Dict[str, Any]:
        """Get a safe snapshot of provider and budget configuration."""
        return {
            "configured": bool(self.providers),
            "selection_strategy": self.selection_strategy,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "providers": [
                {
                    "name": name,
                    "budget": self.provider_budgets.get(name, self.monthly_budget),
                    "spending": self.provider_spending.get(name, 0.0),
                    "client_type": type(self.providers[name]).__name__
                }
                for name in self.provider_order
            ],
            "active_domain": self.active_domain,
            "active_provider": self.active_provider
        }

    def set_selection_strategy(self, strategy: str):
        """Set provider selection strategy."""
        normalized = strategy.strip().lower()
        if normalized not in self.VALID_STRATEGIES:
            raise ValueError(f"Invalid strategy '{strategy}'. Valid: {sorted(self.VALID_STRATEGIES)}")
        self.selection_strategy = normalized

    def list_providers(self) -> List[str]:
        """Get registered provider names."""
        return list(self.provider_order)

    def set_api_client(self, api_client: DomainAPIClient, provider_name: str = "default"):
        """
        Set a single domain API client (backward compatible).
        This resets provider registry to one provider.
        """
        key = self._normalize_provider_name(provider_name)
        self.api_client = api_client
        self.providers = {key: api_client}
        self.provider_order = [key]
        self.provider_spending = {key: self.provider_spending.get(key, 0.0)}
        self.provider_budgets = {key: self.provider_budgets.get(key, self.monthly_budget)}
        self._round_robin_index = 0

    def add_provider(
        self,
        provider_name: str,
        api_client: DomainAPIClient,
        monthly_budget: Optional[float] = None
    ):
        """Add or replace a provider without removing others."""
        key = self._normalize_provider_name(provider_name)
        self.providers[key] = api_client
        if key not in self.provider_order:
            self.provider_order.append(key)
        if key not in self.provider_spending:
            self.provider_spending[key] = 0.0
        self.provider_budgets[key] = monthly_budget if monthly_budget is not None else self.monthly_budget
        if not self.api_client:
            self.api_client = api_client

    def remove_provider(self, provider_name: str):
        """Remove a provider if present."""
        key = self._normalize_provider_name(provider_name)
        removed_client = self.providers.pop(key, None)
        self.provider_spending.pop(key, None)
        self.provider_budgets.pop(key, None)
        self.provider_order = [entry for entry in self.provider_order if entry != key]
        if self.active_provider == key:
            self.active_provider = None
        if removed_client is not None and self.api_client is removed_client:
            self.api_client = next(iter(self.providers.values()), None)

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name.
        Uses cheap TLDs like .xyz, .club, .online.
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def _normalize_price(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace("€", "").replace(",", "")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                filtered = ''.join(ch for ch in cleaned if ch.isdigit() or ch == '.')
                if filtered:
                    try:
                        return float(filtered)
                    except ValueError:
                        return None
        return None

    def _provider_can_spend(self, provider_name: str, price: float) -> bool:
        provider_spent = self.provider_spending.get(provider_name, 0.0)
        provider_budget = self.provider_budgets.get(provider_name, self.monthly_budget)
        return (
            self.current_spending + price <= self.monthly_budget
            and provider_spent + price <= provider_budget
        )

    def _provider_order_for_attempt(self) -> List[str]:
        if not self.provider_order:
            return []
        if self.selection_strategy != "round-robin":
            return list(self.provider_order)

        start = self._round_robin_index % len(self.provider_order)
        self._round_robin_index += 1
        return self.provider_order[start:] + self.provider_order[:start]

    def _build_candidate(
        self,
        domain: str,
        tld: str,
        provider_name: str,
        result: Dict[str, Any],
        max_price: float
    ) -> Optional[Dict[str, Any]]:
        if not result.get("available"):
            return None
        price = self._normalize_price(result.get("price"))
        if price is None or price > max_price:
            return None
        if not self._provider_can_spend(provider_name, price):
            return None
        return {
            "domain": domain,
            "price": price,
            "tld": tld,
            "provider": provider_name,
            "currency": result.get("currency", "USD")
        }

    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Find a cheap available domain.
        Returns domain info including provider or None.
        """
        if not self.providers:
            logger.error("No domain providers configured")
            return None

        cheap_tlds = ["xyz", "club", "online", "site", "website"]

        for _attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            if self.selection_strategy == "cheapest":
                best_candidate = None
                for provider_name in self.provider_order:
                    provider = self.providers[provider_name]
                    result = provider.search_domain(domain)
                    candidate = self._build_candidate(domain, tld, provider_name, result, max_price)
                    if candidate and (best_candidate is None or candidate["price"] < best_candidate["price"]):
                        best_candidate = candidate
                if best_candidate:
                    return best_candidate
                continue

            for provider_name in self._provider_order_for_attempt():
                provider = self.providers[provider_name]
                result = provider.search_domain(domain)
                candidate = self._build_candidate(domain, tld, provider_name, result, max_price)
                if candidate:
                    return candidate

        return None

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 5,
        max_attempts: int = 50
    ) -> List[Dict[str, Any]]:
        """Return a list of cheap domain candidates across providers."""
        if not self.providers:
            logger.error("No domain providers configured")
            return []

        results: List[Dict[str, Any]] = []
        seen_domains = set()
        search_tlds = tlds or ["xyz", "club", "online", "site", "website"]

        for _ in range(max_attempts):
            if len(results) >= limit:
                break
            tld = random.choice(search_tlds)
            domain = self.generate_random_domain(tld)
            if domain in seen_domains:
                continue

            if self.selection_strategy == "cheapest":
                best_candidate = None
                for provider_name in self.provider_order:
                    provider = self.providers[provider_name]
                    candidate = self._build_candidate(
                        domain, tld, provider_name, provider.search_domain(domain), max_price
                    )
                    if candidate and (best_candidate is None or candidate["price"] < best_candidate["price"]):
                        best_candidate = candidate
                if best_candidate:
                    results.append(best_candidate)
                    seen_domains.add(domain)
                continue

            for provider_name in self._provider_order_for_attempt():
                provider = self.providers[provider_name]
                candidate = self._build_candidate(
                    domain, tld, provider_name, provider.search_domain(domain), max_price
                )
                if candidate:
                    results.append(candidate)
                    seen_domains.add(domain)
                    break

        return results

    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider_name: Optional[str] = None
    ) -> bool:
        """
        Purchase domain if within budget and provider limits.
        Returns True on success.
        """
        if not self.providers:
            logger.error("No domain providers configured")
            return False

        chosen_provider = provider_name.strip().lower() if provider_name else None
        if not chosen_provider:
            if not self.provider_order:
                logger.error("Provider order is empty")
                return False
            chosen_provider = self.provider_order[0]

        provider = self.providers.get(chosen_provider)
        if not provider:
            logger.error("Unknown provider '%s'", chosen_provider)
            return False

        normalized_price = self._normalize_price(price)
        if normalized_price is None:
            logger.error("Invalid price value: %r", price)
            return False

        if not self._provider_can_spend(chosen_provider, normalized_price):
            logger.warning(
                "Budget exceeded for provider %s. Global: %.2f/%.2f Provider: %.2f/%.2f",
                chosen_provider,
                self.current_spending,
                self.monthly_budget,
                self.provider_spending.get(chosen_provider, 0.0),
                self.provider_budgets.get(chosen_provider, self.monthly_budget)
            )
            return False

        result = provider.purchase_domain(domain, years=1)
        if result.get("success"):
            now = datetime.now()
            self.current_spending += normalized_price
            self.provider_spending[chosen_provider] = (
                self.provider_spending.get(chosen_provider, 0.0) + normalized_price
            )
            self.owned_domains.append({
                "domain": domain,
                "price": normalized_price,
                "provider": chosen_provider,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365)
            })

            if not self.active_domain:
                self.active_domain = domain
                self.active_provider = chosen_provider

            logger.info(
                "Successfully purchased domain %s for %.2f using provider %s",
                domain,
                normalized_price,
                chosen_provider
            )
            return True

        logger.error("Failed to purchase domain via %s: %s", chosen_provider, result.get("message"))
        return False

    def rotate_domain(self, max_price: float = 5.0, max_attempts: int = 10) -> Optional[str]:
        """
        Rotate to a new domain.
        Finds and purchases a cheap domain based on selection strategy.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price, max_attempts=max_attempts)
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider_name=domain_info.get("provider")
        )
        if success:
            self.active_domain = domain_info["domain"]
            self.active_provider = domain_info.get("provider")
            return self.active_domain
        return None

    def rotate_to_new_domain(self, max_price: float = 5.0, max_attempts: int = 10) -> Dict[str, Any]:
        """
        Backward-compatible helper that returns structured result data.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price, max_attempts=max_attempts)
        if not domain_info:
            return {"success": False, "error": "Could not find available cheap domain"}

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider_name=domain_info.get("provider")
        )
        if not success:
            return {"success": False, "error": "Domain purchase failed", "provider": domain_info.get("provider")}

        self.active_domain = domain_info["domain"]
        self.active_provider = domain_info.get("provider")
        return {
            "success": True,
            "domain": domain_info["domain"],
            "cost": domain_info["price"],
            "provider": domain_info.get("provider")
        }

    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain."""
        return self.active_domain

    def get_owned_domains(self) -> List[Dict[str, Any]]:
        """Get list of owned domains."""
        return self.owned_domains

    def get_budget_status(self) -> Dict[str, Any]:
        """Get global and per-provider budget information."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "provider_spending": dict(self.provider_spending),
            "provider_budgets": dict(self.provider_budgets),
            "selection_strategy": self.selection_strategy,
            "active_provider": self.active_provider
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
