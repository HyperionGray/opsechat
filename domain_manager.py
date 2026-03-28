"""
Domain management and API integration.

Supports automated domain purchasing for burner email rotation with multiple
registrar providers (Porkbun + Namecheap).
"""

from datetime import datetime, timedelta
import logging
import random
import string
from typing import Dict, Iterable, List, Optional, Tuple
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)


def _to_float(value: object, default: float = 999.0) -> float:
    """Safely parse registrar prices that may include currency symbols."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = (
            value.strip()
            .replace("$", "")
            .replace("€", "")
            .replace(",", "")
        )
        try:
            return float(normalized)
        except ValueError:
            return default
    return default


def _split_domain(domain: str) -> Tuple[Optional[str], Optional[str]]:
    """Split example.com into ('example', 'com')."""
    if "." not in domain:
        return None, None
    sld, tld = domain.rsplit(".", 1)
    if not sld or not tld:
        return None, None
    return sld, tld


class DomainAPIClient:
    """Base class for domain registrar API clients."""

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def search_domain(self, domain: str) -> Dict:
        """Search whether a domain is available."""
        raise NotImplementedError

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase a domain."""
        raise NotImplementedError

    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for a TLD."""
        raise NotImplementedError


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management.
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
            "secretapikey": self.api_secret,
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

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        result = self._make_request("domain/check", {"domain": domain})
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and bool(result.get("isAvailable", False)),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
            "provider": "porkbun",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain.
        Note: This actually purchases the domain and charges your account.
        """
        result = self._make_request(
            "domain/create",
            {"domain": domain, "years": years},
        )
        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId"),
            "provider": "porkbun",
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
                "currency": "USD",
                "provider": "porkbun",
            }
        return {}

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("domain/listAll")
        if result.get("status") == "SUCCESS":
            domains = result.get("domains", [])
            return [item.get("domain") for item in domains if item.get("domain")]
        return []


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap API client for domain management.
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str,
        api_user: Optional[str] = None,
    ):
        super().__init__(api_key)
        self.username = username
        self.client_ip = client_ip
        self.api_user = api_user or username
        self.session = requests.Session()

    @staticmethod
    def _iter_local_name(root: ET.Element, local_name: str) -> Iterable[ET.Element]:
        for elem in root.iter():
            if elem.tag.rsplit("}", 1)[-1] == local_name:
                yield elem

    @classmethod
    def _first_local_name(cls, root: ET.Element, local_name: str) -> Optional[ET.Element]:
        for elem in cls._iter_local_name(root, local_name):
            return elem
        return None

    def _make_request(self, command: str, params: Optional[Dict] = None) -> Optional[ET.Element]:
        query = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            query.update(params)

        try:
            response = self.session.get(self.BASE_URL, params=query, timeout=30)
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as exc:
            logger.error("Namecheap API request failed for %s: %s", command, exc)
            return None

    def _is_success(self, root: Optional[ET.Element]) -> bool:
        return bool(root is not None and root.attrib.get("Status", "").upper() == "OK")

    def _extract_error(self, root: Optional[ET.Element]) -> str:
        if root is None:
            return "request failed"
        errors = [err.text for err in self._iter_local_name(root, "Error") if err.text]
        return "; ".join(errors) if errors else "unknown Namecheap API error"

    def search_domain(self, domain: str) -> Dict:
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not self._is_success(root):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": "namecheap",
                "error": self._extract_error(root),
            }

        check_result = None
        assert root is not None
        for candidate in self._iter_local_name(root, "DomainCheckResult"):
            if candidate.attrib.get("Domain", "").lower() == domain.lower():
                check_result = candidate
                break
        if check_result is None:
            check_result = self._first_local_name(root, "DomainCheckResult")

        if check_result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": "namecheap",
                "error": "missing DomainCheckResult",
            }

        available = check_result.attrib.get("Available", "false").lower() == "true"
        price = (
            check_result.attrib.get("PremiumRegistrationPrice")
            or check_result.attrib.get("RegistrationPrice")
        )
        return {
            "domain": domain,
            "available": available,
            "price": _to_float(price, default=999.0) if price is not None else None,
            "currency": "USD",
            "provider": "namecheap",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase a domain from Namecheap.

        Namecheap typically requires a preconfigured account profile and an
        allowed client IP. This call uses auto-generated contacts if available.
        """
        sld, tld = _split_domain(domain)
        if not sld or not tld:
            return {
                "success": False,
                "domain": domain,
                "provider": "namecheap",
                "message": "invalid domain format",
            }

        root = self._make_request(
            "namecheap.domains.create",
            {
                "DomainName": domain,
                "Years": years,
                "AddFreeWhoisguard": "yes",
                "WGEnabled": "yes",
                "UseAutoGenContacts": "yes",
            },
        )
        success = self._is_success(root)
        order_id = None
        if root is not None:
            create_result = self._first_local_name(root, "DomainCreateResult")
            if create_result is not None:
                order_id = create_result.attrib.get("OrderID")

        return {
            "success": success,
            "domain": domain,
            "provider": "namecheap",
            "message": "" if success else self._extract_error(root),
            "order_id": order_id,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        root = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ProductName": tld,
                "ActionName": "register",
            },
        )
        if not self._is_success(root):
            return {}

        registration_price = None
        assert root is not None
        for product_price in self._iter_local_name(root, "ProductPrice"):
            duration = product_price.attrib.get("Duration")
            if duration in (None, "1"):
                registration_price = product_price.attrib.get("Price")
                break

        return {
            "tld": tld,
            "registration": _to_float(registration_price, default=0.0) if registration_price else None,
            "currency": "USD",
            "provider": "namecheap",
        }

    def list_domains(self) -> List[str]:
        root = self._make_request("namecheap.domains.getList", {"PageSize": 100, "Page": 1})
        if not self._is_success(root):
            return []

        names: List[str] = []
        assert root is not None
        for domain_elem in self._iter_local_name(root, "Domain"):
            name = domain_elem.attrib.get("Name")
            if name:
                names.append(name)
        return names


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Automatically purchases cheap domains and rotates active domain.
    """

    CHEAP_TLDS = ["xyz", "club", "online", "site", "website"]

    def __init__(self, api_client: Optional[DomainAPIClient] = None, monthly_budget: float = 50.0):
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.default_provider: Optional[str] = None
        self.provider_metadata: Dict[str, Dict] = {}

        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client is not None:
            self.set_api_client(api_client, provider_name="default", make_default=True)

    @property
    def api_client(self) -> Optional[DomainAPIClient]:
        """Backward-compatible single-client accessor."""
        if self.default_provider and self.default_provider in self.api_clients:
            return self.api_clients[self.default_provider]
        if self.api_clients:
            return next(iter(self.api_clients.values()))
        return None

    def set_api_client(
        self,
        api_client: DomainAPIClient,
        provider_name: str = "default",
        make_default: bool = True,
    ) -> None:
        """Set/replace a provider client."""
        self.api_clients[provider_name] = api_client
        if make_default or not self.default_provider:
            self.default_provider = provider_name

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient, make_default: bool = False) -> None:
        """Add an additional provider client."""
        self.set_api_client(api_client, provider_name=provider_name, make_default=make_default)

    def list_providers(self) -> List[str]:
        return sorted(self.api_clients.keys())

    def get_active_provider(self) -> Optional[str]:
        return self.default_provider

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: float = 50.0,
        provider: str = "porkbun",
        username: Optional[str] = None,
        client_ip: Optional[str] = None,
        api_user: Optional[str] = None,
        set_default: bool = True,
    ) -> Dict:
        """Configure and register a provider client."""
        provider_name = provider.lower().strip()
        self.monthly_budget = monthly_budget

        if provider_name == "porkbun":
            if not secret_key:
                return {"success": False, "message": "Porkbun secret_key is required"}
            client = PorkbunAPIClient(api_key, secret_key)
            self.add_api_client("porkbun", client, make_default=set_default)
            self.provider_metadata["porkbun"] = {
                "provider": "porkbun",
                "configured": True,
                "api_key_suffix": api_key[-4:] if len(api_key) >= 4 else api_key,
            }
            return {"success": True, "provider": "porkbun"}

        if provider_name == "namecheap":
            if not username or not client_ip:
                return {
                    "success": False,
                    "message": "Namecheap username and client_ip are required",
                }
            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                api_user=api_user,
            )
            self.add_api_client("namecheap", client, make_default=set_default)
            self.provider_metadata["namecheap"] = {
                "provider": "namecheap",
                "configured": True,
                "api_key_suffix": api_key[-4:] if len(api_key) >= 4 else api_key,
                "username": username,
                "client_ip": client_ip,
                "api_user": api_user or username,
            }
            return {"success": True, "provider": "namecheap"}

        return {"success": False, "message": f"Unsupported provider: {provider}"}

    def get_config(self) -> Dict:
        """Return non-secret provider configuration summary."""
        return {
            "default_provider": self.default_provider,
            "providers": self.list_providers(),
            "provider_metadata": self.provider_metadata,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def _iter_clients(self, preferred: Optional[List[str]] = None) -> Iterable[Tuple[str, DomainAPIClient]]:
        seen = set()
        if preferred:
            for provider in preferred:
                if provider in self.api_clients and provider not in seen:
                    seen.add(provider)
                    yield provider, self.api_clients[provider]
        if self.default_provider and self.default_provider in self.api_clients and self.default_provider not in seen:
            seen.add(self.default_provider)
            yield self.default_provider, self.api_clients[self.default_provider]
        for provider, client in self.api_clients.items():
            if provider not in seen:
                seen.add(provider)
                yield provider, client

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """Generate random domain name."""
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    # Backward-compatible alias used in older docs and scripts.
    generate_random_domain_name = generate_random_domain

    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        preferred_providers: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """Find a cheap available domain across configured providers."""
        if not self.api_clients:
            logger.error("No API client configured")
            return None

        for _ in range(max_attempts):
            tld = random.choice(self.CHEAP_TLDS)
            domain = self.generate_random_domain(tld)

            for provider, client in self._iter_clients(preferred_providers):
                result = client.search_domain(domain)
                if not result.get("available"):
                    continue

                price = _to_float(result.get("price"), default=999.0)
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider,
                    }
        return None

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 5,
        attempts_per_tld: int = 3,
        preferred_providers: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Search for multiple cheap available domains.
        Returns up to `limit` results.
        """
        if not self.api_clients:
            logger.error("No API client configured")
            return []

        candidates = tlds or self.CHEAP_TLDS
        results: List[Dict] = []
        seen_domains = set()
        max_attempts = max(1, len(candidates) * max(1, attempts_per_tld))

        for _ in range(max_attempts):
            if len(results) >= limit:
                break
            tld = random.choice(candidates)
            domain = self.generate_random_domain(tld)
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            for provider, client in self._iter_clients(preferred_providers):
                search_result = client.search_domain(domain)
                if not search_result.get("available"):
                    continue
                price = _to_float(search_result.get("price"), default=999.0)
                if price <= max_price:
                    results.append(
                        {
                            "domain": domain,
                            "price": price,
                            "tld": tld,
                            "provider": provider,
                        }
                    )
                    break
        return results

    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider: Optional[str] = None,
    ) -> bool:
        """Purchase domain if within budget."""
        if not self.api_clients:
            logger.error("No API client configured")
            return False

        selected_provider = provider or self.default_provider
        if selected_provider not in self.api_clients:
            selected_provider = next(iter(self.api_clients.keys()))

        if self.current_spending + price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                price,
                self.monthly_budget,
            )
            return False

        result = self.api_clients[selected_provider].purchase_domain(domain, years=1)
        if not result.get("success"):
            logger.error("Failed to purchase domain via %s: %s", selected_provider, result.get("message"))
            return False

        now = datetime.now()
        self.current_spending += price
        self.owned_domains.append(
            {
                "domain": domain,
                "price": price,
                "provider": selected_provider,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365),
            }
        )
        if not self.active_domain:
            self.active_domain = domain

        logger.info(
            "Successfully purchased domain %s for $%s via provider %s",
            domain,
            price,
            selected_provider,
        )
        return True

    def rotate_domain(self, provider: Optional[str] = None) -> Optional[str]:
        """Rotate to a new domain and return its name on success."""
        preferred = [provider] if provider else None
        domain_info = self.find_cheap_available_domain(preferred_providers=preferred)
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider=domain_info.get("provider") or provider,
        )
        if success:
            self.active_domain = domain_info["domain"]
            return self.active_domain
        return None

    def rotate_to_new_domain(
        self,
        max_price: float = 5.0,
        provider: Optional[str] = None,
    ) -> Dict:
        """
        Rotate to a new domain and return a detailed status payload.
        Compatible with existing route handlers expecting dict responses.
        """
        preferred = [provider] if provider else None
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            preferred_providers=preferred,
        )
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain",
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider=domain_info.get("provider") or provider,
        )
        if not success:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded",
                "domain": domain_info["domain"],
                "provider": domain_info.get("provider"),
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": domain_info["domain"],
            "price": domain_info["price"],
            "provider": domain_info.get("provider"),
        }

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
            "domains_owned": len(self.owned_domains),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
