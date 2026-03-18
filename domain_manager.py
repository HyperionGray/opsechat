"""
Domain management and API integration.
Supports automated domain purchasing for burner email rotation.
"""
from __future__ import annotations

import logging
import random
import re
import string
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """Base class for domain registrar API clients."""

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

    BASE_URL = "https://porkbun.com/api/json/v3"

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()

    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check if domain is available."""
        result = self._make_request("domain/check", {"domain": domain})
        available = result.get("isAvailable", False)
        if isinstance(available, str):
            available = available.lower() == "true"

        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and bool(available),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase domain.
        Note: This actually purchases the domain and charges your account.
        """
        result = self._make_request(
            "domain/create",
            {
                "domain": domain,
                "years": years,
            },
        )

        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId"),
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
            }

        return {}

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("domain/listAll")

        if result.get("status") == "SUCCESS":
            domains = result.get("domains", [])
            return [domain.get("domain") for domain in domains if domain.get("domain")]

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
        api_user: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
    ):
        super().__init__(api_key)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            payload.update(params)

        try:
            response = self.session.get(self.BASE_URL, params=payload, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            return {"success": True, "root": root}
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def _split_domain(self, domain: str) -> Optional[Dict[str, str]]:
        parts = domain.split(".")
        if len(parts) < 2:
            return None
        return {"sld": parts[0], "tld": ".".join(parts[1:])}

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
        node = root.find(".//DomainCheckResult") or root.find(".//{*}DomainCheckResult")
        available = False
        if node is not None:
            available = node.attrib.get("Available", "false").lower() == "true"

        return {
            "domain": domain,
            "available": available,
            "price": None,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase domain.
        Note: This actually purchases the domain and charges your account.
        """
        domain_parts = self._split_domain(domain)
        if not domain_parts:
            return {
                "success": False,
                "domain": domain,
                "message": "Invalid domain format",
                "order_id": None,
            }

        result = self._make_request(
            "namecheap.domains.create",
            {
                "DomainName": domain,
                "Years": max(1, int(years)),
            },
        )
        if not result.get("success"):
            return {
                "success": False,
                "domain": domain,
                "message": result.get("error", "Unknown Namecheap API error"),
                "order_id": None,
            }

        root = result["root"]
        success = root.attrib.get("Status", "").upper() == "OK"
        order_id_node = root.find(".//OrderID") or root.find(".//{*}OrderID")
        order_id = order_id_node.text if order_id_node is not None else None

        return {
            "success": success,
            "domain": domain,
            "message": "" if success else "Domain purchase was not accepted by Namecheap API",
            "order_id": order_id,
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get pricing for TLD registration."""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ProductName": tld,
                "ActionName": "register",
            },
        )
        if not result.get("success"):
            return {}

        root = result["root"]
        price_node = root.find(".//ProductPrice") or root.find(".//{*}ProductPrice")
        if price_node is None:
            return {}

        return {
            "tld": tld,
            "registration": price_node.attrib.get("YourPrice"),
            "renewal": price_node.attrib.get("YourPrice"),
            "transfer": price_node.attrib.get("YourPrice"),
            "currency": "USD",
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Automatically purchase cheap domains and rotate them.
    """

    def __init__(self, api_client: Optional[DomainAPIClient] = None, monthly_budget: float = 50.0):
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict[str, Any]] = []
        self.active_domain: Optional[str] = None
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        # Backward compatibility: some call sites still access manager.api_client directly.
        self.api_client: Optional[DomainAPIClient] = None

        if api_client:
            provider = self._provider_name_for_client(api_client)
            self.add_api_client(provider, api_client, set_active=True)

    def _provider_name_for_client(self, api_client: DomainAPIClient) -> str:
        if isinstance(api_client, PorkbunAPIClient):
            return "porkbun"
        if isinstance(api_client, NamecheapAPIClient):
            return "namecheap"
        return "default"

    def _get_active_client(self) -> Optional[DomainAPIClient]:
        if self.active_provider:
            return self.api_clients.get(self.active_provider)
        return self.api_client

    @staticmethod
    def _coerce_price(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"(\d+(?:\.\d+)?)", value.replace(",", ""))
            if match:
                return float(match.group(1))
        return None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.utcnow()

    def add_api_client(self, provider: str, api_client: DomainAPIClient, set_active: bool = False) -> str:
        """Register an API client under a provider name."""
        provider_name = provider.strip().lower()
        self.api_clients[provider_name] = api_client
        if set_active or not self.active_provider:
            self.set_active_provider(provider_name)
        return provider_name

    def set_active_provider(self, provider: str) -> bool:
        """Set active provider by name."""
        provider_name = provider.strip().lower()
        if provider_name not in self.api_clients:
            return False
        self.active_provider = provider_name
        self.api_client = self.api_clients[provider_name]
        return True

    def get_active_provider(self) -> Optional[str]:
        """Get active provider name."""
        return self.active_provider

    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client (legacy compatibility)."""
        self.add_api_client("default", api_client, set_active=True)

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        provider: str = "porkbun",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Configure provider credentials and active budget.
        Used by web routes and CLI.
        """
        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        provider_name = provider.strip().lower()
        if provider_name == "porkbun":
            if not secret_key:
                raise ValueError("Porkbun configuration requires secret_key")
            client: DomainAPIClient = PorkbunAPIClient(api_key, secret_key)
        elif provider_name == "namecheap":
            api_user = kwargs.get("api_user")
            username = kwargs.get("username")
            client_ip = kwargs.get("client_ip", "127.0.0.1")
            if not api_user:
                raise ValueError("Namecheap configuration requires api_user")
            client = NamecheapAPIClient(
                api_key=api_key,
                api_user=api_user,
                username=username,
                client_ip=client_ip,
            )
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

        self.add_api_client(provider_name, client, set_active=True)
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return current domain-rotation configuration summary."""
        return {
            "provider": self.active_provider,
            "configured": self._get_active_client() is not None,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name.
        Uses cheap TLDs like .xyz, .club, .online.
        """
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def find_cheap_available_domain(self, max_price: float = 5.0, max_attempts: int = 10) -> Optional[Dict[str, Any]]:
        """
        Find a cheap available domain.
        Returns domain info or None.
        """
        client = self._get_active_client()
        if not client:
            logger.error("No API client configured")
            return None

        cheap_tlds = ["xyz", "club", "online", "site", "website"]

        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            result = client.search_domain(domain)

            if not result.get("available"):
                continue

            price = self._coerce_price(result.get("price"))
            if price is None:
                # Some registrars don't return price in availability calls.
                # Assume zero for selection, actual charges are still bounded by budget check.
                price = 0.0

            if price <= max_price:
                return {
                    "domain": domain,
                    "price": price,
                    "tld": tld,
                    "provider": self.active_provider,
                }

        return None

    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget.
        Returns True on success.
        """
        client = self._get_active_client()
        if not client:
            logger.error("No API client configured")
            return False

        if self.current_spending + price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                price,
                self.monthly_budget,
            )
            return False

        result = client.purchase_domain(domain, years=1)
        if not result.get("success"):
            logger.error("Failed to purchase domain: %s", result.get("message"))
            return False

        now = datetime.utcnow()
        self.current_spending += price
        self.owned_domains.append(
            {
                "domain": domain,
                "price": price,
                "provider": self.active_provider,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365),
            }
        )

        if not self.active_domain:
            self.active_domain = domain

        logger.info("Successfully purchased domain: %s for $%s", domain, price)
        return True

    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain.
        Finds and purchases a new cheap domain.
        """
        domain_info = self.find_cheap_available_domain()
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None

        success = self.purchase_domain_if_budget_allows(domain_info["domain"], domain_info["price"])
        if success:
            self.active_domain = domain_info["domain"]
            return self.active_domain
        return None

    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain."""
        return self.active_domain

    def get_owned_domains(self) -> List[Dict[str, Any]]:
        """Get list of owned domains."""
        return self.owned_domains

    def load_owned_domains(self, domains: List[Dict[str, Any]]) -> None:
        """Load owned domains from serialized state."""
        loaded_domains: List[Dict[str, Any]] = []
        for domain_data in domains or []:
            loaded_domains.append(
                {
                    **domain_data,
                    "purchased_at": self._parse_datetime(domain_data.get("purchased_at")),
                    "expires_at": self._parse_datetime(domain_data.get("expires_at")),
                }
            )
        self.owned_domains = loaded_domains

    def get_owned_domains_serializable(self) -> List[Dict[str, Any]]:
        """Get owned domains with datetimes converted to ISO-8601 strings."""
        serialized: List[Dict[str, Any]] = []
        for domain_data in self.owned_domains:
            item = dict(domain_data)
            for key in ("purchased_at", "expires_at"):
                if isinstance(item.get(key), datetime):
                    item[key] = item[key].isoformat()
            serialized.append(item)
        return serialized

    def get_budget_status(self) -> Dict[str, Any]:
        """Get budget information."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "provider": self.active_provider,
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
