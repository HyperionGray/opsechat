"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
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


def _coerce_price(price) -> Optional[float]:
    """Normalize price values from registrar APIs into float USD values."""
    if price is None:
        return None
    if isinstance(price, (int, float)):
        return float(price)
    if isinstance(price, str):
        cleaned = (
            price.replace("$", "")
            .replace("€", "")
            .replace(",", "")
            .strip()
        )
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


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
    Namecheap API client for domain management.
    API docs: https://www.namecheap.com/support/api/intro/
    """

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
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        contact: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key, None)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.contact = contact or {}
        self.session = requests.Session()

    @staticmethod
    def _tag_matches(element, tag_suffix: str) -> bool:
        return element.tag.endswith(tag_suffix)

    def _make_request(self, command: str, params: Optional[Dict] = None) -> Optional[ET.Element]:
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
            return root
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return None

    @staticmethod
    def _extract_errors(root: ET.Element) -> List[str]:
        errors: List[str] = []
        for element in root.iter():
            if element.tag.endswith("Error") and element.text:
                errors.append(element.text.strip())
        return errors

    def search_domain(self, domain: str) -> Dict:
        """Check if a domain is available."""
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if root is None:
            return {"domain": domain, "available": False, "message": "request_failed"}

        errors = self._extract_errors(root)
        if errors:
            return {
                "domain": domain,
                "available": False,
                "message": "; ".join(errors),
            }

        for element in root.iter():
            if self._tag_matches(element, "DomainCheckResult"):
                available_value = str(element.attrib.get("Available", "")).lower()
                available = available_value in {"true", "yes", "1"}
                return {
                    "domain": domain,
                    "available": available,
                    "price": None,  # Namecheap check endpoint does not include final price.
                    "currency": "USD",
                }

        return {"domain": domain, "available": False, "message": "invalid_response"}

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase a domain.
        Requires Namecheap contact fields for Registrant/Admin/Tech/AuxBilling.
        """
        missing = [field for field in self.REQUIRED_CONTACT_FIELDS if not self.contact.get(field)]
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": f"missing_contact_fields: {', '.join(missing)}",
            }

        params = {
            "DomainName": domain,
            "Years": years,
        }
        for prefix in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field in self.REQUIRED_CONTACT_FIELDS:
                params[f"{prefix}{field}"] = self.contact[field]
            if self.contact.get("OrganizationName"):
                params[f"{prefix}OrganizationName"] = self.contact["OrganizationName"]

        root = self._make_request("namecheap.domains.create", params)
        if root is None:
            return {"success": False, "domain": domain, "message": "request_failed"}

        errors = self._extract_errors(root)
        if errors:
            return {"success": False, "domain": domain, "message": "; ".join(errors)}

        order_id = None
        for element in root.iter():
            if self._tag_matches(element, "DomainCreateResult"):
                order_id = element.attrib.get("OrderID")
                return {
                    "success": True,
                    "domain": domain,
                    "message": "",
                    "order_id": order_id,
                }

        return {"success": False, "domain": domain, "message": "invalid_response"}

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get registration pricing for a TLD."""
        normalized_tld = tld.lstrip(".").lower()
        root = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductName": normalized_tld,
            },
        )
        if root is None:
            return {}

        errors = self._extract_errors(root)
        if errors:
            return {}

        for element in root.iter():
            if not self._tag_matches(element, "Product"):
                continue
            if element.attrib.get("Name", "").lstrip(".").lower() != normalized_tld:
                continue
            for price_entry in element:
                if not self._tag_matches(price_entry, "Price"):
                    continue
                if price_entry.attrib.get("Duration", "1") != "1":
                    continue
                registration = (
                    price_entry.attrib.get("YourPrice")
                    or price_entry.attrib.get("Price")
                    or price_entry.attrib.get("AdditionalCost")
                )
                normalized_price = _coerce_price(registration)
                if normalized_price is None:
                    continue
                return {
                    "tld": normalized_tld,
                    "registration": normalized_price,
                    "renewal": _coerce_price(price_entry.attrib.get("YourRenewPrice")),
                    "transfer": _coerce_price(price_entry.attrib.get("YourTransferPrice")),
                    "currency": "USD",
                }

        return {}


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
    ):
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.primary_provider: Optional[str] = None
        if api_client:
            self.add_api_client("primary", api_client, make_primary=True)
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient, provider: str = "primary"):
        """Set the domain API client"""
        self.add_api_client(provider, api_client, make_primary=True)

    def add_api_client(self, provider: str, api_client: DomainAPIClient, make_primary: bool = False):
        """Add or replace a domain API client for a specific provider."""
        self.api_clients[provider] = api_client
        if self.primary_provider is None or make_primary:
            self.primary_provider = provider

    def _resolve_client(self, provider: Optional[str] = None) -> Optional[tuple]:
        """Resolve (provider_name, client) from explicit provider or primary."""
        if not self.api_clients:
            return None

        if provider:
            client = self.api_clients.get(provider)
            if client:
                return provider, client
            logger.error(f"No API client configured for provider: {provider}")
            return None

        if self.primary_provider and self.primary_provider in self.api_clients:
            return self.primary_provider, self.api_clients[self.primary_provider]

        first_provider = next(iter(self.api_clients))
        return first_provider, self.api_clients[first_provider]
    
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
        providers: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_clients:
            logger.error("No API clients configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        if providers:
            candidate_clients = [(name, self.api_clients[name]) for name in providers if name in self.api_clients]
        else:
            candidate_clients = list(self.api_clients.items())

        if not candidate_clients:
            logger.error("No matching API clients found for requested providers")
            return None
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            attempt_matches: List[Dict] = []

            for provider_name, api_client in candidate_clients:
                result = api_client.search_domain(domain)
                if not result.get("available"):
                    continue

                price = _coerce_price(result.get("price"))
                if price is None:
                    pricing = api_client.get_pricing(tld)
                    price = _coerce_price(pricing.get("registration"))

                if price is None:
                    continue

                if price <= max_price:
                    attempt_matches.append(
                        {
                            "domain": domain,
                            "price": price,
                            "tld": tld,
                            "provider": provider_name,
                        }
                    )

            if attempt_matches:
                return min(attempt_matches, key=lambda candidate: candidate["price"])
        
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
        resolved = self._resolve_client(provider)
        if not resolved:
            logger.error("No API client configured")
            return False
        provider_name, client = resolved
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": provider_name,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${price} via {provider_name}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self, preferred_provider: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        providers = [preferred_provider] if preferred_provider else None
        domain_info = self.find_cheap_available_domain(providers=providers)
        
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
            "domains_owned": len(self.owned_domains),
            "providers_configured": list(self.api_clients.keys()),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
