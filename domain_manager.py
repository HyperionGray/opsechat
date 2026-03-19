"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _parse_price(value, default: float = 999.0) -> float:
    """Best-effort price parsing from registrar payloads."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace("€", "").replace(",", "")
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                return default
    return default


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


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap XML API client for domain management.
    Docs: https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        api_user: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        use_sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key)
        self.username = username
        self.api_user = api_user or username
        self.client_ip = client_ip
        self.use_sandbox = use_sandbox
        self.base_url = self.SANDBOX_URL if use_sandbox else self.BASE_URL
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, str]] = None) -> Optional[ET.Element]:
        """Make API request and return parsed XML root."""
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
            return ET.fromstring(response.text)
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return None

    @staticmethod
    def _is_success(root: Optional[ET.Element]) -> bool:
        return root is not None and root.attrib.get("Status") == "OK"

    @staticmethod
    def _extract_errors(root: Optional[ET.Element]) -> str:
        if root is None:
            return "Unknown API error"
        errors = [e.text for e in root.findall(".//Errors/Error") if e.text]
        return "; ".join(errors) if errors else "Unknown API error"

    def _build_contact_payload(self) -> Dict[str, str]:
        """
        Build Namecheap contact payload with sensible defaults.
        Override defaults by passing contact_profile in constructor.
        """
        defaults = {
            "FirstName": "Ops",
            "LastName": "Admin",
            "Address1": "123 Privacy St",
            "City": "Wilmington",
            "StateProvince": "Delaware",
            "PostalCode": "19801",
            "Country": "US",
            "Phone": "+1.3025550100",
            "EmailAddress": "admin@example.com",
        }
        contact = {**defaults, **self.contact_profile}

        payload: Dict[str, str] = {}
        for prefix in ("Registrant", "Tech", "Admin", "AuxBilling"):
            payload.update(
                {
                    f"{prefix}FirstName": contact["FirstName"],
                    f"{prefix}LastName": contact["LastName"],
                    f"{prefix}Address1": contact["Address1"],
                    f"{prefix}City": contact["City"],
                    f"{prefix}StateProvince": contact["StateProvince"],
                    f"{prefix}PostalCode": contact["PostalCode"],
                    f"{prefix}Country": contact["Country"],
                    f"{prefix}Phone": contact["Phone"],
                    f"{prefix}EmailAddress": contact["EmailAddress"],
                }
            )
        return payload

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not self._is_success(root):
            return {
                "domain": domain,
                "available": False,
                "message": self._extract_errors(root),
            }

        result_node = root.find(".//CommandResponse/DomainCheckResult")
        if result_node is None:
            result_node = root.find(".//DomainCheckResult")

        if result_node is None:
            return {"domain": domain, "available": False, "message": "Invalid API response"}

        return {
            "domain": domain,
            "available": result_node.attrib.get("Available", "").lower() == "true",
            "price": result_node.attrib.get("PremiumRegistrationPrice")
            or result_node.attrib.get("RegistrationPrice"),
            "currency": "USD",
            "premium": result_node.attrib.get("IsPremiumName", "").lower() == "true",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase a domain through Namecheap."""
        root = self._make_request(
            "namecheap.domains.create",
            {
                "DomainName": domain,
                "Years": str(years),
                **self._build_contact_payload(),
            },
        )
        success = self._is_success(root)
        message = "Domain purchased successfully" if success else self._extract_errors(root)
        order_id = None

        if root is not None:
            result_node = root.find(".//CommandResponse/DomainCreateResult")
            if result_node is None:
                result_node = root.find(".//DomainCreateResult")
            if result_node is not None:
                order_id = result_node.attrib.get("OrderID")

        return {
            "success": success,
            "domain": domain,
            "message": message,
            "order_id": order_id,
        }

    def get_pricing(self, tld: str) -> Dict:
        """Get registration pricing for TLD if available."""
        root = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "register",
                "ProductName": f".{tld}",
            },
        )
        if not self._is_success(root):
            return {}

        # Namecheap pricing response varies by account; parse loosely.
        product = root.find(f".//Product[@Name='.{tld}']")
        if product is None:
            product = root.find(f".//Product[@Name='{tld}']")

        if product is None:
            return {"tld": tld, "currency": "USD"}

        first_price = product.find(".//Price")
        return {
            "tld": tld,
            "registration": first_price.attrib.get("YourPrice") if first_price is not None else None,
            "renewal": first_price.attrib.get("YourPrice") if first_price is not None else None,
            "transfer": first_price.attrib.get("YourPrice") if first_price is not None else None,
            "currency": "USD",
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.provider_order: List[str] = []
        self.active_provider: Optional[str] = None
        self.api_client: Optional[DomainAPIClient] = None  # Backwards compatibility
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client:
            self.set_api_client(api_client)

    @staticmethod
    def _provider_name_from_client(api_client: DomainAPIClient) -> str:
        class_name = api_client.__class__.__name__
        return class_name.replace("APIClient", "").lower()
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the primary API client (backwards compatible helper)."""
        inferred_name = self._provider_name_from_client(api_client)
        self.add_api_client(inferred_name, api_client, set_active=True)

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient, set_active: bool = False):
        """Register an API client for a provider."""
        key = provider_name.strip().lower()
        self.api_clients[key] = api_client
        if key not in self.provider_order:
            self.provider_order.append(key)

        if set_active or not self.active_provider:
            self.active_provider = key
            self.api_client = api_client

    def set_active_provider(self, provider_name: str) -> bool:
        """Set which provider should be tried first."""
        key = provider_name.strip().lower()
        if key not in self.api_clients:
            return False
        self.active_provider = key
        self.api_client = self.api_clients[key]
        return True

    def get_active_provider(self) -> Optional[str]:
        """Get currently preferred provider name."""
        return self.active_provider

    def list_providers(self) -> List[str]:
        """List registered provider names in priority order."""
        return list(self.provider_order)

    def _iter_provider_clients(self, provider: Optional[str] = None) -> List[Tuple[str, DomainAPIClient]]:
        """Return provider/client pairs in query order."""
        if provider:
            key = provider.strip().lower()
            client = self.api_clients.get(key)
            return [(key, client)] if client else []

        if not self.api_clients:
            return []

        order = list(self.provider_order)
        if self.active_provider and self.active_provider in order:
            order.remove(self.active_provider)
            order.insert(0, self.active_provider)

        return [(name, self.api_clients[name]) for name in order]
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"
    
    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        provider: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        provider_clients = self._iter_provider_clients(provider)
        if not provider_clients:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            for provider_name, client in provider_clients:
                try:
                    result = client.search_domain(domain)
                except Exception as e:
                    logger.warning(f"{provider_name} search failed for {domain}: {e}")
                    continue

                if result.get("available"):
                    price = _parse_price(result.get("price"), default=999.0)

                    if price <= max_price:
                        return {
                            "domain": domain,
                            "price": price,
                            "tld": tld,
                            "provider": provider_name,
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
        provider_clients = self._iter_provider_clients(provider)
        if not provider_clients:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        for provider_name, client in provider_clients:
            try:
                result = client.purchase_domain(domain, years=1)
            except Exception as e:
                logger.warning(f"{provider_name} purchase failed for {domain}: {e}")
                continue

            if result.get("success"):
                now = datetime.now(timezone.utc)
                self.current_spending += price
                self.owned_domains.append(
                    {
                        "domain": domain,
                        "price": price,
                        "provider": provider_name,
                        "purchased_at": now,
                        "expires_at": now + timedelta(days=365),
                    }
                )

                # Set as active if no active domain
                if not self.active_domain:
                    self.active_domain = domain

                self.active_provider = provider_name
                self.api_client = client
                logger.info(f"Successfully purchased domain: {domain} for ${price} via {provider_name}")
                return True

            logger.warning(
                f"{provider_name} rejected purchase for {domain}: {result.get('message', 'unknown error')}"
            )

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
            provider=provider or domain_info.get("provider"),
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
            "domains_owned": len(self.owned_domains),
            "providers_configured": len(self.api_clients),
            "active_provider": self.active_provider,
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
