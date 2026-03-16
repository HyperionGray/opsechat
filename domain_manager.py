"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET
import requests
import random
import string
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    @abstractmethod
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        pass
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        pass
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        pass


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
            "currency": result.get("currency", "USD"),
            "provider": "porkbun"
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

    PRODUCTION_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None
    ):
        super().__init__(api_key)
        self.username = username
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.contact_profile = contact_profile or {}
        self.base_url = self.SANDBOX_URL if sandbox else self.PRODUCTION_URL
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Optional[ET.Element]:
        request_params = {
            "ApiUser": self.username,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            request_params.update(params)

        try:
            response = self.session.get(self.base_url, params=request_params, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            errors = root.findall(".//{*}Errors/{*}Error")
            if errors:
                error_message = "; ".join((e.text or "").strip() for e in errors if (e.text or "").strip())
                logger.error("Namecheap API request failed: %s", error_message)
                return None
            return root
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return None

    @staticmethod
    def _as_bool(value: str) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes"}

    def search_domain(self, domain: str) -> Dict:
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if root is None:
            return {"domain": domain, "available": False, "message": "Namecheap request failed"}

        domain_check = root.find(".//{*}DomainCheckResult")
        if domain_check is None:
            return {"domain": domain, "available": False, "message": "Unexpected Namecheap API response"}

        price = domain_check.attrib.get("PremiumRegistrationPrice")
        if price in {"", "0", "0.00"}:
            price = None

        return {
            "domain": domain,
            "available": self._as_bool(domain_check.attrib.get("Available", "false")),
            "price": price,
            "premium": self._as_bool(domain_check.attrib.get("IsPremiumName", "false")),
            "currency": "USD",
            "provider": "namecheap",
        }

    def _build_contact_payload(self) -> Optional[Dict[str, str]]:
        required = {
            "first_name": "FirstName",
            "last_name": "LastName",
            "address1": "Address1",
            "city": "City",
            "state": "StateProvince",
            "postal_code": "PostalCode",
            "country": "Country",
            "phone": "Phone",
            "email": "EmailAddress",
        }
        missing = [k for k in required if not self.contact_profile.get(k)]
        if missing:
            logger.error(
                "Namecheap purchase requires contact profile keys: %s",
                ", ".join(sorted(missing)),
            )
            return None

        payload: Dict[str, str] = {}
        for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for source_key, api_key_suffix in required.items():
                payload[f"{role}{api_key_suffix}"] = self.contact_profile[source_key]
        return payload

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        contact_payload = self._build_contact_payload()
        if contact_payload is None:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Missing Namecheap contact profile. "
                    "Configure first_name,last_name,address1,city,state,postal_code,country,phone,email."
                ),
            }

        params: Dict[str, Any] = {
            "DomainName": domain,
            "Years": years,
            "AddFreeWhoisguard": "yes",
        }
        params.update(contact_payload)
        root = self._make_request("namecheap.domains.create", params)

        if root is None:
            return {"success": False, "domain": domain, "message": "Namecheap request failed"}

        create_result = root.find(".//{*}DomainCreateResult")
        if create_result is None:
            return {"success": False, "domain": domain, "message": "Unexpected Namecheap API response"}

        success = self._as_bool(create_result.attrib.get("Registered", "false"))
        return {
            "success": success,
            "domain": domain,
            "message": "Purchase completed" if success else "Purchase failed",
            "order_id": create_result.attrib.get("OrderID"),
            "provider": "namecheap",
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        root = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "DOMAINS",
                "ActionName": "REGISTER",
                "ProductName": tld,
            },
        )
        if root is None:
            return {}

        selected_price = None
        for price_node in root.findall(".//{*}Price"):
            duration = str(price_node.attrib.get("Duration", "")).strip()
            if duration in {"1", "1Y"}:
                selected_price = price_node
                break
            if selected_price is None:
                selected_price = price_node

        if selected_price is None:
            return {}

        return {
            "tld": tld,
            "registration": selected_price.attrib.get("YourPrice"),
            "currency": "USD",
            "provider": "namecheap",
        }


SUPPORTED_REGISTRARS = ("porkbun", "namecheap")


def create_domain_api_client(provider: str, **kwargs) -> DomainAPIClient:
    """
    Factory for supported registrar API clients.
    """
    normalized = (provider or "").strip().lower()
    if normalized == "porkbun":
        api_key = kwargs.get("api_key")
        api_secret = kwargs.get("api_secret")
        if not api_key or not api_secret:
            raise ValueError("Porkbun requires api_key and api_secret")
        return PorkbunAPIClient(api_key=api_key, api_secret=api_secret)

    if normalized == "namecheap":
        api_key = kwargs.get("api_key")
        username = kwargs.get("username")
        client_ip = kwargs.get("client_ip", "127.0.0.1")
        sandbox = kwargs.get("sandbox", False)
        contact_profile = kwargs.get("contact_profile")
        if not api_key or not username:
            raise ValueError("Namecheap requires api_key and username")
        return NamecheapAPIClient(
            api_key=api_key,
            username=username,
            client_ip=client_ip,
            sandbox=sandbox,
            contact_profile=contact_profile,
        )

    raise ValueError(
        f"Unsupported provider '{provider}'. Supported providers: {', '.join(SUPPORTED_REGISTRARS)}"
    )


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
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
    
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
                price = self._parse_price(result.get("price"))
                if price is None:
                    pricing = self.api_client.get_pricing(tld)
                    price = self._parse_price(pricing.get("registration"))

                if price is None:
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": result.get("provider")
                    }
        
        return None

    @staticmethod
    def _parse_price(value: Any) -> Optional[float]:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace("€", "").replace(",", "")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                logger.warning("Unable to parse price value: %s", value)
                return None

        logger.warning("Unsupported price value type: %s", type(value).__name__)
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
