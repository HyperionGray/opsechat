"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
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
    Supports sandbox and production environments.
    """

    XML_NS = {"nc": "http://api.namecheap.com/xml.response"}

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str,
        api_user: Optional[str] = None,
        sandbox: bool = False,
        default_contacts: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key, None)
        self.username = username
        self.api_user = api_user or username
        self.client_ip = client_ip
        self.default_contacts = default_contacts or {}
        self.base_url = (
            "https://api.sandbox.namecheap.com/xml.response"
            if sandbox
            else "https://api.namecheap.com/xml.response"
        )
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> Optional[ET.Element]:
        """Make Namecheap API request and return parsed XML."""
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
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as e:
            logger.error("Namecheap API request failed: %s", e)
            return None

    def _is_success(self, root: Optional[ET.Element]) -> bool:
        return root is not None and root.attrib.get("Status") == "OK"

    def _error_message(self, root: Optional[ET.Element]) -> str:
        if root is None:
            return "No response from Namecheap API"

        node = root.find(".//nc:Errors/nc:Error", self.XML_NS)
        if node is not None and node.text:
            return node.text.strip()
        return "Unknown Namecheap API error"

    def _build_contact_payload(self) -> Dict[str, str]:
        """
        Build a minimal contact payload for namecheap.domains.create.
        Namecheap requires separate registrant/admin/tech/aux billing fields.
        """
        first_name = self.default_contacts.get("first_name", "Ops")
        last_name = self.default_contacts.get("last_name", "Chat")
        address1 = self.default_contacts.get("address1", "123 Privacy St")
        city = self.default_contacts.get("city", "Wilmington")
        state = self.default_contacts.get("state", "DE")
        postal_code = self.default_contacts.get("postal_code", "19801")
        country = self.default_contacts.get("country", "US")
        phone = self.default_contacts.get("phone", "+1.5555555555")
        email = self.default_contacts.get("email", "ops@example.com")

        contact_values = {
            "FirstName": first_name,
            "LastName": last_name,
            "Address1": address1,
            "City": city,
            "StateProvince": state,
            "PostalCode": postal_code,
            "Country": country,
            "Phone": phone,
            "EmailAddress": email,
        }

        payload: Dict[str, str] = {}
        for prefix in ("Registrant", "Admin", "Tech", "AuxBilling"):
            for key, value in contact_values.items():
                payload[f"{prefix}{key}"] = value
        return payload

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available via Namecheap."""
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})

        if not self._is_success(root):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": self._error_message(root),
            }

        node = root.find(".//nc:CommandResponse/nc:DomainCheckResult", self.XML_NS)
        if node is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "Missing DomainCheckResult in Namecheap response",
            }

        available = node.attrib.get("Available", "false").lower() == "true"
        price = None
        if available:
            tld = domain.split(".")[-1]
            pricing = self.get_pricing(tld)
            price = pricing.get("registration")

        return {
            "domain": node.attrib.get("Domain", domain),
            "available": available,
            "price": price,
            "currency": "USD",
        }

    def _get_action_price(self, tld: str, action: str) -> Optional[float]:
        root = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "DOMAINS",
                "ActionName": action,
                "ProductName": tld.lstrip("."),
            },
        )
        if not self._is_success(root):
            return None

        price_nodes = root.findall(".//nc:Price", self.XML_NS)
        one_year_node = None
        for node in price_nodes:
            if node.attrib.get("Duration") == "1":
                one_year_node = node
                break
        if one_year_node is None and price_nodes:
            one_year_node = price_nodes[0]
        if one_year_node is None:
            return None

        value = one_year_node.attrib.get("YourPrice") or one_year_node.attrib.get("Price")
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get Namecheap registration and renewal pricing when available."""
        registration = self._get_action_price(tld, "REGISTER")
        renewal = self._get_action_price(tld, "RENEW")

        return {
            "tld": tld.lstrip("."),
            "registration": registration,
            "renewal": renewal,
            "transfer": None,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase a domain using configured default contacts."""
        payload = {"DomainName": domain, "Years": str(years)}
        payload.update(self._build_contact_payload())

        root = self._make_request("namecheap.domains.create", payload)
        if not self._is_success(root):
            return {
                "success": False,
                "domain": domain,
                "message": self._error_message(root),
                "order_id": None,
            }

        result_node = root.find(".//nc:CommandResponse/nc:DomainCreateResult", self.XML_NS)
        return {
            "success": True,
            "domain": domain,
            "message": "Domain purchased successfully",
            "order_id": result_node.attrib.get("OrderID") if result_node is not None else None,
        }

    def list_domains(self) -> List[str]:
        """List domains in Namecheap account."""
        root = self._make_request("namecheap.domains.getList")
        if not self._is_success(root):
            return []

        domains = []
        for node in root.findall(".//nc:DomainGetListResult/nc:Domain", self.XML_NS):
            name = node.attrib.get("Name")
            if name:
                domains.append(name)

        if domains:
            return domains

        # Fallback path if Namecheap changes XML nesting.
        for node in root.findall(".//nc:Domain", self.XML_NS):
            name = node.attrib.get("Name")
            if name:
                domains.append(name)
        return domains


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
    ):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.registrar = registrar
        self._api_config: Dict[str, Any] = {}
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    @staticmethod
    def _mask_secret(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * (len(value) - 4)}{value[-4:]}"

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @staticmethod
    def serialize_owned_domains(owned_domains: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert datetime values to ISO strings for JSON storage."""
        serialized: List[Dict[str, Any]] = []
        for domain in owned_domains:
            item = dict(domain)
            for key in ("purchased_at", "expires_at"):
                value = item.get(key)
                if isinstance(value, datetime):
                    item[key] = value.isoformat()
            serialized.append(item)
        return serialized

    @staticmethod
    def deserialize_owned_domains(owned_domains: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse stored ISO timestamps back into datetime objects."""
        deserialized: List[Dict[str, Any]] = []
        for domain in owned_domains:
            item = dict(domain)
            for key in ("purchased_at", "expires_at"):
                value = item.get(key)
                if isinstance(value, str):
                    try:
                        item[key] = datetime.fromisoformat(value)
                    except ValueError:
                        # Preserve original value if legacy/non-ISO format.
                        pass
            deserialized.append(item)
        return deserialized

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        **kwargs: Any,
    ):
        """
        Configure API client and budget.
        Supports porkbun and namecheap registrars.
        """
        registrar_name = (registrar or "porkbun").strip().lower()
        self.monthly_budget = float(monthly_budget)

        if registrar_name == "porkbun":
            api_secret = kwargs.get("api_secret") or secret_key or kwargs.get("porkbun_secret_key")
            if not api_key or not api_secret:
                raise ValueError("Porkbun requires api_key and secret_key/api_secret")

            self.set_api_client(PorkbunAPIClient(api_key, api_secret))
            self.registrar = "porkbun"
            self._api_config = {"api_key": api_key, "api_secret": api_secret}
            return

        if registrar_name == "namecheap":
            username = kwargs.get("username")
            client_ip = kwargs.get("client_ip")
            api_user = kwargs.get("api_user")
            sandbox = self._to_bool(kwargs.get("sandbox", False))
            default_contacts = kwargs.get("default_contacts")

            if not api_key or not username or not client_ip:
                raise ValueError("Namecheap requires api_key, username, and client_ip")

            self.set_api_client(
                NamecheapAPIClient(
                    api_key=api_key,
                    username=username,
                    client_ip=client_ip,
                    api_user=api_user,
                    sandbox=sandbox,
                    default_contacts=default_contacts,
                )
            )
            self.registrar = "namecheap"
            self._api_config = {
                "api_key": api_key,
                "username": username,
                "client_ip": client_ip,
                "api_user": api_user or username,
                "sandbox": sandbox,
                "has_default_contacts": bool(default_contacts),
            }
            return

        raise ValueError(f"Unsupported registrar: {registrar_name}")

    def get_config(self) -> Dict[str, Any]:
        """Get current manager configuration with secrets masked."""
        config: Dict[str, Any] = {
            "registrar": self.registrar,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

        if self.registrar == "porkbun":
            config.update(
                {
                    "api_key": self._mask_secret(self._api_config.get("api_key")),
                    "api_secret": self._mask_secret(self._api_config.get("api_secret")),
                }
            )
        elif self.registrar == "namecheap":
            config.update(
                {
                    "api_key": self._mask_secret(self._api_config.get("api_key")),
                    "username": self._api_config.get("username"),
                    "api_user": self._api_config.get("api_user"),
                    "client_ip": self._api_config.get("client_ip"),
                    "sandbox": self._api_config.get("sandbox", False),
                    "has_default_contacts": self._api_config.get("has_default_contacts", False),
                }
            )

        return config
    
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
        if not self.api_client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = result.get("price", 999)

                if price is None:
                    continue
                
                if isinstance(price, str):
                    # Remove currency symbols
                    try:
                        price = float(price.replace("$", "").replace("€", ""))
                    except ValueError:
                        continue
                
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
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
            domain_info["price"]
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
