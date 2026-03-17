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
    API docs: https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    REQUIRED_CONTACT_FIELDS = {
        "first_name",
        "last_name",
        "address1",
        "city",
        "state_province",
        "postal_code",
        "country",
        "phone",
        "email_address",
    }

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str,
        api_user: Optional[str] = None,
        sandbox: bool = False,
        default_contact: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key, None)
        self.username = username
        self.api_user = api_user or username
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.default_contact = default_contact or {}
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute Namecheap API request and return parsed XML payload."""
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
            root = ET.fromstring(response.text)
            status = root.attrib.get("Status", "ERROR").upper()
            errors = [node.text or "" for node in root.findall(".//{*}Error")]
            return {
                "status": "SUCCESS" if status == "OK" else "ERROR",
                "errors": errors,
                "message": "; ".join(errors),
                "root": root,
            }
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return {"status": "ERROR", "errors": [str(e)], "message": str(e), "root": None}

    def _normalize_price(self, price: Optional[str]) -> Optional[float]:
        """Normalize price values like '$1.23' to float."""
        if price is None:
            return None
        cleaned = str(price).replace("$", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    def search_domain(self, domain: str) -> Dict:
        """Check if a domain is available on Namecheap."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        root = result.get("root")
        if result.get("status") != "SUCCESS" or root is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": result.get("message", "Namecheap API error"),
            }

        check_node = root.find(".//{*}DomainCheckResult")
        if check_node is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "Invalid Namecheap response payload",
            }

        available_flag = str(check_node.attrib.get("Available", "false")).lower()
        price = (
            check_node.attrib.get("PremiumRegistrationPrice")
            or check_node.attrib.get("PremiumRenewalPrice")
            or check_node.attrib.get("RegistrationPrice")
        )

        return {
            "domain": domain,
            "available": available_flag in {"true", "yes", "1"},
            "price": self._normalize_price(price),
            "currency": "USD",
        }

    def _build_contact_params(self, contact: Dict[str, str]) -> Dict[str, str]:
        """Build Namecheap contact payload for all required contact groups."""
        missing = [field for field in self.REQUIRED_CONTACT_FIELDS if not contact.get(field)]
        if missing:
            raise ValueError(
                "Missing Namecheap contact fields: "
                + ", ".join(sorted(missing))
                + ". Provide a complete contact profile."
            )

        params = {}
        field_map = {
            "FirstName": contact["first_name"],
            "LastName": contact["last_name"],
            "Address1": contact["address1"],
            "City": contact["city"],
            "StateProvince": contact["state_province"],
            "PostalCode": contact["postal_code"],
            "Country": contact["country"],
            "Phone": contact["phone"],
            "EmailAddress": contact["email_address"],
        }
        for contact_type in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for key, value in field_map.items():
                params[f"{contact_type}{key}"] = value
        return params

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain via Namecheap.

        Namecheap requires contact profile fields. Configure default_contact
        during client initialization to enable purchases.
        """
        try:
            contact_payload = self._build_contact_params(self.default_contact)
        except ValueError as e:
            return {"success": False, "domain": domain, "message": str(e), "order_id": None}

        payload = {
            "DomainName": domain,
            "Years": years,
        }
        payload.update(contact_payload)
        result = self._make_request("namecheap.domains.create", payload)
        root = result.get("root")

        if result.get("status") != "SUCCESS" or root is None:
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Namecheap API error"),
                "order_id": None,
            }

        create_node = root.find(".//{*}DomainCreateResult")
        order_id = create_node.attrib.get("OrderID") if create_node is not None else None
        registered = (
            str(create_node.attrib.get("Registered", "false")).lower() in {"true", "yes", "1"}
            if create_node is not None
            else False
        )
        return {
            "success": registered,
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": order_id,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Fetch pricing information for a TLD."""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductName": tld.upper(),
            },
        )
        root = result.get("root")
        if result.get("status") != "SUCCESS" or root is None:
            return {}

        price_node = root.find(".//{*}ProductPrice")
        if price_node is None:
            return {}

        return {
            "tld": tld,
            "registration": self._normalize_price(price_node.attrib.get("Price")),
            "renewal": self._normalize_price(price_node.attrib.get("AdditionalCost")),
            "currency": price_node.attrib.get("Currency", "USD"),
        }

    def list_domains(self) -> List[str]:
        """List currently owned domains."""
        result = self._make_request("namecheap.domains.getList")
        root = result.get("root")
        if result.get("status") != "SUCCESS" or root is None:
            return []

        domains = []
        for node in root.findall(".//{*}Domain"):
            name = node.attrib.get("Name")
            if name:
                domains.append(name)
        return domains


def create_domain_api_client(
    provider: str,
    *,
    api_key: str,
    api_secret: Optional[str] = None,
    username: Optional[str] = None,
    client_ip: str = "127.0.0.1",
    sandbox: bool = False,
    default_contact: Optional[Dict[str, str]] = None,
) -> DomainAPIClient:
    """Factory helper to create supported domain registrar clients."""
    provider_normalized = (provider or "").strip().lower()
    if provider_normalized == "porkbun":
        if not api_secret:
            raise ValueError("Porkbun requires api_secret")
        return PorkbunAPIClient(api_key, api_secret)

    if provider_normalized == "namecheap":
        if not username:
            raise ValueError("Namecheap requires username")
        return NamecheapAPIClient(
            api_key=api_key,
            username=username,
            client_ip=client_ip,
            sandbox=sandbox,
            default_contact=default_contact,
        )

    raise ValueError(f"Unsupported provider: {provider}")


def _mask_secret(value: Optional[str]) -> str:
    """Mask sensitive values for safe config display."""
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.provider = "manual"
        self._config: Dict[str, Any] = {}
        if api_client is not None:
            class_name = api_client.__class__.__name__.lower()
            if "porkbun" in class_name:
                self.provider = "porkbun"
            elif "namecheap" in class_name:
                self.provider = "namecheap"
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        class_name = api_client.__class__.__name__.lower()
        if "porkbun" in class_name:
            self.provider = "porkbun"
        elif "namecheap" in class_name:
            self.provider = "namecheap"
        else:
            self.provider = "custom"

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: float = 50.0,
        provider: str = "porkbun",
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        default_contact: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Configure the manager with registrar credentials.

        This method is used by email routes that apply runtime configuration.
        """
        client = create_domain_api_client(
            provider=provider,
            api_key=api_key,
            api_secret=secret_key,
            username=username,
            client_ip=client_ip,
            sandbox=sandbox,
            default_contact=default_contact,
        )
        self.set_api_client(client)
        self.monthly_budget = float(monthly_budget)
        self._config = {
            "provider": provider,
            "api_key": api_key,
            "secret_key": secret_key,
            "username": username,
            "client_ip": client_ip,
            "sandbox": sandbox,
            "default_contact_configured": bool(default_contact),
        }
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return safe configuration/status data for UI display."""
        return {
            "configured": self.api_client is not None,
            "provider": self.provider,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "api_key": _mask_secret(self._config.get("api_key")),
            "secret_key": _mask_secret(self._config.get("secret_key")),
            "username": self._config.get("username") or "",
            "client_ip": self._config.get("client_ip") or "",
            "sandbox": bool(self._config.get("sandbox")),
            "default_contact_configured": bool(self._config.get("default_contact_configured")),
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
                
                if isinstance(price, str):
                    # Remove currency symbols
                    try:
                        price = float(price.replace("$", "").replace("€", ""))
                    except ValueError:
                        logger.warning(f"Invalid price format for {domain}: {price}")
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
        result = self.rotate_domain_with_details()
        if result.get("success"):
            return result.get("domain")
        return None

    def rotate_domain_with_details(self) -> Dict[str, Any]:
        """Rotate to a new domain and return structured result details."""
        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {
                "success": False,
                "message": "Could not find available cheap domain",
                "domain": None,
            }
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            return {
                "success": True,
                "message": "Domain rotated successfully",
                "domain": self.active_domain,
                "price": domain_info["price"],
            }
        
        return {
            "success": False,
            "message": "Domain purchase failed or exceeded budget",
            "domain": None,
            "price": domain_info.get("price"),
        }
    
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
