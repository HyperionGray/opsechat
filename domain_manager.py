"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation.
"""

import logging
import random
import string
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """Base interface for domain registrar API clients."""

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    def search_domain(self, domain: str) -> Dict:
        """Search if a domain is available."""

    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase a domain."""

    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for a TLD."""


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
            "provider": "porkbun",
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and result.get("isAvailable", False),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain.
        Note: This actually purchases the domain and charges your account.
        """
        result = self._make_request("domain/create", {"domain": domain, "years": years})

        return {
            "success": result.get("status") == "SUCCESS",
            "provider": "porkbun",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId"),
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get pricing for TLD."""
        result = self._make_request("pricing/get", {"tld": tld})

        if result.get("status") == "SUCCESS":
            pricing = result.get("pricing", {})
            return {
                "provider": "porkbun",
                "tld": tld,
                "registration": pricing.get("registration"),
                "renewal": pricing.get("renewal"),
                "transfer": pricing.get("transfer"),
                "currency": "USD",
            }

        return {}

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("domain/listAll")

        if result.get("status") == "SUCCESS":
            domains = result.get("domains", [])
            return [d.get("domain") for d in domains if d.get("domain")]

        return []


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap XML API client for domain management.
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        api_user: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key=api_key, api_secret=None)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    def _response_has_errors(self, root: ET.Element) -> bool:
        return root.find(".//{*}Errors/{*}Error") is not None

    def _collect_errors(self, root: ET.Element) -> List[str]:
        errors = []
        for error in root.findall(".//{*}Errors/{*}Error"):
            text = (error.text or "").strip()
            if text:
                errors.append(text)
        return errors

    def _make_request(self, command: str, params: Optional[Dict] = None) -> Dict:
        base_url = self.SANDBOX_URL if self.sandbox else self.BASE_URL
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
            response = self.session.get(base_url, params=query, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            status = root.attrib.get("Status", "ERROR")
            errors = self._collect_errors(root)
            if status != "OK" or self._response_has_errors(root):
                return {"status": "ERROR", "errors": errors or [f"{command} failed"], "root": root}
            return {"status": "SUCCESS", "errors": [], "root": root}
        except Exception as exc:
            logger.error("Namecheap API request failed (%s): %s", command, exc)
            return {"status": "ERROR", "errors": [str(exc)], "root": None}

    def _build_contact_payload(self) -> Dict:
        required_keys = [
            "FirstName",
            "LastName",
            "Address1",
            "City",
            "StateProvince",
            "PostalCode",
            "Country",
            "Phone",
            "EmailAddress",
        ]
        missing = [key for key in required_keys if not self.contact_profile.get(key)]
        if missing:
            return {"_error": f"Missing Namecheap contact_profile keys: {', '.join(missing)}"}

        payload = {}
        for prefix in ["Registrant", "Tech", "Admin", "AuxBilling"]:
            for key in required_keys:
                payload[f"{prefix}{key}"] = self.contact_profile[key]
            payload[f"{prefix}Address2"] = self.contact_profile.get("Address2", "")
            payload[f"{prefix}OrganizationName"] = self.contact_profile.get("OrganizationName", "")
            payload[f"{prefix}PhoneExt"] = self.contact_profile.get("PhoneExt", "")
        return payload

    def search_domain(self, domain: str) -> Dict:
        """Check if a domain is available."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if result["status"] != "SUCCESS":
            return {
                "provider": "namecheap",
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "; ".join(result.get("errors", [])),
            }

        root = result["root"]
        node = root.find(".//{*}DomainCheckResult")
        if node is None:
            return {
                "provider": "namecheap",
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "Malformed Namecheap response",
            }

        is_available = node.attrib.get("Available", "").lower() == "true"
        regular_price = node.attrib.get("RegistrationPrice")
        premium_price = node.attrib.get("PremiumRegistrationPrice")
        is_premium = node.attrib.get("IsPremiumName", "").lower() == "true"
        selected_price = premium_price if is_premium and premium_price else regular_price
        return {
            "provider": "namecheap",
            "domain": domain,
            "available": is_available,
            "price": selected_price,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase a domain using Namecheap API."""
        sld, dot, tld = domain.partition(".")
        if not sld or not dot or not tld:
            return {
                "success": False,
                "provider": "namecheap",
                "domain": domain,
                "message": "Invalid domain format",
            }

        contact_payload = self._build_contact_payload()
        if "_error" in contact_payload:
            return {
                "success": False,
                "provider": "namecheap",
                "domain": domain,
                "message": contact_payload["_error"],
            }

        params = {"SLD": sld, "TLD": tld, "Years": years}
        params.update(contact_payload)
        result = self._make_request("namecheap.domains.create", params)
        if result["status"] != "SUCCESS":
            return {
                "success": False,
                "provider": "namecheap",
                "domain": domain,
                "message": "; ".join(result.get("errors", [])),
            }

        root = result["root"]
        create_result = root.find(".//{*}DomainCreateResult")
        if create_result is None:
            return {
                "success": False,
                "provider": "namecheap",
                "domain": domain,
                "message": "Malformed Namecheap create response",
            }

        registered = create_result.attrib.get("Registered", "").lower() == "true"
        return {
            "success": registered,
            "provider": "namecheap",
            "domain": domain,
            "message": "" if registered else "Domain registration failed",
            "order_id": create_result.attrib.get("OrderID"),
            "charged_amount": create_result.attrib.get("ChargedAmount"),
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get registration pricing for a TLD."""
        clean_tld = tld.lower().lstrip(".")
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "DOMAINS",
                "ActionName": "REGISTER",
                "ProductName": clean_tld,
            },
        )
        if result["status"] != "SUCCESS":
            return {}

        root = result["root"]
        price = None
        for product in root.findall(".//{*}Product"):
            name = product.attrib.get("Name", "").lower().lstrip(".")
            if not name or name != clean_tld:
                continue
            product_price = product.find(".//{*}Price")
            if product_price is not None and product_price.attrib.get("Price"):
                price = product_price.attrib.get("Price")
                break
        if price is None:
            product_price = root.find(".//{*}Price")
            if product_price is not None:
                price = product_price.attrib.get("Price")

        if price is None:
            return {}
        return {
            "provider": "namecheap",
            "tld": clean_tld,
            "registration": price,
            "currency": "USD",
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Supports multi-registrar search and purchase with fallback providers.
    """

    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
        provider_name: str = "porkbun",
    ):
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.primary_provider: Optional[str] = None
        self.fallback_providers: List[str] = []
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        if api_client:
            self.register_api_client(provider_name, api_client, set_primary=True)

    @property
    def api_client(self) -> Optional[DomainAPIClient]:
        """Backward-compatible accessor for the primary API client."""
        if not self.primary_provider:
            return None
        return self.api_clients.get(self.primary_provider)

    def _parse_price(self, price_value) -> Optional[float]:
        if isinstance(price_value, (int, float)):
            return float(price_value)
        if isinstance(price_value, str):
            cleaned = (
                price_value.replace("$", "")
                .replace("€", "")
                .replace("USD", "")
                .replace(",", "")
                .strip()
            )
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _mask_secret(self, value: str) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * max(8, len(value) - 4)}{value[-4:]}"

    def _provider_order(self) -> List[str]:
        if not self.primary_provider and not self.api_clients:
            return []
        ordered = []
        if self.primary_provider and self.primary_provider in self.api_clients:
            ordered.append(self.primary_provider)
        for provider in self.fallback_providers:
            if provider in self.api_clients and provider not in ordered:
                ordered.append(provider)
        for provider in self.api_clients:
            if provider not in ordered:
                ordered.append(provider)
        return ordered

    def set_api_client(self, api_client: DomainAPIClient, provider_name: str = "porkbun"):
        """Set the domain API client (backward compatible)."""
        self.register_api_client(provider_name, api_client, set_primary=True)

    def add_api_client(self, provider: str, api_client: DomainAPIClient, set_primary: bool = False):
        """Compatibility alias for adding API clients."""
        self.register_api_client(provider, api_client, set_primary=set_primary)

    def register_api_client(
        self,
        provider: str,
        api_client: DomainAPIClient,
        set_primary: bool = False,
    ) -> None:
        """Register an API client under a provider key."""
        provider_key = provider.lower().strip()
        if not provider_key:
            raise ValueError("Provider name must be non-empty")
        self.api_clients[provider_key] = api_client
        if set_primary or self.primary_provider is None:
            self.primary_provider = provider_key

    def set_primary_provider(self, provider: str) -> None:
        provider_key = provider.lower().strip()
        if provider_key not in self.api_clients:
            raise ValueError(f"Provider '{provider}' is not configured")
        self.primary_provider = provider_key

    def set_fallback_providers(self, providers: List[str]) -> None:
        cleaned = []
        for provider in providers:
            provider_key = provider.lower().strip()
            if not provider_key or provider_key == self.primary_provider:
                continue
            if provider_key in self.api_clients and provider_key not in cleaned:
                cleaned.append(provider_key)
        self.fallback_providers = cleaned

    def configure(
        self,
        api_key: str,
        secret_key: str = "",
        monthly_budget: float = 50.0,
        provider: str = "porkbun",
        **kwargs,
    ) -> Dict:
        """
        Configure the global manager with an API provider.
        Supports provider='porkbun' or provider='namecheap'.
        """
        provider_key = provider.lower().strip()
        self.monthly_budget = float(monthly_budget)

        if provider_key == "porkbun":
            if not secret_key:
                raise ValueError("Porkbun requires secret_key")
            client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
        elif provider_key == "namecheap":
            api_user = kwargs.get("api_user") or kwargs.get("username")
            client_ip = kwargs.get("client_ip", "127.0.0.1")
            if not api_user:
                raise ValueError("Namecheap requires api_user or username")
            client = NamecheapAPIClient(
                api_key=api_key,
                api_user=api_user,
                username=kwargs.get("username", api_user),
                client_ip=client_ip,
                sandbox=bool(kwargs.get("sandbox", False)),
                contact_profile=kwargs.get("contact_profile"),
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self.register_api_client(provider_key, client, set_primary=True)
        fallback = kwargs.get("fallback_providers")
        if isinstance(fallback, list):
            self.set_fallback_providers(fallback)
        return self.get_config()

    def get_config(self) -> Dict:
        """Get current domain manager configuration without exposing secrets."""
        provider_summary = {}
        for provider_name, client in self.api_clients.items():
            provider_summary[provider_name] = {
                "configured": True,
                "api_key_masked": self._mask_secret(getattr(client, "api_key", "")),
            }
            if isinstance(client, NamecheapAPIClient):
                provider_summary[provider_name].update(
                    {
                        "api_user": client.api_user,
                        "username": client.username,
                        "client_ip": client.client_ip,
                        "sandbox": client.sandbox,
                        "contact_profile_configured": bool(client.contact_profile),
                    }
                )

        return {
            "configured": bool(self.api_clients),
            "primary_provider": self.primary_provider,
            "fallback_providers": self.fallback_providers[:],
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "providers": provider_summary,
        }

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name.
        Uses cheap TLDs like .xyz, .club, .online.
        """
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain across configured providers.
        Returns domain info dict or None.
        """
        provider_order = self._provider_order()
        if not provider_order:
            logger.error("No API clients configured")
            return None

        cheap_tlds = ["xyz", "club", "online", "site", "website"]

        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for provider in provider_order:
                client = self.api_clients[provider]
                try:
                    result = client.search_domain(domain)
                except Exception as exc:
                    logger.warning("Provider '%s' search failed for %s: %s", provider, domain, exc)
                    continue

                if not result.get("available"):
                    continue

                price = self._parse_price(result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
                    if pricing:
                        price = self._parse_price(pricing.get("registration"))

                if price is None:
                    logger.warning("Provider '%s' returned unknown price for %s", provider, domain)
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider,
                    }

        return None

    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider: Optional[str] = None,
    ) -> bool:
        """
        Purchase domain if within budget.
        Returns True on success.
        """
        provider_order = self._provider_order()
        if not provider_order:
            logger.error("No API clients configured")
            return False

        parsed_price = self._parse_price(price)
        if parsed_price is None:
            logger.error("Invalid domain price value: %s", price)
            return False

        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                parsed_price,
                self.monthly_budget,
            )
            return False

        selected_provider = (provider or self.primary_provider or "").lower().strip()
        if selected_provider not in self.api_clients:
            selected_provider = provider_order[0]

        client = self.api_clients[selected_provider]
        result = client.purchase_domain(domain, years=1)

        if result.get("success"):
            now = datetime.now()
            self.current_spending += parsed_price
            self.owned_domains.append(
                {
                    "domain": domain,
                    "provider": selected_provider,
                    "price": parsed_price,
                    "purchased_at": now,
                    "expires_at": now + timedelta(days=365),
                }
            )

            if not self.active_domain:
                self.active_domain = domain

            logger.info(
                "Successfully purchased domain: %s via %s for $%s",
                domain,
                selected_provider,
                parsed_price,
            )
            return True

        logger.error("Failed to purchase domain via %s: %s", selected_provider, result.get("message"))
        return False

    def rotate_domain_with_result(self, max_price: float = 5.0) -> Dict:
        """
        Rotate to a new domain and return status details.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {"success": False, "error": "Could not find available cheap domain"}

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider=domain_info.get("provider"),
        )
        if not success:
            return {
                "success": False,
                "error": "Failed to purchase domain",
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

    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain.
        Returns the active domain on success, else None.
        """
        result = self.rotate_domain_with_result()
        if result.get("success"):
            return result.get("domain")
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
            "domains_owned": len(self.owned_domains),
            "primary_provider": self.primary_provider,
            "providers_configured": list(self.api_clients.keys()),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
