"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import os
import requests
import random
import string
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """

    provider_name = "generic"

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

    provider_name = "porkbun"
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
            "currency": result.get("currency", "USD"),
            "provider": self.provider_name
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
            "order_id": result.get("orderId"),
            "provider": self.provider_name
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
                "currency": "USD",
                "provider": self.provider_name
            }

        return {}

    def list_domains(self) -> List[str]:
        """List owned domains"""
        result = self._make_request("domain/listAll")

        if result.get("status") == "SUCCESS":
            domains = result.get("domains", [])
            return [d.get("domain") for d in domains if d.get("domain")]

        return []


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap XML API client for domain management
    https://www.namecheap.com/support/api/intro/
    """

    provider_name = "namecheap"
    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"
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
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key=api_key, api_secret=None)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip or os.getenv("NAMECHEAP_CLIENT_IP", "127.0.0.1")
        self.sandbox = sandbox
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    @staticmethod
    def _split_domain(domain: str) -> Optional[Dict[str, str]]:
        parts = domain.strip().lower().split(".")
        if len(parts) < 2:
            return None
        return {
            "sld": ".".join(parts[:-1]),
            "tld": parts[-1],
        }

    def _make_request(self, command: str, params: Optional[Dict[str, str]] = None) -> Dict:
        payload = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            payload.update(params)

        try:
            response = self.session.get(self.base_url, params=payload, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception as exc:
            logger.error(f"Namecheap API request failed: {exc}")
            return {"success": False, "message": str(exc)}

        status = root.attrib.get("Status", "ERROR")
        errors = [err.text for err in root.findall(".//{*}Errors/{*}Error") if err.text]
        return {
            "success": status.upper() == "OK",
            "root": root,
            "errors": errors,
            "message": "; ".join(errors) if errors else "",
        }

    def search_domain(self, domain: str) -> Dict:
        result = self._make_request(
            "namecheap.domains.check",
            {"DomainList": domain},
        )
        if not result.get("success"):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": self.provider_name,
                "message": result.get("message", "Request failed"),
            }

        root = result["root"]
        check_result = root.find(".//{*}DomainCheckResult")
        if check_result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": self.provider_name,
                "message": "Malformed Namecheap response",
            }

        available = check_result.attrib.get("Available", "false").lower() == "true"
        premium = check_result.attrib.get("IsPremiumName", "false").lower() == "true"
        price = check_result.attrib.get("PremiumRegistrationPrice")
        if not price:
            split_domain = self._split_domain(domain)
            if split_domain:
                pricing = self.get_pricing(split_domain["tld"])
                price = pricing.get("registration")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "provider": self.provider_name,
            "premium": premium,
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        split_domain = self._split_domain(domain)
        if not split_domain:
            return {
                "success": False,
                "domain": domain,
                "message": "Invalid domain format",
                "provider": self.provider_name,
            }

        missing_fields = [
            field for field in self.REQUIRED_CONTACT_FIELDS if not self.contact_profile.get(field)
        ]
        if missing_fields:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Namecheap purchase requires contact profile fields: "
                    + ", ".join(missing_fields)
                ),
                "provider": self.provider_name,
            }

        params = {
            "DomainName": domain,
            "Years": str(years),
        }
        for prefix in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field, value in self.contact_profile.items():
                params[f"{prefix}{field}"] = value

        result = self._make_request("namecheap.domains.create", params)
        if not result.get("success"):
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Request failed"),
                "provider": self.provider_name,
            }

        root = result["root"]
        create_result = root.find(".//{*}DomainCreateResult")
        return {
            "success": create_result is not None,
            "domain": domain,
            "order_id": create_result.attrib.get("OrderID") if create_result is not None else None,
            "message": result.get("message", ""),
            "provider": self.provider_name,
        }

    def get_pricing(self, tld: str) -> Dict:
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductName": tld.upper(),
            },
        )
        if not result.get("success"):
            return {}

        root = result["root"]
        price_nodes = root.findall(".//{*}Price")
        registration = None
        for node in price_nodes:
            if node.attrib.get("Duration") == "1":
                registration = node.attrib.get("YourPrice")
                if registration:
                    break
        if not registration and price_nodes:
            registration = price_nodes[0].attrib.get("YourPrice")

        if not registration:
            return {}

        return {
            "tld": tld,
            "registration": registration,
            "currency": "USD",
            "provider": self.provider_name,
        }

    def list_domains(self) -> List[str]:
        result = self._make_request(
            "namecheap.domains.getList",
            {"PageSize": "100", "SortBy": "NAME"},
        )
        if not result.get("success"):
            return []

        root = result["root"]
        domain_nodes = root.findall(".//{*}Domain")
        return [node.attrib.get("Name") for node in domain_nodes if node.attrib.get("Name")]


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0):
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.active_provider: Optional[str] = None
        if api_client:
            self.set_api_client(api_client)

    @staticmethod
    def _normalize_provider_name(provider_name: Optional[str]) -> str:
        if not isinstance(provider_name, str) or not provider_name.strip():
            return "default"
        return provider_name.strip().lower()

    @staticmethod
    def _parse_price(price: Optional[object]) -> Optional[float]:
        if price is None:
            return None
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            cleaned = (
                price.strip()
                .replace("$", "")
                .replace("€", "")
                .replace(",", "")
            )
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _get_api_client(self, provider: Optional[str] = None) -> Optional[DomainAPIClient]:
        if not self.api_clients:
            return None
        if provider:
            return self.api_clients.get(self._normalize_provider_name(provider))
        if self.active_provider and self.active_provider in self.api_clients:
            return self.api_clients[self.active_provider]
        first_provider = next(iter(self.api_clients))
        return self.api_clients[first_provider]

    def get_available_providers(self) -> List[str]:
        """Get all configured provider names"""
        return list(self.api_clients.keys())

    def set_api_client(self, api_client: DomainAPIClient):
        """
        Set the primary domain API client.
        Backward-compatible behavior: replaces existing providers.
        """
        self.api_clients = {}
        provider_name = self._normalize_provider_name(
            getattr(api_client, "provider_name", "default")
        )
        self.api_clients[provider_name] = api_client
        self.active_provider = provider_name

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient):
        """Add an additional registrar API client."""
        normalized = self._normalize_provider_name(provider_name)
        self.api_clients[normalized] = api_client
        if not self.active_provider:
            self.active_provider = normalized

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: float = 50.0,
        provider: str = "porkbun",
        **kwargs,
    ) -> Dict:
        """
        Configure a registrar client.
        Added primarily for route-level compatibility.
        """
        provider_name = self._normalize_provider_name(provider)
        self.monthly_budget = monthly_budget

        if provider_name == "porkbun":
            if not secret_key:
                raise ValueError("Porkbun configuration requires secret_key")
            client = PorkbunAPIClient(api_key, secret_key)
        elif provider_name == "namecheap":
            client = NamecheapAPIClient(
                api_user=kwargs.get("api_user", ""),
                api_key=api_key,
                username=kwargs.get("username"),
                client_ip=kwargs.get("client_ip"),
                sandbox=bool(kwargs.get("sandbox", False)),
                contact_profile=kwargs.get("contact_profile"),
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        replace_existing = bool(kwargs.get("replace_existing", False))
        if replace_existing:
            self.api_clients = {}
        self.add_api_client(provider_name, client)
        self.active_provider = provider_name

        return {"success": True, "provider": provider_name}

    def get_config(self) -> Dict:
        """Get current manager configuration metadata."""
        return {
            "providers": self.get_available_providers(),
            "active_provider": self.active_provider,
            "active_domain": self.active_domain,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
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
                                   provider: Optional[str] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_clients:
            logger.error("No API client configured")
            return None

        provider_names = (
            [self._normalize_provider_name(provider)]
            if provider
            else self.get_available_providers()
        )
        provider_names = [name for name in provider_names if name in self.api_clients]
        if not provider_names:
            logger.error("No matching API provider configured")
            return None

        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]

        for attempt in range(max_attempts):
            provider_name = provider_names[attempt % len(provider_names)]
            api_client = self.api_clients[provider_name]
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            result = api_client.search_domain(domain)

            if result.get("available"):
                price = self._parse_price(result.get("price"))
                if price is None:
                    pricing = api_client.get_pricing(tld)
                    price = self._parse_price(pricing.get("registration"))
                if price is None:
                    price = 999.0

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider_name,
                        "currency": result.get("currency", "USD"),
                    }

        return None

    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider: Optional[str] = None,
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        api_client = self._get_api_client(provider)
        if not api_client:
            logger.error("No API client configured")
            return False

        provider_name = self._normalize_provider_name(
            provider or getattr(api_client, "provider_name", self.active_provider or "default")
        )

        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False

        # Attempt purchase
        result = api_client.purchase_domain(domain, years=1)

        if result.get("success"):
            now = datetime.now()
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": provider_name,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365)
            })

            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            self.active_provider = provider_name

            logger.info(
                f"Successfully purchased domain: {domain} for ${price} via {provider_name}"
            )
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False

    def rotate_domain(self, provider: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(provider=provider)

        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None

        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"],
            provider=domain_info.get("provider"),
        )

        if success:
            self.active_domain = domain_info["domain"]
            self.active_provider = domain_info.get("provider", self.active_provider)
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
            "domains_owned": len(self.owned_domains),
            "active_provider": self.active_provider,
            "providers_configured": len(self.api_clients),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
