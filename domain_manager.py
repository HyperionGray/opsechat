"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

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
    Namecheap API client for domain management
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"
    XML_NAMESPACE = {"nc": "http://api.namecheap.com/xml.response"}

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: str,
        client_ip: str,
        sandbox: bool = False,
        contact_details: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key)
        self.api_user = api_user
        self.username = username
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.contact_details = contact_details or {}
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict] = None) -> Dict:
        """Make Namecheap API request and parse XML response."""
        url = self.SANDBOX_URL if self.sandbox else self.BASE_URL
        params = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }

        if data:
            params.update(data)

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return self._parse_response(response.text)
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return {"status": "ERROR", "message": str(e)}

    def _parse_response(self, xml_payload: str) -> Dict:
        """Parse Namecheap XML API response."""
        try:
            root = ET.fromstring(xml_payload)
        except ET.ParseError as e:
            logger.error(f"Failed parsing Namecheap XML response: {e}")
            return {"status": "ERROR", "message": f"Invalid XML: {e}"}

        status = root.attrib.get("Status", "ERROR")
        errors = []
        for error_node in root.findall(".//nc:Errors/nc:Error", self.XML_NAMESPACE):
            if error_node.text:
                errors.append(error_node.text.strip())

        if status != "OK" or errors:
            message = "; ".join(errors) if errors else f"Namecheap API status={status}"
            return {"status": "ERROR", "message": message, "xml": root}

        return {"status": "SUCCESS", "xml": root}

    @staticmethod
    def _split_domain(domain: str) -> Optional[Tuple[str, str]]:
        """Split a fully qualified domain into SLD + TLD."""
        if "." not in domain:
            return None
        parts = domain.split(".")
        sld = parts[0]
        tld = ".".join(parts[1:])
        if not sld or not tld:
            return None
        return sld, tld

    def _build_contact_payload(self) -> Optional[Dict[str, str]]:
        """
        Build Namecheap contacts payload.
        Domains cannot be created without contact profile fields.
        """
        required_fields = [
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
        missing = [field for field in required_fields if not self.contact_details.get(field)]
        if missing:
            logger.error(
                "Missing Namecheap contact fields required for purchase: %s",
                ", ".join(missing),
            )
            return None

        payload: Dict[str, str] = {}
        for contact_type in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field in required_fields:
                payload[f"{contact_type}{field}"] = self.contact_details[field]

            if self.contact_details.get("OrganizationName"):
                payload[f"{contact_type}OrganizationName"] = self.contact_details[
                    "OrganizationName"
                ]
            if self.contact_details.get("PhoneExt"):
                payload[f"{contact_type}PhoneExt"] = self.contact_details["PhoneExt"]

        return payload

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        result = self._make_request(
            "namecheap.domains.check",
            {"DomainList": domain},
        )
        if result.get("status") != "SUCCESS":
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
            }

        root = result["xml"]
        check_node = root.find(
            ".//nc:CommandResponse/nc:DomainCheckResult",
            self.XML_NAMESPACE,
        )
        if check_node is None:
            check_node = root.find(".//nc:DomainCheckResult", self.XML_NAMESPACE)

        if check_node is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
            }

        available = check_node.attrib.get("Available", "false").lower() == "true"
        price = check_node.attrib.get("Price") or check_node.attrib.get(
            "PremiumRegistrationPrice"
        )

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase a domain using Namecheap API."""
        split = self._split_domain(domain)
        if split is None:
            return {
                "success": False,
                "domain": domain,
                "message": "Invalid domain format",
                "order_id": None,
            }

        contact_payload = self._build_contact_payload()
        if not contact_payload:
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap contact profile is incomplete",
                "order_id": None,
            }

        sld, tld = split
        params = {
            "DomainName": domain,
            "SLD": sld,
            "TLD": tld,
            "Years": years,
            "AddFreeWhoisguard": "yes",
            "WGEnabled": "yes",
        }
        params.update(contact_payload)

        result = self._make_request("namecheap.domains.create", params)
        if result.get("status") != "SUCCESS":
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Namecheap domain purchase failed"),
                "order_id": None,
            }

        root = result["xml"]
        create_node = root.find(".//nc:DomainCreateResult", self.XML_NAMESPACE)
        if create_node is None:
            return {
                "success": False,
                "domain": domain,
                "message": "Missing DomainCreateResult in API response",
                "order_id": None,
            }

        registered = create_node.attrib.get("Registered", "false").lower() == "true"
        order_id = create_node.attrib.get("OrderID")
        charged_amount = create_node.attrib.get("ChargedAmount")

        return {
            "success": registered,
            "domain": domain,
            "message": "Domain registered successfully" if registered else "Domain registration failed",
            "order_id": order_id,
            "charged_amount": charged_amount,
        }

    def get_pricing(self, tld: str) -> Dict:
        """Get Namecheap registration pricing for a TLD."""
        normalized_tld = tld.lower().lstrip(".")
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "DOMAINS",
                "ActionName": "REGISTER",
            },
        )

        if result.get("status") != "SUCCESS":
            return {}

        root = result["xml"]
        product_nodes = root.findall(".//nc:Product", self.XML_NAMESPACE)
        matching_product = None
        for product in product_nodes:
            product_name = product.attrib.get("Name", "").lower().lstrip(".")
            if product_name == normalized_tld:
                matching_product = product
                break

        if matching_product is None:
            return {}

        price_node = matching_product.find(".//nc:Price", self.XML_NAMESPACE)
        if price_node is None:
            return {}

        return {
            "tld": normalized_tld,
            "registration": price_node.attrib.get("YourPrice") or price_node.attrib.get("Price"),
            "renewal": None,
            "transfer": None,
            "currency": price_node.attrib.get("Currency", "USD"),
        }

    def list_domains(self) -> List[str]:
        """List domains in Namecheap account."""
        result = self._make_request(
            "namecheap.domains.getList",
            {
                "Page": 1,
                "PageSize": 100,
                "SortBy": "NAME",
            },
        )
        if result.get("status") != "SUCCESS":
            return []

        root = result["xml"]
        domains = []
        for domain_node in root.findall(
            ".//nc:DomainGetListResult/nc:Domain",
            self.XML_NAMESPACE,
        ):
            domain_name = domain_node.attrib.get("Name")
            if domain_name:
                domains.append(domain_name)
        return domains


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        if api_client:
            self.api_clients["primary"] = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.active_provider: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient, provider_name: str = "primary"):
        """Set the domain API client"""
        self.api_client = api_client
        self.api_clients[provider_name] = api_client

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient):
        """Add additional provider-specific API client."""
        self.api_clients[provider_name] = api_client
        if self.api_client is None:
            self.api_client = api_client

    @staticmethod
    def _coerce_price(price) -> Optional[float]:
        """Normalize price values from API responses for comparisons."""
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
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _resolve_provider_name(self, client: Optional[DomainAPIClient]) -> Optional[str]:
        """Find configured provider name for a client instance."""
        if client is None:
            return None
        for provider_name, configured_client in self.api_clients.items():
            if configured_client is client:
                return provider_name
        return None

    def _ordered_clients(
        self, preferred_provider: Optional[str] = None
    ) -> List[Tuple[str, DomainAPIClient]]:
        """
        Return configured clients ordered by preferred provider first.
        Falls back to the legacy single-client field when needed.
        """
        clients: List[Tuple[str, DomainAPIClient]] = []
        if preferred_provider and preferred_provider in self.api_clients:
            clients.append((preferred_provider, self.api_clients[preferred_provider]))

        for provider_name, client in self.api_clients.items():
            if provider_name == preferred_provider:
                continue
            clients.append((provider_name, client))

        if not clients and self.api_client:
            clients.append(("primary", self.api_client))
        return clients
    
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
        preferred_provider: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        providers = self._ordered_clients(preferred_provider=preferred_provider)
        if not providers:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            best_candidate = None
            for provider_name, client in providers:
                result = client.search_domain(domain)

                if not result.get("available"):
                    continue

                parsed_price = self._coerce_price(result.get("price"))
                if parsed_price is None:
                    continue

                if parsed_price <= max_price and (
                    best_candidate is None or parsed_price < best_candidate["price"]
                ):
                    best_candidate = {
                        "domain": domain,
                        "price": parsed_price,
                        "tld": tld,
                        "provider": provider_name,
                    }

            if best_candidate:
                return best_candidate
        
        return None
    
    def purchase_domain_if_budget_allows(
        self, domain: str, price: float, provider_name: Optional[str] = None
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        providers = self._ordered_clients(preferred_provider=provider_name)
        if not providers:
            logger.error("No API client configured")
            return False
        effective_provider, effective_client = providers[0]
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = effective_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": effective_provider,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
                self.active_provider = effective_provider
            
            logger.info(
                "Successfully purchased domain: %s for $%s via %s",
                domain,
                price,
                effective_provider,
            )
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
        domain_info = self.find_cheap_available_domain(preferred_provider=preferred_provider)
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"],
            provider_name=domain_info.get("provider"),
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            self.active_provider = domain_info.get("provider")
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
            "providers_configured": list(self.api_clients.keys()),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
