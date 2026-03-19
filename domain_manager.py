"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
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
    https://www.namecheap.com/support/api/methods/domains/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_BASE_URL = "https://api.sandbox.namecheap.com/xml.response"
    REQUIRED_CONTACT_FIELDS = [
        "first_name",
        "last_name",
        "address1",
        "city",
        "state_province",
        "postal_code",
        "country",
        "phone",
        "email_address",
    ]

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.contact_profile = self._normalize_contact_profile(contact_profile or {})
        self.session = requests.Session()
        self.base_url = self.SANDBOX_BASE_URL if sandbox else self.BASE_URL

    def _normalize_contact_profile(self, profile: Dict[str, str]) -> Dict[str, str]:
        return {str(k).lower(): str(v).strip() for k, v in profile.items() if v is not None}

    def _extract_errors(self, root: ET.Element) -> List[str]:
        return [node.text.strip() for node in root.findall(".//Errors/Error") if node.text]

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
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
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return {"success": False, "errors": [str(e)]}

        errors = self._extract_errors(root)
        if errors:
            return {"success": False, "errors": errors, "xml_root": root}

        return {"success": True, "xml_root": root}

    def _build_contact_payload(self) -> Optional[Dict[str, str]]:
        missing = [field for field in self.REQUIRED_CONTACT_FIELDS if not self.contact_profile.get(field)]
        if missing:
            return None

        value_map = {
            "FirstName": self.contact_profile["first_name"],
            "LastName": self.contact_profile["last_name"],
            "Address1": self.contact_profile["address1"],
            "City": self.contact_profile["city"],
            "StateProvince": self.contact_profile["state_province"],
            "PostalCode": self.contact_profile["postal_code"],
            "Country": self.contact_profile["country"],
            "Phone": self.contact_profile["phone"],
            "EmailAddress": self.contact_profile["email_address"],
            "OrganizationName": self.contact_profile.get("organization_name", ""),
            "Address2": self.contact_profile.get("address2", ""),
        }

        payload: Dict[str, str] = {}
        for prefix in ["Registrant", "Admin", "Tech", "AuxBilling"]:
            for field_name, field_value in value_map.items():
                payload[f"{prefix}{field_name}"] = field_value
        return payload

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available"""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})

        if not result.get("success"):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "; ".join(result.get("errors", [])),
            }

        node = result["xml_root"].find(".//DomainCheckResult")
        if node is None:
            return {"domain": domain, "available": False, "price": None, "currency": "USD"}

        return {
            "domain": domain,
            "available": str(node.get("Available", "false")).lower() == "true",
            "price": node.get("PremiumRegistrationPrice") or node.get("RegularPrice"),
            "currency": node.get("Currency", "USD"),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain (requires contact profile values)"""
        contact_payload = self._build_contact_payload()
        if not contact_payload:
            missing = [field for field in self.REQUIRED_CONTACT_FIELDS if not self.contact_profile.get(field)]
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Missing Namecheap contact profile fields for purchase: "
                    + ", ".join(sorted(missing))
                ),
                "order_id": None,
            }

        payload = {"DomainName": domain, "Years": years}
        payload.update(contact_payload)
        result = self._make_request("namecheap.domains.create", payload)

        if not result.get("success"):
            return {
                "success": False,
                "domain": domain,
                "message": "; ".join(result.get("errors", [])),
                "order_id": None,
            }

        create_node = result["xml_root"].find(".//DomainCreateResult")
        order_node = result["xml_root"].find(".//OrderID")
        registered = (
            create_node is not None
            and str(create_node.get("Registered", "false")).lower() == "true"
        )

        return {
            "success": registered,
            "domain": domain,
            "message": "Purchased" if registered else "Purchase request was not accepted",
            "order_id": order_node.text if order_node is not None and order_node.text else None,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get pricing for TLD registration"""
        tld_name = tld.replace(".", "").lower()
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "register",
                "ProductName": tld_name,
            },
        )

        if not result.get("success"):
            return {}

        price_node = result["xml_root"].find(".//ProductPrice")
        if price_node is None:
            return {}

        return {
            "tld": tld_name,
            "registration": (
                price_node.get("YourPrice")
                or price_node.get("RegularPrice")
                or price_node.get("Price")
            ),
            "renewal": price_node.get("RegularPrice") or price_node.get("Price"),
            "transfer": price_node.get("RegularPrice") or price_node.get("Price"),
            "currency": price_node.get("Currency", "USD"),
        }


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
        self._config: Dict[str, Any] = {
            "registrar": "porkbun",
            "monthly_budget": monthly_budget,
        }
        if api_client:
            self.set_api_client(api_client)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        if isinstance(api_client, NamecheapAPIClient):
            self._config["registrar"] = "namecheap"
        else:
            self._config["registrar"] = "porkbun"
    
    @staticmethod
    def _parse_price(value: Any, default: float = 999.0) -> float:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace("€", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return default
        return default
    
    @classmethod
    def create_api_client(cls, registrar: str, **config: Any) -> DomainAPIClient:
        registrar_name = (registrar or "porkbun").strip().lower()
        if registrar_name == "porkbun":
            api_key = config.get("api_key", "")
            api_secret = config.get("api_secret") or config.get("secret_key")
            if not api_key or not api_secret:
                raise ValueError("Porkbun requires api_key and api_secret")
            return PorkbunAPIClient(api_key, api_secret)
        if registrar_name == "namecheap":
            api_user = config.get("api_user", "")
            api_key = config.get("api_key", "")
            if not api_user or not api_key:
                raise ValueError("Namecheap requires api_user and api_key")
            return NamecheapAPIClient(
                api_user=api_user,
                api_key=api_key,
                username=config.get("username"),
                client_ip=config.get("client_ip", "127.0.0.1"),
                sandbox=bool(config.get("sandbox", False)),
                contact_profile=config.get("contact_profile"),
            )
        raise ValueError(f"Unsupported registrar: {registrar}")
    
    def configure(self, registrar: str = "porkbun", monthly_budget: float = 50.0, **kwargs: Any):
        """Configure manager and instantiate registrar API client"""
        monthly_budget = float(monthly_budget)
        if monthly_budget <= 0:
            raise ValueError("monthly_budget must be greater than zero")
        
        api_client = self.create_api_client(registrar, **kwargs)
        self.set_api_client(api_client)
        self.monthly_budget = monthly_budget
        self._config = {
            "registrar": (registrar or "porkbun").strip().lower(),
            "monthly_budget": monthly_budget,
            "api_key": kwargs.get("api_key", ""),
            "api_secret": kwargs.get("api_secret") or kwargs.get("secret_key", ""),
            "api_user": kwargs.get("api_user", ""),
            "username": kwargs.get("username", ""),
            "client_ip": kwargs.get("client_ip", "127.0.0.1"),
            "sandbox": bool(kwargs.get("sandbox", False)),
            "contact_profile": kwargs.get("contact_profile", {}),
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get non-sensitive domain configuration summary"""
        budget = self.get_budget_status()
        api_key = self._config.get("api_key", "")
        api_secret = self._config.get("api_secret", "")
        return {
            "configured": bool(self.api_client),
            "registrar": self._config.get("registrar", "porkbun"),
            "monthly_budget": self.monthly_budget,
            "api_key_last4": api_key[-4:] if api_key else "",
            "has_api_secret": bool(api_secret),
            "api_user": self._config.get("api_user", ""),
            "username": self._config.get("username", ""),
            "client_ip": self._config.get("client_ip", ""),
            "sandbox": bool(self._config.get("sandbox", False)),
            "active_domain": self.active_domain,
            "domains_owned": budget["domains_owned"],
            "current_spending": budget["current_spending"],
            "remaining": budget["remaining"],
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
                price = self._parse_price(result.get("price"), default=999.0)
                
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
