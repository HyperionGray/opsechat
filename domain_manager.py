"""
Domain management and API integration.
Supports automated domain purchasing for burner email rotation.
"""

import logging
import random
import string
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


def _mask_secret(secret: Optional[str]) -> Optional[str]:
    if not secret:
        return secret
    if len(secret) <= 6:
        return "*" * len(secret)
    return f"{secret[:2]}{'*' * (len(secret) - 4)}{secret[-2:]}"


def _coerce_price(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip().replace("$", "").replace("€", "").replace(",", "")
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients.
    """

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available."""

    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain."""

    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD."""


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

        payload = {"apikey": self.api_key, "secretapikey": self.api_secret}

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
            "available": result.get("status") == "SUCCESS"
            and result.get("isAvailable", False),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
            "provider": "porkbun",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain.
        Note: This actually purchases the domain and charges your account.
        """
        result = self._make_request("domain/create", {"domain": domain, "years": years})

        return {
            "success": result.get("status") == "SUCCESS",
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
    SANDBOX_BASE_URL = "https://api.sandbox.namecheap.com/xml.response"

    REQUIRED_CONTACT_FIELDS = (
        "FirstName",
        "LastName",
        "Address1",
        "City",
        "StateProvince",
        "PostalCode",
        "Country",
        "Phone",
        "EmailAddress",
    )

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: Optional[str] = None,
        client_ip: Optional[str] = None,
        sandbox: bool = False,
        default_contacts: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key=api_key)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip or "127.0.0.1"
        self.base_url = self.SANDBOX_BASE_URL if sandbox else self.BASE_URL
        self.default_contacts = default_contacts or {}
        self.session = requests.Session()

    @staticmethod
    def _iter_elements(root: ET.Element, element_name: str) -> Iterable[ET.Element]:
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] == element_name:
                yield element

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> Dict:
        params: Dict[str, Any] = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }

        if data:
            for key, value in data.items():
                if value is not None:
                    params[key] = value

        try:
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            status = root.attrib.get("Status", "").upper()
            errors = [
                (error.text or "").strip()
                for error in self._iter_elements(root, "Error")
                if (error.text or "").strip()
            ]
            return {
                "status": "SUCCESS" if status == "OK" and not errors else "ERROR",
                "errors": errors,
                "root": root,
            }
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return {"status": "ERROR", "errors": [str(exc)], "root": None}

    def search_domain(self, domain: str) -> Dict:
        result = self._make_request(
            "namecheap.domains.check",
            {"DomainList": domain},
        )

        if result["status"] != "SUCCESS" or result["root"] is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": "namecheap",
                "error": "; ".join(result.get("errors", [])),
            }

        available = False
        for domain_check in self._iter_elements(result["root"], "DomainCheckResult"):
            available = str(domain_check.attrib.get("Available", "")).lower() == "true"
            break

        tld = domain.rsplit(".", 1)[-1] if "." in domain else domain
        pricing = self.get_pricing(tld) if available else {}
        return {
            "domain": domain,
            "available": available,
            "price": pricing.get("registration"),
            "currency": pricing.get("currency", "USD"),
            "provider": "namecheap",
        }

    def _build_contact_payload(self) -> Optional[Dict[str, str]]:
        if not self.default_contacts:
            return None

        payload: Dict[str, str] = {}
        for section in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field in self.REQUIRED_CONTACT_FIELDS:
                section_field = f"{section}{field}"
                if section_field in self.default_contacts:
                    payload[section_field] = self.default_contacts[section_field]
                    continue

                generic_field = field
                if generic_field not in self.default_contacts:
                    return None
                payload[section_field] = self.default_contacts[generic_field]
        return payload

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        contact_payload = self._build_contact_payload()
        if not contact_payload:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Namecheap purchase requires default contact fields. "
                    "Provide contact info when creating NamecheapAPIClient."
                ),
            }

        result = self._make_request(
            "namecheap.domains.create",
            {
                "DomainName": domain,
                "Years": years,
                **contact_payload,
            },
        )
        if result["status"] != "SUCCESS" or result["root"] is None:
            return {
                "success": False,
                "domain": domain,
                "message": "; ".join(result.get("errors", [])),
            }

        order_id = None
        for created in self._iter_elements(result["root"], "DomainCreateResult"):
            order_id = created.attrib.get("OrderID")
            break

        return {
            "success": True,
            "domain": domain,
            "message": "Domain purchase completed via Namecheap API",
            "order_id": order_id,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductName": tld.upper(),
            },
        )
        if result["status"] != "SUCCESS" or result["root"] is None:
            return {}

        registration_price = None
        renewal_price = None
        for price in self._iter_elements(result["root"], "Price"):
            duration = price.attrib.get("Duration")
            if duration not in (None, "1"):
                continue
            if price.attrib.get("ProductType", "").upper() != "DOMAIN":
                continue
            registration_price = (
                price.attrib.get("YourPrice")
                or price.attrib.get("RegularPrice")
                or registration_price
            )
            renewal_price = price.attrib.get("RegularPrice") or renewal_price
            if registration_price:
                break

        return {
            "tld": tld,
            "registration": _coerce_price(registration_price),
            "renewal": _coerce_price(renewal_price),
            "transfer": None,
            "currency": "USD",
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Automatically purchase cheap domains and rotate them.
    """

    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
    ):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.provider_configs: Dict[str, Dict[str, Any]] = {}
        self.primary_provider: Optional[str] = None

        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client:
            inferred = self._infer_provider_name(api_client)
            self.add_api_client(inferred, api_client, set_primary=True)

    @staticmethod
    def _normalize_provider_name(name: str) -> str:
        return name.strip().lower().replace(" ", "_")

    @staticmethod
    def _infer_provider_name(api_client: DomainAPIClient) -> str:
        class_name = api_client.__class__.__name__.lower()
        if "porkbun" in class_name:
            return "porkbun"
        if "namecheap" in class_name:
            return "namecheap"
        return class_name.replace("apiclient", "")

    def _update_primary_alias(self):
        if self.primary_provider and self.primary_provider in self.api_clients:
            self.api_client = self.api_clients[self.primary_provider]
        elif self.api_clients:
            first_provider = next(iter(self.api_clients))
            self.primary_provider = first_provider
            self.api_client = self.api_clients[first_provider]
        else:
            self.api_client = None
            self.primary_provider = None

    def set_api_client(self, api_client: DomainAPIClient):
        """Set the primary domain API client."""
        provider_name = self._infer_provider_name(api_client)
        self.add_api_client(provider_name, api_client, set_primary=True)

    def add_api_client(
        self,
        provider_name: str,
        api_client: DomainAPIClient,
        set_primary: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Register a domain API client provider."""
        normalized = self._normalize_provider_name(provider_name)
        self.api_clients[normalized] = api_client
        if config:
            self.provider_configs[normalized] = config
        elif normalized not in self.provider_configs:
            self.provider_configs[normalized] = {}
        if set_primary or not self.primary_provider:
            self.primary_provider = normalized
        self._update_primary_alias()

    def set_primary_provider(self, provider_name: str) -> bool:
        normalized = self._normalize_provider_name(provider_name)
        if normalized not in self.api_clients:
            return False
        self.primary_provider = normalized
        self._update_primary_alias()
        return True

    def _iter_candidate_clients(
        self, preferred_provider: Optional[str] = None
    ) -> Iterable[Tuple[str, DomainAPIClient]]:
        ordered_names: List[str] = []
        if preferred_provider:
            ordered_names.append(self._normalize_provider_name(preferred_provider))
        if self.primary_provider:
            ordered_names.append(self.primary_provider)
        ordered_names.extend(self.api_clients.keys())

        seen = set()
        for provider_name in ordered_names:
            if provider_name in seen:
                continue
            seen.add(provider_name)
            api_client = self.api_clients.get(provider_name)
            if api_client:
                yield provider_name, api_client

    def _get_client_for_provider(
        self, provider_name: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[DomainAPIClient]]:
        if provider_name:
            normalized = self._normalize_provider_name(provider_name)
            return normalized, self.api_clients.get(normalized)
        if self.primary_provider and self.primary_provider in self.api_clients:
            return self.primary_provider, self.api_clients[self.primary_provider]
        return None, None

    def configure(
        self,
        api_key: str = "",
        secret_key: str = "",
        monthly_budget: Optional[float] = None,
        provider: str = "porkbun",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Configure provider credentials and budget.
        Kept compatible with existing email config forms.
        """
        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        normalized_provider = self._normalize_provider_name(provider)
        if normalized_provider == "porkbun":
            if not api_key or not secret_key:
                return {
                    "success": False,
                    "message": "Porkbun configuration requires api_key and secret_key",
                }
            client = PorkbunAPIClient(api_key, secret_key)
            self.add_api_client(
                "porkbun",
                client,
                set_primary=kwargs.get("set_primary", True),
                config={"api_key": api_key, "api_secret": secret_key},
            )
            return {"success": True, "message": "Porkbun provider configured"}

        if normalized_provider == "namecheap":
            api_user = kwargs.get("api_user", "")
            username = kwargs.get("username")
            client_ip = kwargs.get("client_ip", "127.0.0.1")
            sandbox = bool(kwargs.get("sandbox", False))
            default_contacts = kwargs.get("default_contacts")
            if not api_user or not api_key:
                return {
                    "success": False,
                    "message": "Namecheap configuration requires api_user and api_key",
                }
            client = NamecheapAPIClient(
                api_user=api_user,
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                sandbox=sandbox,
                default_contacts=default_contacts,
            )
            self.add_api_client(
                "namecheap",
                client,
                set_primary=kwargs.get("set_primary", False),
                config={
                    "api_user": api_user,
                    "api_key": api_key,
                    "username": username or api_user,
                    "client_ip": client_ip,
                    "sandbox": sandbox,
                    "default_contacts": bool(default_contacts),
                },
            )
            return {"success": True, "message": "Namecheap provider configured"}

        return {"success": False, "message": f"Unknown provider: {provider}"}

    def get_config(self) -> Dict[str, Any]:
        """Return sanitized runtime configuration for UI rendering."""
        providers = {}
        for provider_name in self.api_clients:
            cfg = dict(self.provider_configs.get(provider_name, {}))
            if "api_key" in cfg:
                cfg["api_key"] = _mask_secret(str(cfg["api_key"]))
            if "api_secret" in cfg:
                cfg["api_secret"] = _mask_secret(str(cfg["api_secret"]))
            providers[provider_name] = {"configured": True, **cfg}

        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "primary_provider": self.primary_provider,
            "providers": providers,
        }

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name.
        Uses cheap TLDs like .xyz, .club, .online.
        """
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def _resolve_price(
        self,
        domain_result: Dict[str, Any],
        api_client: DomainAPIClient,
        tld: str,
    ) -> Optional[float]:
        price = _coerce_price(domain_result.get("price"))
        if price is not None:
            return price
        pricing = api_client.get_pricing(tld)
        return _coerce_price(pricing.get("registration"))

    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        preferred_provider: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain.
        Returns domain info or None.
        """
        if not self.api_clients:
            logger.error("No API client configured")
            return None

        cheap_tlds = ["xyz", "club", "online", "site", "website"]

        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            random_domain = self.generate_random_domain(tld)

            for provider_name, api_client in self._iter_candidate_clients(
                preferred_provider=preferred_provider
            ):
                result = api_client.search_domain(random_domain)
                if not result.get("available"):
                    continue

                resolved_domain = result.get("domain") or random_domain
                resolved_tld = resolved_domain.rsplit(".", 1)[-1]
                price = self._resolve_price(result, api_client, resolved_tld)
                if price is None:
                    continue
                if price <= max_price:
                    return {
                        "domain": resolved_domain,
                        "price": price,
                        "tld": resolved_tld,
                        "provider": provider_name,
                    }

        return None

    def purchase_domain_if_budget_allows(
        self, domain: str, price: float, provider: Optional[str] = None
    ) -> bool:
        """
        Purchase domain if within budget.
        Returns True on success.
        """
        provider_name, api_client = self._get_client_for_provider(provider)
        if not api_client:
            logger.error("No API client configured for provider: %s", provider)
            return False

        if self.current_spending + price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                price,
                self.monthly_budget,
            )
            return False

        result = api_client.purchase_domain(domain, years=1)
        if result.get("success"):
            self.current_spending += price
            now = datetime.now()
            self.owned_domains.append(
                {
                    "domain": domain,
                    "price": price,
                    "provider": provider_name,
                    "purchased_at": now,
                    "expires_at": now + timedelta(days=365),
                }
            )
            if not self.active_domain:
                self.active_domain = domain
            logger.info(
                "Successfully purchased domain %s via %s for $%s",
                domain,
                provider_name,
                price,
            )
            return True

        logger.error("Failed to purchase domain via %s: %s", provider_name, result)
        return False

    def rotate_to_new_domain(
        self,
        max_price: float = 5.0,
        preferred_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Rotate to a new domain with structured response.
        """
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            preferred_provider=preferred_provider,
        )
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain",
            }

        success = self.purchase_domain_if_budget_allows(
            domain=domain_info["domain"],
            price=domain_info["price"],
            provider=domain_info.get("provider"),
        )
        if not success:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded",
                "provider": domain_info.get("provider"),
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "price": domain_info["price"],
            "provider": domain_info.get("provider"),
        }

    def rotate_domain(self, preferred_provider: Optional[str] = None) -> Optional[str]:
        """
        Backward-compatible rotate API that returns domain string or None.
        """
        result = self.rotate_to_new_domain(preferred_provider=preferred_provider)
        if result.get("success"):
            return result.get("domain")
        logger.error("Could not rotate domain: %s", result.get("error", "unknown error"))
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
            "providers_configured": len(self.api_clients),
            "primary_provider": self.primary_provider,
        }

    def export_state(self) -> Dict[str, Any]:
        """Export JSON-serializable state snapshot."""
        owned_domains = []
        for domain in self.owned_domains:
            exported = dict(domain)
            for field in ("purchased_at", "expires_at"):
                value = exported.get(field)
                if isinstance(value, datetime):
                    exported[field] = value.isoformat()
            owned_domains.append(exported)

        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": owned_domains,
            "active_domain": self.active_domain,
            "primary_provider": self.primary_provider,
        }

    def import_state(self, state: Dict[str, Any]):
        """Import persisted state snapshot."""
        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))
        self.current_spending = float(state.get("current_spending", 0.0))
        self.active_domain = state.get("active_domain")
        self.primary_provider = state.get("primary_provider") or self.primary_provider

        imported_domains = []
        for domain in state.get("owned_domains", []):
            parsed = dict(domain)
            for field in ("purchased_at", "expires_at"):
                value = parsed.get(field)
                if isinstance(value, str):
                    try:
                        parsed[field] = datetime.fromisoformat(value)
                    except ValueError:
                        parsed[field] = value
            imported_domains.append(parsed)
        self.owned_domains = imported_domains
        self._update_primary_alias()


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
