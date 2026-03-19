"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
from abc import ABC, abstractmethod
import requests
import random
import string
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    @staticmethod
    def normalize_price(price: object, default: float = 999.0) -> float:
        """Normalize registrar price formats into a float."""
        if price is None:
            return default

        if isinstance(price, (int, float)):
            return float(price)

        if isinstance(price, str):
            sanitized = price.replace("$", "").replace("€", "").replace(",", "").strip()
            try:
                return float(sanitized)
            except ValueError:
                return default

        return default

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
    Namecheap uses an XML API endpoint.
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    REQUIRED_CONTACT_FIELDS = {
        "FirstName",
        "LastName",
        "Address1",
        "City",
        "StateProvince",
        "PostalCode",
        "Country",
        "Phone",
        "EmailAddress",
    }

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str = "127.0.0.1",
        contact_details: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key, api_secret=None)
        self.username = username
        self.client_ip = client_ip
        self.contact_details = contact_details or {}
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, object]] = None) -> ET.Element:
        """Make Namecheap API request and parse XML response."""
        query = {
            "ApiUser": self.username,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }

        if params:
            query.update(params)

        try:
            response = self.session.get(self.BASE_URL, params=query, timeout=30)
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return ET.fromstring('<ApiResponse Status="ERROR"></ApiResponse>')

    @staticmethod
    def _is_ok(root: ET.Element) -> bool:
        return root.attrib.get("Status") == "OK"

    @staticmethod
    def _extract_errors(root: ET.Element) -> str:
        errors = [node.text for node in root.findall(".//Errors/Error") if node.text]
        return "; ".join(errors) if errors else "Unknown API error"

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})

        if not self._is_ok(root):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": self._extract_errors(root),
            }

        result = root.find(".//DomainCheckResult")
        if result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "Malformed response: missing DomainCheckResult",
            }

        is_available = result.attrib.get("Available", "false").lower() == "true"
        premium_price = result.attrib.get("PremiumRegistrationPrice")

        price = self.normalize_price(premium_price, default=0.0) if premium_price else None
        return {
            "domain": domain,
            "available": is_available,
            "price": price,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain through Namecheap.
        If contact details are not provided, we attempt to use account defaults.
        """
        params: Dict[str, object] = {
            "DomainName": domain,
            "Years": years,
        }

        if self.contact_details and self.REQUIRED_CONTACT_FIELDS.issubset(self.contact_details.keys()):
            # Namecheap requires contact data for every role.
            for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
                for field, value in self.contact_details.items():
                    params[f"{role}{field}"] = value
        else:
            # Best-effort purchase path that relies on registrar account defaults.
            params["UseGlobalDefaults"] = "true"

        root = self._make_request("namecheap.domains.create", params)
        if not self._is_ok(root):
            return {
                "success": False,
                "domain": domain,
                "message": self._extract_errors(root),
                "order_id": None,
            }

        created = root.find(".//DomainCreateResult")
        order_id = None
        if created is not None:
            order_id = created.attrib.get("OrderID")

        return {
            "success": True,
            "domain": domain,
            "message": "Domain purchased successfully",
            "order_id": order_id,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get pricing for a TLD."""
        root = self._make_request("namecheap.users.getPricing", {"ProductType": "DOMAIN", "ActionName": "REGISTER"})
        if not self._is_ok(root):
            return {}

        normalized_tld = tld.lstrip(".").lower()
        for product in root.findall(".//Product"):
            product_name = product.attrib.get("Name", "").lower().lstrip(".")
            if product_name != normalized_tld:
                continue

            price_node = product.find(".//Price")
            if price_node is None:
                continue

            return {
                "tld": normalized_tld,
                "registration": price_node.attrib.get("Price"),
                "renewal": price_node.attrib.get("Price"),
                "transfer": price_node.attrib.get("Price"),
                "currency": price_node.attrib.get("Currency", "USD"),
            }

        return {}


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
        if isinstance(api_client, PorkbunAPIClient):
            self.registrar = "porkbun"
        elif isinstance(api_client, NamecheapAPIClient):
            self.registrar = "namecheap"
        else:
            self.registrar = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        if isinstance(api_client, PorkbunAPIClient):
            self.registrar = "porkbun"
        elif isinstance(api_client, NamecheapAPIClient):
            self.registrar = "namecheap"
        else:
            self.registrar = "custom"

    def configure(
        self,
        api_key: str,
        secret_key: str = "",
        monthly_budget: float = 10.0,
        registrar: str = "porkbun",
        username: str = "",
        client_ip: str = "127.0.0.1",
        contact_details: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """Configure domain API client and budget."""
        registrar_name = (registrar or "porkbun").strip().lower()
        if monthly_budget <= 0:
            raise ValueError("monthly_budget must be greater than 0")

        if registrar_name == "porkbun":
            if not api_key or not secret_key:
                raise ValueError("Porkbun requires api_key and secret_key")
            client: DomainAPIClient = PorkbunAPIClient(api_key, secret_key)
        elif registrar_name == "namecheap":
            if not api_key or not username:
                raise ValueError("Namecheap requires api_key and username")
            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                contact_details=contact_details,
            )
        else:
            raise ValueError(f"Unsupported registrar: {registrar_name}")

        self.set_api_client(client)
        self.monthly_budget = monthly_budget
        self.registrar = registrar_name

        return {
            "success": True,
            "registrar": self.registrar,
            "monthly_budget": self.monthly_budget,
        }

    def get_config(self) -> Dict:
        """Return non-sensitive domain manager configuration state."""
        has_api_client = self.api_client is not None
        has_api_key = bool(getattr(self.api_client, "api_key", "")) if has_api_client else False
        has_secret_key = bool(getattr(self.api_client, "api_secret", "")) if has_api_client else False
        username = getattr(self.api_client, "username", "") if has_api_client else ""
        client_ip = getattr(self.api_client, "client_ip", "") if has_api_client else ""

        return {
            "registrar": self.registrar or "unconfigured",
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "has_api_client": has_api_client,
            "has_api_key": has_api_key,
            "has_secret_key": has_secret_key,
            "username": username,
            "client_ip": client_ip,
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
                price = DomainAPIClient.normalize_price(result.get("price"), default=999.0)
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
