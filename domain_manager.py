"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import re
from xml.etree import ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    
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

    def provider_name(self) -> str:
        """Provider identifier used for metadata and logging."""
        return "generic"


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

    def provider_name(self) -> str:
        return "porkbun"


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap API client for domain management.
    Docs: https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"
    CONTACT_TYPES = ("Registrant", "Tech", "Admin", "AuxBilling")
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
        api_key: str,
        api_user: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        contact_details: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.contact_details = contact_details or {}
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        query = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "Command": command,
            "ClientIp": self.client_ip,
        }
        if params:
            query.update(params)

        try:
            response = self.session.get(self.base_url, params=query, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception as exc:
            logger.error(f"Namecheap API request failed: {exc}")
            return {"success": False, "errors": [str(exc)]}

        errors = [el.text or "Unknown error" for el in root.findall(".//{*}Error")]
        if errors:
            return {"success": False, "errors": errors, "root": root}

        return {"success": True, "root": root}

    def search_domain(self, domain: str) -> Dict:
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not result.get("success"):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": self.provider_name(),
                "error": "; ".join(result.get("errors", [])),
            }

        node = result["root"].find(".//{*}DomainCheckResult")
        if node is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": self.provider_name(),
                "error": "DomainCheckResult missing in Namecheap response",
            }

        available = node.attrib.get("Available", "false").lower() == "true"
        premium_price = node.attrib.get("PremiumRegistrationPrice")
        regular_price = node.attrib.get("RegistrationPrice")
        price = premium_price or regular_price

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "provider": self.provider_name(),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        missing = [f for f in self.REQUIRED_CONTACT_FIELDS if not self.contact_details.get(f)]
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Missing Namecheap contact fields: "
                    + ", ".join(sorted(missing))
                ),
            }

        payload: Dict[str, Any] = {"DomainName": domain, "Years": years}
        for contact_type in self.CONTACT_TYPES:
            for field in self.REQUIRED_CONTACT_FIELDS:
                payload[f"{contact_type}Contact{field}"] = self.contact_details[field]

        result = self._make_request("namecheap.domains.create", payload)
        if not result.get("success"):
            return {
                "success": False,
                "domain": domain,
                "message": "; ".join(result.get("errors", [])),
            }

        create_node = result["root"].find(".//{*}DomainCreateResult")
        order_id = None
        if create_node is not None:
            order_id = create_node.attrib.get("OrderID")

        return {
            "success": True,
            "domain": domain,
            "message": "Purchased successfully",
            "order_id": order_id,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        # Namecheap pricing responses are deeply nested and may vary by account.
        # We expose consistent keys and only fill what we can parse safely.
        result = self._make_request(
            "namecheap.users.getPricing",
            {"ProductType": "DOMAIN", "ProductName": tld},
        )
        if not result.get("success"):
            return {}

        registration = None
        renewal = None
        transfer = None
        for price_node in result["root"].findall(".//{*}Price"):
            category = (price_node.attrib.get("Category", "") or "").upper()
            your_price = price_node.attrib.get("YourPrice")
            if category == "REGISTER" and registration is None:
                registration = your_price
            elif category == "RENEW" and renewal is None:
                renewal = your_price
            elif category == "TRANSFER" and transfer is None:
                transfer = your_price

        return {
            "tld": tld,
            "registration": registration,
            "renewal": renewal,
            "transfer": transfer,
            "currency": "USD",
        }

    def provider_name(self) -> str:
        return "namecheap"


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.primary_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        if api_client:
            self.add_api_client(self._provider_name_for_client(api_client), api_client, make_primary=True)

    @staticmethod
    def _provider_name_for_client(api_client: DomainAPIClient) -> str:
        provider = "primary"
        try:
            provider_candidate = api_client.provider_name()
            if isinstance(provider_candidate, str) and provider_candidate.strip():
                provider = provider_candidate
        except Exception:
            provider = "primary"
        return provider
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.add_api_client(self._provider_name_for_client(api_client), api_client, make_primary=True)

    def add_api_client(self, provider: str, api_client: DomainAPIClient,
                       make_primary: bool = False):
        """Register an API client under a provider name."""
        key = provider.strip().lower() if isinstance(provider, str) and provider.strip() else "primary"
        self.api_clients[key] = api_client
        if make_primary or not self.primary_provider:
            self.primary_provider = key
            self.api_client = api_client

    def set_primary_api_client(self, provider: str) -> bool:
        """Set which registered provider should be tried first."""
        key = provider.strip().lower()
        if key not in self.api_clients:
            return False
        self.primary_provider = key
        self.api_client = self.api_clients[key]
        return True

    @staticmethod
    def _parse_price(price: Any) -> Optional[float]:
        """Parse price values from APIs like '$2.99', '2.99 USD', or numeric types."""
        if isinstance(price, (int, float)):
            return float(price)
        if not isinstance(price, str):
            return None
        cleaned = re.sub(r"[^0-9.]", "", price)
        if cleaned.count(".") > 1 or not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _iter_api_clients(self) -> Iterable[Tuple[str, DomainAPIClient]]:
        if self.primary_provider and self.primary_provider in self.api_clients:
            yield self.primary_provider, self.api_clients[self.primary_provider]
        elif self.api_client:
            # Backward compatibility for manager configured with only api_client.
            yield "primary", self.api_client

        for provider, client in self.api_clients.items():
            if provider != self.primary_provider:
                yield provider, client

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        provider: str = "porkbun",
        **kwargs: Any,
    ) -> Dict:
        """Configure credentials and budget for a supported provider."""
        provider_key = provider.strip().lower()
        if monthly_budget is not None:
            if monthly_budget <= 0:
                raise ValueError("monthly_budget must be positive")
            self.monthly_budget = float(monthly_budget)

        if provider_key == "porkbun":
            secret = kwargs.get("api_secret") or secret_key
            if not api_key or not secret:
                raise ValueError("Porkbun requires api_key and secret_key")
            client = PorkbunAPIClient(api_key, secret)
            self.add_api_client("porkbun", client, make_primary=True)
        elif provider_key == "namecheap":
            api_user = kwargs.get("api_user")
            if not api_user:
                raise ValueError("Namecheap requires api_user")
            client = NamecheapAPIClient(
                api_key=api_key,
                api_user=api_user,
                username=kwargs.get("username"),
                client_ip=kwargs.get("client_ip", "127.0.0.1"),
                sandbox=bool(kwargs.get("sandbox", False)),
                contact_details=kwargs.get("contact_details"),
            )
            self.add_api_client("namecheap", client, make_primary=True)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        return self.get_config()

    def get_config(self) -> Dict:
        """Expose safe, non-secret domain manager configuration."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "primary_provider": self.primary_provider,
            "providers": sorted(self.api_clients.keys()),
            "configured": bool(self.api_clients or self.api_client),
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
                                   max_attempts: int = 10) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_client and not self.api_clients:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            for provider, client in self._iter_api_clients():
                result = client.search_domain(domain)
                if not result.get("available"):
                    continue

                price = self._parse_price(result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
                    price = self._parse_price(pricing.get("registration"))
                if price is None:
                    logger.warning(
                        f"Provider '{provider}' returned available domain without parsable price: {domain}"
                    )
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
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client and not self.api_clients:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase with provider-aware selection
        if provider:
            selected_client = self.api_clients.get(provider, self.api_client)
            selected_provider = provider
        else:
            selected_provider = self.primary_provider or "primary"
            selected_client = self.api_client
            if self.primary_provider and self.primary_provider in self.api_clients:
                selected_client = self.api_clients[self.primary_provider]

        if selected_client is None:
            logger.error(f"No API client available for provider '{selected_provider}'")
            return False

        result = selected_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": selected_provider,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
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
