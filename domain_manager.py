"""
Domain management and registrar API integration.
Supports automated domain purchasing and rotation for burner email domains.
"""

import logging
import random
import string
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """Base class for domain registrar API clients."""

    registrar_name = "generic"

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search if a domain is available."""
        raise NotImplementedError()

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase a domain."""
        raise NotImplementedError()

    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing information for a TLD."""
        raise NotImplementedError()

    def list_domains(self) -> List[str]:
        """List domains owned in this registrar account."""
        return []


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management.
    https://porkbun.com/api/json/v3/documentation
    """

    registrar_name = "porkbun"
    BASE_URL = "https://porkbun.com/api/json/v3"

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()

    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a Porkbun API request."""
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

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check whether a domain is available."""
        result = self._make_request("domain/check", {"domain": domain})
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and bool(result.get("isAvailable")),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase a domain.
        NOTE: This action attempts a real registrar purchase.
        """
        result = self._make_request("domain/create", {"domain": domain, "years": years})
        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId"),
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get pricing for a TLD."""
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
            return [item.get("domain") for item in domains if item.get("domain")]
        return []


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap API client for domain management.
    https://www.namecheap.com/support/api/
    """

    registrar_name = "namecheap"
    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        default_contact: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key, None)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.default_contact = default_contact or {}
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.session = requests.Session()

    @staticmethod
    def _local_name(tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def _find_elements(cls, root: ET.Element, local_name: str) -> List[ET.Element]:
        return [node for node in root.iter() if cls._local_name(node.tag) == local_name]

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> Optional[ET.Element]:
        """Make a Namecheap API request and return XML root."""
        payload = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if data:
            payload.update(data)

        try:
            response = self.session.get(self.base_url, params=payload, timeout=30)
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return None

    def _is_success(self, root: Optional[ET.Element]) -> bool:
        return bool(root is not None and root.attrib.get("Status") == "OK")

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check whether a domain is available."""
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not self._is_success(root):
            return {"domain": domain, "available": False, "price": None, "currency": "USD"}

        check_results = self._find_elements(root, "DomainCheckResult")
        match = None
        for result in check_results:
            if result.attrib.get("Domain", "").lower() == domain.lower():
                match = result
                break
        if match is None and check_results:
            match = check_results[0]

        available = bool(match and match.attrib.get("Available", "").lower() == "true")
        price = None
        if available and "." in domain:
            pricing = self.get_pricing(domain.rsplit(".", 1)[-1])
            price = pricing.get("registration")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase a domain with Namecheap.
        Namecheap requires contact profile fields for purchases.
        """
        if not self.default_contact:
            return {
                "success": False,
                "domain": domain,
                "message": "Missing Namecheap contact profile",
                "order_id": None,
            }

        if "." not in domain:
            return {"success": False, "domain": domain, "message": "Invalid domain name", "order_id": None}

        contact_defaults = {
            "first_name": "Domain",
            "last_name": "Admin",
            "address1": "123 Privacy Street",
            "city": "Wilmington",
            "state_province": "DE",
            "postal_code": "19801",
            "country": "US",
            "phone": "+1.5555555555",
            "email_address": "admin@example.com",
            "organization": "Private Registration",
        }
        contact = {**contact_defaults, **self.default_contact}

        sld, tld = domain.rsplit(".", 1)
        payload: Dict[str, Any] = {
            "DomainName": domain,
            "SLD": sld,
            "TLD": tld,
            "Years": years,
        }

        for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
            payload[f"{role}FirstName"] = contact["first_name"]
            payload[f"{role}LastName"] = contact["last_name"]
            payload[f"{role}Address1"] = contact["address1"]
            payload[f"{role}City"] = contact["city"]
            payload[f"{role}StateProvince"] = contact["state_province"]
            payload[f"{role}PostalCode"] = contact["postal_code"]
            payload[f"{role}Country"] = contact["country"]
            payload[f"{role}Phone"] = contact["phone"]
            payload[f"{role}EmailAddress"] = contact["email_address"]
            payload[f"{role}OrganizationName"] = contact["organization"]

        root = self._make_request("namecheap.domains.create", payload)
        if not self._is_success(root):
            errors = []
            if root is not None:
                for error in self._find_elements(root, "Error"):
                    if error.text:
                        errors.append(error.text.strip())
            message = "; ".join(errors) if errors else "Namecheap purchase failed"
            return {"success": False, "domain": domain, "message": message, "order_id": None}

        create_results = self._find_elements(root, "DomainCreateResult")
        order_id = create_results[0].attrib.get("OrderID") if create_results else None
        return {"success": True, "domain": domain, "message": "SUCCESS", "order_id": order_id}

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get registration pricing for a TLD."""
        root = self._make_request(
            "namecheap.users.getPricing",
            {"ProductType": "DOMAIN", "ActionName": "REGISTER", "ProductName": tld.upper()},
        )
        if not self._is_success(root):
            return {}

        for price_node in self._find_elements(root, "Price"):
            duration = price_node.attrib.get("Duration")
            if duration in (None, "1"):
                return {
                    "tld": tld,
                    "registration": price_node.attrib.get("YourPrice")
                    or price_node.attrib.get("Price")
                    or price_node.attrib.get("RegularPrice"),
                    "renewal": None,
                    "transfer": None,
                    "currency": price_node.attrib.get("Currency", "USD"),
                }
        return {}

    def list_domains(self) -> List[str]:
        """List owned domains."""
        root = self._make_request("namecheap.domains.getList")
        if not self._is_success(root):
            return []
        return [node.attrib["Name"] for node in self._find_elements(root, "Domain") if node.attrib.get("Name")]


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Supports one active registrar plus additional configured registrar clients.
    """

    def __init__(self, api_client: Optional[DomainAPIClient] = None, monthly_budget: float = 50.0):
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_registrar: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict[str, Any]] = []
        self.active_domain: Optional[str] = None

        if api_client is not None:
            self.set_api_client(api_client)

    @staticmethod
    def _parse_price(value: Any) -> Optional[float]:
        """Parse a registrar price field to float."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = (
                value.replace("$", "")
                .replace("€", "")
                .replace("USD", "")
                .replace("usd", "")
                .strip()
            )
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def add_api_client(self, registrar: str, api_client: DomainAPIClient, set_active: bool = False) -> None:
        """Register an API client under the given registrar name."""
        registrar_key = registrar.lower().strip()
        self.api_clients[registrar_key] = api_client
        if set_active or self.active_registrar is None:
            self.active_registrar = registrar_key

    def set_api_client(self, api_client: DomainAPIClient) -> None:
        """Set a single API client and mark it active."""
        registrar = getattr(api_client, "registrar_name", None)
        if not isinstance(registrar, str) or not registrar:
            registrar = getattr(type(api_client), "registrar_name", "generic")
        if not isinstance(registrar, str) or not registrar:
            registrar = "generic"
        self.add_api_client(registrar, api_client, set_active=True)

    def set_active_registrar(self, registrar: str) -> bool:
        """Switch the active registrar if configured."""
        registrar_key = registrar.lower().strip()
        if registrar_key in self.api_clients:
            self.active_registrar = registrar_key
            return True
        return False

    def get_api_client(self, registrar: Optional[str] = None) -> Optional[DomainAPIClient]:
        """Get a configured API client by registrar or active registrar."""
        registrar_key = (registrar or self.active_registrar or "").lower().strip()
        if not registrar_key:
            return None
        return self.api_clients.get(registrar_key)

    def get_available_registrars(self) -> List[str]:
        """Get list of configured registrars."""
        return sorted(self.api_clients.keys())

    def configure(
        self,
        api_key: str = "",
        secret_key: str = "",
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Configure registrar credentials and set budget.

        For Porkbun:
            api_key=<porkbun_api_key>, secret_key=<porkbun_secret_key>

        For Namecheap:
            registrar="namecheap", api_key=<api_user>, secret_key=<api_key>,
            client_ip=<whitelisted_ip>, username=<api_username>, sandbox=<bool>,
            contact_profile=<dict>
        """
        if monthly_budget <= 0:
            raise ValueError("monthly_budget must be greater than zero")

        registrar_key = (registrar or "porkbun").lower().strip()
        self.monthly_budget = monthly_budget

        if registrar_key == "porkbun":
            if not api_key or not secret_key:
                raise ValueError("Porkbun requires api_key and secret_key")
            client = PorkbunAPIClient(api_key, secret_key)
            self.add_api_client("porkbun", client, set_active=True)
        elif registrar_key == "namecheap":
            if not api_key or not secret_key:
                raise ValueError("Namecheap requires api_user and api_key")
            client = NamecheapAPIClient(
                api_user=api_key,
                api_key=secret_key,
                username=kwargs.get("username"),
                client_ip=kwargs.get("client_ip", "127.0.0.1"),
                sandbox=bool(kwargs.get("sandbox", False)),
                default_contact=kwargs.get("contact_profile"),
            )
            self.add_api_client("namecheap", client, set_active=True)
        else:
            raise ValueError(f"Unsupported registrar: {registrar_key}")

        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return safe runtime configuration details (no secrets)."""
        return {
            "configured": bool(self.api_clients),
            "active_registrar": self.active_registrar,
            "available_registrars": self.get_available_registrars(),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "domains_owned": len(self.owned_domains),
            "active_domain": self.active_domain,
        }

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """Generate random domain name with alphanumeric hostname."""
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        registrar: Optional[str] = None,
        tlds: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find an available domain below max_price using the selected registrar.
        Returns domain info or None.
        """
        api_client = self.get_api_client(registrar)
        if not api_client:
            logger.error("No API client configured")
            return None

        registrar_name = (registrar or self.active_registrar or "unknown").lower()
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]

        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            result = api_client.search_domain(domain)

            if not result.get("available"):
                continue

            price = self._parse_price(result.get("price"))
            if price is None:
                pricing = api_client.get_pricing(tld)
                price = self._parse_price(pricing.get("registration"))
            if price is None:
                continue
            if price <= max_price:
                return {"domain": domain, "price": price, "tld": tld, "registrar": registrar_name}

        return None

    def purchase_domain_if_budget_allows(
        self, domain: str, price: float, registrar: Optional[str] = None
    ) -> bool:
        """Purchase domain if within budget. Returns True on success."""
        api_client = self.get_api_client(registrar)
        if not api_client:
            logger.error("No API client configured")
            return False

        registrar_name = (registrar or self.active_registrar or "unknown").lower()
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
            now = datetime.now()
            self.current_spending += price
            self.owned_domains.append(
                {
                    "domain": domain,
                    "price": price,
                    "registrar": registrar_name,
                    "purchased_at": now,
                    "expires_at": now + timedelta(days=365),
                }
            )

            if not self.active_domain:
                self.active_domain = domain

            logger.info("Successfully purchased domain: %s for $%s via %s", domain, price, registrar_name)
            return True

        logger.error("Failed to purchase domain: %s", result.get("message"))
        return False

    def rotate_domain(
        self, max_price: float = 5.0, max_attempts: int = 10, registrar: Optional[str] = None
    ) -> Optional[str]:
        """Rotate to a new domain by finding and purchasing one within budget."""
        domain_info = self.find_cheap_available_domain(
            max_price=max_price, max_attempts=max_attempts, registrar=registrar
        )
        if not domain_info:
            logger.error("Could not find an available cheap domain")
            return None

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], domain_info["price"], registrar=domain_info.get("registrar")
        )
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

    def get_budget_status(self) -> Dict[str, Any]:
        """Get budget and registrar status."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "active_registrar": self.active_registrar,
            "available_registrars": self.get_available_registrars(),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
