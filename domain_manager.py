"""
Domain management and API integration.
Supports automated domain purchasing for burner email rotation.
"""

from datetime import datetime, timedelta
import logging
import random
import re
import string
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """Base class for domain registrar API clients."""

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search if domain is available."""
        raise NotImplementedError

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase domain."""
        raise NotImplementedError

    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing for TLD."""
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

    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request."""
        url = f"{self.BASE_URL}/{endpoint}"
        payload: Dict[str, Any] = {
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

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check if domain is available."""
        result = self._make_request("domain/check", {"domain": domain})
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and bool(result.get("isAvailable", False)),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase domain and return normalized response payload."""
        result = self._make_request("domain/create", {"domain": domain, "years": years})
        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId"),
            "currency": "USD",
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get pricing for TLD."""
        result = self._make_request("pricing/get", {"tld": tld})
        if result.get("status") != "SUCCESS":
            return {}

        pricing = result.get("pricing", {})
        return {
            "tld": tld,
            "registration": pricing.get("registration"),
            "renewal": pricing.get("renewal"),
            "transfer": pricing.get("transfer"),
            "currency": "USD",
        }

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("domain/listAll")
        if result.get("status") != "SUCCESS":
            return []
        return [d.get("domain") for d in result.get("domains", []) if d.get("domain")]


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap XML API client for domain management.
    Docs: https://www.namecheap.com/support/api/
    """

    PRODUCTION_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: str,
        client_ip: str,
        use_sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key=api_key)
        self.api_user = api_user
        self.username = username
        self.client_ip = client_ip
        self.base_url = self.SANDBOX_URL if use_sandbox else self.PRODUCTION_URL
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make Namecheap request and parse XML response."""
        payload: Dict[str, Any] = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "Command": command,
            "ClientIp": self.client_ip,
        }
        if params:
            payload.update(params)

        try:
            response = self.session.get(self.base_url, params=payload, timeout=30)
            response.raise_for_status()
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return {"success": False, "error": str(exc)}

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            logger.error("Namecheap XML parse failed: %s", exc)
            return {"success": False, "error": f"Invalid XML response: {exc}"}

        status_ok = root.attrib.get("Status", "").upper() == "OK"
        error_node = root.find(".//{*}Errors/{*}Error")
        error_text = error_node.text if error_node is not None and error_node.text else None

        return {
            "success": status_ok and error_text is None,
            "root": root,
            "error": error_text,
        }

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check if domain is available."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not result.get("success"):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": result.get("error"),
            }

        root = result["root"]
        check = root.find(".//{*}DomainCheckResult")
        if check is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "Missing DomainCheckResult",
            }

        available = check.attrib.get("Available", "").lower() in ("true", "1", "yes")
        price = (
            check.attrib.get("PremiumRegistrationPrice")
            or check.attrib.get("RegistrationPrice")
            or check.attrib.get("Price")
        )
        return {
            "domain": check.attrib.get("Domain", domain),
            "available": available,
            "price": price,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase a domain with Namecheap.

        Contact profile is mandatory for live purchases.
        """
        if "." not in domain:
            return {"success": False, "domain": domain, "message": "Invalid domain format"}
        if not self.contact_profile:
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap contact profile required for purchase",
            }

        required = [
            "first_name",
            "last_name",
            "address1",
            "city",
            "state_province",
            "postal_code",
            "country",
            "phone",
            "email_address",
        ]
        missing = [field for field in required if not self.contact_profile.get(field)]
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": f"Missing contact fields: {', '.join(missing)}",
            }

        sld, tld = domain.rsplit(".", 1)
        contact = {
            "FirstName": self.contact_profile["first_name"],
            "LastName": self.contact_profile["last_name"],
            "Address1": self.contact_profile["address1"],
            "City": self.contact_profile["city"],
            "StateProvince": self.contact_profile["state_province"],
            "PostalCode": self.contact_profile["postal_code"],
            "Country": self.contact_profile["country"],
            "Phone": self.contact_profile["phone"],
            "EmailAddress": self.contact_profile["email_address"],
        }
        if self.contact_profile.get("organization"):
            contact["OrganizationName"] = self.contact_profile["organization"]

        params: Dict[str, Any] = {
            "SLD": sld,
            "TLD": tld,
            "Years": years,
            "AddFreeWhoisguard": "yes",
            "WGEnabled": "yes",
        }
        for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field, value in contact.items():
                params[f"{role}{field}"] = value

        result = self._make_request("namecheap.domains.create", params)
        if not result.get("success"):
            return {
                "success": False,
                "domain": domain,
                "message": result.get("error") or "Namecheap API error",
            }

        create_result = result["root"].find(".//{*}DomainCreateResult")
        registered = (
            create_result is not None
            and create_result.attrib.get("Registered", "").lower() in ("true", "1", "yes")
        )
        order_id = create_result.attrib.get("OrderID") if create_result is not None else None
        return {
            "success": registered,
            "domain": domain,
            "message": "Domain purchased successfully" if registered else "Purchase not confirmed",
            "order_id": order_id,
            "currency": "USD",
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get registration pricing for a TLD."""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "REGISTER",
                "ProductName": tld,
            },
        )
        if not result.get("success"):
            return {}

        root = result["root"]
        product = (
            root.find(f".//{{*}}Product[@Name='.{tld}']")
            or root.find(f".//{{*}}Product[@Name='{tld}']")
            or root.find(".//{*}Product")
        )
        if product is None:
            return {}

        price_node = product.find(".//{*}Price")
        if price_node is None:
            return {}

        registration = price_node.attrib.get("YourPrice") or price_node.attrib.get("Price")
        return {
            "tld": tld,
            "registration": registration,
            "renewal": registration,
            "transfer": None,
            "currency": "USD",
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Supports multiple registrar providers with fallback ordering.
    """

    def __init__(self, api_client: Optional[DomainAPIClient] = None, monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict[str, Any]] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False

        if api_client:
            self.add_api_client("default", api_client)

    def _provider_order(self, provider_name: Optional[str] = None) -> List[str]:
        """Return providers in preferred order."""
        if provider_name:
            requested = provider_name.strip().lower()
            return [requested] if requested in self.api_clients else []

        ordered: List[str] = []
        if self.active_provider and self.active_provider in self.api_clients:
            ordered.append(self.active_provider)
        for name in self.api_clients:
            if name not in ordered:
                ordered.append(name)
        return ordered

    def _resolve_client(self, provider_name: Optional[str] = None) -> Optional[Tuple[str, DomainAPIClient]]:
        providers = self._provider_order(provider_name)
        if not providers:
            return None
        selected = providers[0]
        self.active_provider = selected
        self.api_client = self.api_clients[selected]
        return selected, self.api_client

    def _parse_price(self, value: Any) -> Optional[float]:
        """Normalize registrar price values to float."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    return None
        return None

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient):
        """Register an API client provider."""
        normalized = provider_name.strip().lower()
        if not normalized:
            raise ValueError("provider_name cannot be empty")
        self.api_clients[normalized] = api_client
        if not self.active_provider:
            self.active_provider = normalized
        self.api_client = self.api_clients[self.active_provider]

    def set_api_client(self, api_client: DomainAPIClient):
        """Backward-compatible single-provider setup."""
        self.add_api_client("default", api_client)

    def set_active_provider(self, provider_name: str) -> bool:
        """Select active provider."""
        normalized = provider_name.strip().lower()
        if normalized not in self.api_clients:
            logger.warning("Provider not configured: %s", provider_name)
            return False
        self.active_provider = normalized
        self.api_client = self.api_clients[normalized]
        return True

    def configure(
        self,
        api_key: str = "",
        secret_key: str = "",
        monthly_budget: Optional[float] = None,
        provider: str = "porkbun",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Configure registrar credentials from UI/API input."""
        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        provider_name = provider.strip().lower()
        if provider_name == "porkbun":
            if not api_key or not secret_key:
                raise ValueError("Porkbun requires api_key and secret_key")
            self.add_api_client("porkbun", PorkbunAPIClient(api_key, secret_key))
            self.set_active_provider("porkbun")
        elif provider_name == "namecheap":
            username = kwargs.get("namecheap_username") or kwargs.get("username")
            api_user = kwargs.get("namecheap_api_user") or kwargs.get("api_user") or username
            client_ip = kwargs.get("namecheap_client_ip") or kwargs.get("client_ip")
            sandbox = bool(kwargs.get("namecheap_sandbox", kwargs.get("use_sandbox", False)))
            contact_profile = kwargs.get("contact_profile")

            if not api_key or not username or not api_user or not client_ip:
                raise ValueError(
                    "Namecheap requires api_key, namecheap_username, "
                    "namecheap_api_user (or username), and namecheap_client_ip"
                )

            self.add_api_client(
                "namecheap",
                NamecheapAPIClient(
                    api_user=api_user,
                    api_key=api_key,
                    username=username,
                    client_ip=client_ip,
                    use_sandbox=sandbox,
                    contact_profile=contact_profile,
                ),
            )
            self.set_active_provider("namecheap")
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

        return {"success": True, "config": self.get_config()}

    def get_config(self) -> Dict[str, Any]:
        """Return safe configuration summary (without secrets)."""
        return {
            "providers": {
                name: {"client_type": client.__class__.__name__}
                for name, client in self.api_clients.items()
            },
            "active_provider": self.active_provider,
            "api_configured": bool(self.api_clients),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode,
        }

    def set_test_mode(self, enabled: bool):
        """Enable or disable dry-run mode."""
        self.test_mode = bool(enabled)

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """Generate a random domain in the requested TLD."""
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        """Compatibility alias."""
        return self.generate_random_domain(tld=tld, length=length)

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 10,
        max_attempts_per_tld: int = 4,
        provider_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for cheap available domains across providers.
        Returns candidates sorted by lowest price.
        """
        providers = self._provider_order(provider_name)
        if not providers:
            logger.error("No API client configured")
            return []

        selected_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        results: List[Dict[str, Any]] = []

        for tld in selected_tlds:
            for _ in range(max_attempts_per_tld):
                for provider in providers:
                    client = self.api_clients[provider]
                    candidate = self.generate_random_domain(tld=tld)
                    search_result = client.search_domain(candidate)
                    if not search_result.get("available"):
                        continue

                    parsed_price = self._parse_price(search_result.get("price"))
                    if parsed_price is None or parsed_price > max_price:
                        continue

                    resolved_domain = search_result.get("domain", candidate)
                    results.append(
                        {
                            "domain": resolved_domain,
                            "price": parsed_price,
                            "tld": resolved_domain.rsplit(".", 1)[-1],
                            "provider": provider,
                            "currency": search_result.get("currency", "USD"),
                        }
                    )
                    if len(results) >= limit:
                        return sorted(results, key=lambda item: item["price"])

        return sorted(results, key=lambda item: item["price"])

    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        provider_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find one cheap available domain.
        Returns domain info or None.
        """
        providers = self._provider_order(provider_name)
        if not providers:
            logger.error("No API client configured")
            return None

        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            for provider in providers:
                client = self.api_clients[provider]
                candidate = self.generate_random_domain(tld=tld)
                search_result = client.search_domain(candidate)
                if not search_result.get("available"):
                    continue

                parsed_price = self._parse_price(search_result.get("price"))
                if parsed_price is None or parsed_price > max_price:
                    continue

                resolved_domain = search_result.get("domain", candidate)
                return {
                    "domain": resolved_domain,
                    "price": parsed_price,
                    "tld": resolved_domain.rsplit(".", 1)[-1],
                    "provider": provider,
                    "currency": search_result.get("currency", "USD"),
                }

        return None

    def _purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider_name: Optional[str] = None,
    ) -> bool:
        resolved = self._resolve_client(provider_name)
        if not resolved:
            logger.error("No API client configured")
            return False
        selected_provider, client = resolved

        parsed_price = self._parse_price(price)
        if parsed_price is None:
            logger.error("Invalid price for purchase: %s", price)
            return False

        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, requested: $%s, budget: $%s",
                self.current_spending,
                parsed_price,
                self.monthly_budget,
            )
            return False

        if self.test_mode:
            purchase_result = {"success": True, "currency": "USD"}
        else:
            purchase_result = client.purchase_domain(domain, years=1)

        if not purchase_result.get("success"):
            logger.error("Failed to purchase domain: %s", purchase_result.get("message"))
            return False

        now = datetime.now()
        self.current_spending += parsed_price
        self.owned_domains.append(
            {
                "domain": domain,
                "price": parsed_price,
                "provider": selected_provider,
                "currency": purchase_result.get("currency", "USD"),
                "purchased_at": now,
                "expires_at": now + timedelta(days=365),
            }
        )

        if not self.active_domain:
            self.active_domain = domain

        logger.info(
            "Successfully purchased domain %s for $%s via %s",
            domain,
            parsed_price,
            selected_provider,
        )
        return True

    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """Purchase with active/default provider (backward-compatible signature)."""
        return self._purchase_domain_if_budget_allows(domain, price, provider_name=None)

    def purchase_domain_with_provider(self, domain: str, price: float, provider_name: str) -> bool:
        """Purchase with explicit provider selection."""
        return self._purchase_domain_if_budget_allows(domain, price, provider_name=provider_name)

    def rotate_to_new_domain(
        self,
        max_price: float = 5.0,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Rotate to a new domain and return structured result.
        """
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            provider_name=provider_name,
        )
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {"success": False, "error": "Could not find available cheap domain"}

        success = self._purchase_domain_if_budget_allows(
            domain=domain_info["domain"],
            price=domain_info["price"],
            provider_name=domain_info.get("provider"),
        )
        if not success:
            return {
                "success": False,
                "error": "Domain purchase failed or exceeded budget",
                "domain": domain_info["domain"],
                "provider": domain_info.get("provider"),
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": domain_info["domain"],
            "cost": domain_info["price"],
            "provider": domain_info.get("provider"),
            "currency": domain_info.get("currency", "USD"),
        }

    def rotate_domain(self) -> Optional[str]:
        """Backward-compatible rotate API that returns only the domain."""
        result = self.rotate_to_new_domain()
        return result.get("domain") if result.get("success") else None

    def configure_domain_dns(
        self,
        domain: str,
        mx_records: Optional[List[Dict[str, Any]]] = None,
        a_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        DNS config placeholder API.

        Keeping a structured response avoids runtime attribute errors for callers.
        """
        logger.warning("DNS configuration not implemented for %s", domain)
        return {
            "success": False,
            "error": "DNS configuration is not implemented yet",
            "domain": domain,
            "mx_records": mx_records or [],
            "a_records": a_records or [],
        }

    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain."""
        return self.active_domain

    def get_owned_domains(self) -> List[Dict[str, Any]]:
        """Get list of owned domains."""
        return self.owned_domains

    def get_budget_status(self) -> Dict[str, Any]:
        """Get budget information."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "active_provider": self.active_provider,
            "providers": list(self.api_clients.keys()),
            "test_mode": self.test_mode,
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
