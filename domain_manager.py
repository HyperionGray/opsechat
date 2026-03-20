"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import xml.etree.ElementTree as ET
import random
import string
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

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
        raise NotImplementedError

    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError

    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError

    def list_domains(self) -> List[str]:
        """List owned domains where supported by registrar API"""
        return []


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
    XML API docs: https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str,
        contact_profile: Optional[Dict[str, str]] = None,
        sandbox: bool = False
    ):
        super().__init__(api_key, api_secret=username)
        self.username = username
        self.client_ip = client_ip
        self.contact_profile = contact_profile or {}
        self.sandbox = sandbox
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> Dict:
        """Make Namecheap API request and parse XML envelope."""
        payload = {
            "ApiUser": self.username,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command
        }
        if self.sandbox:
            payload["Sandbox"] = "true"
        if data:
            payload.update(data)

        try:
            response = self.session.get(self.BASE_URL, params=payload, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            if root.attrib.get("Status") != "OK":
                errors = [e.text for e in root.findall(".//Errors/Error") if e.text]
                return {
                    "status": "ERROR",
                    "message": "; ".join(errors) if errors else "Namecheap API returned error status"
                }
            return {"status": "SUCCESS", "xml_root": root}
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return {"status": "ERROR", "message": str(e)}

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if result.get("status") != "SUCCESS":
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": result.get("message", "Unknown Namecheap error")
            }

        xml_root = result["xml_root"]
        item = xml_root.find(".//DomainCheckResult")
        if item is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "Malformed Namecheap response"
            }

        available = item.attrib.get("Available", "false").lower() == "true"
        is_premium = item.attrib.get("IsPremiumName", "false").lower() == "true"
        premium_price = item.attrib.get("PremiumRegistrationPrice")
        price: Optional[float] = None
        if premium_price:
            try:
                price = float(premium_price)
            except ValueError:
                price = None

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "premium": is_premium
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain from Namecheap.
        Namecheap requires contact details, so this call needs contact_profile.
        """
        if not self.contact_profile:
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap contact profile is required for purchases"
            }

        payload = {
            "DomainName": domain,
            "Years": years,
            "AgreeToTerms": "yes"
        }
        payload.update(self._build_contact_payload())
        result = self._make_request("namecheap.domains.create", payload)

        if result.get("status") != "SUCCESS":
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Namecheap domain purchase failed")
            }

        xml_root = result["xml_root"]
        create_result = xml_root.find(".//DomainCreateResult")
        if create_result is None:
            return {
                "success": False,
                "domain": domain,
                "message": "Malformed Namecheap purchase response"
            }

        success = create_result.attrib.get("Registered", "false").lower() == "true"
        return {
            "success": success,
            "domain": domain,
            "message": "Domain purchased successfully" if success else "Domain purchase failed",
            "order_id": create_result.attrib.get("OrderID")
        }

    def get_pricing(self, tld: str) -> Dict:
        """
        Get approximate pricing data for TLD where available.
        Namecheap's pricing response can be nested, so this parser extracts
        the first exposed registration price.
        """
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAINS",
                "ActionName": "REGISTER",
                "ProductCategory": "DOMAINS",
                "ProductName": tld.lower()
            }
        )
        if result.get("status") != "SUCCESS":
            return {}

        xml_root = result["xml_root"]
        price_node = xml_root.find(".//Price")
        if price_node is None:
            return {"tld": tld.lower(), "currency": "USD"}

        return {
            "tld": tld.lower(),
            "registration": price_node.attrib.get("YourPrice") or price_node.attrib.get("Price"),
            "currency": price_node.attrib.get("Currency", "USD")
        }

    def _build_contact_payload(self) -> Dict[str, str]:
        """Build contact payload expected by Namecheap domain purchase API."""
        p = self.contact_profile
        defaults = {
            "first_name": "Domain",
            "last_name": "Operator",
            "address1": "123 Privacy St",
            "city": "Privacy City",
            "state_province": "CA",
            "postal_code": "94016",
            "country": "US",
            "phone": "+1.5555555555",
            "email_address": "admin@example.com",
            "organization": "Private Registration"
        }

        for key, value in defaults.items():
            p.setdefault(key, value)

        mapped = {
            "FirstName": p["first_name"],
            "LastName": p["last_name"],
            "Address1": p["address1"],
            "City": p["city"],
            "StateProvince": p["state_province"],
            "PostalCode": p["postal_code"],
            "Country": p["country"],
            "Phone": p["phone"],
            "EmailAddress": p["email_address"],
            "OrganizationName": p["organization"]
        }

        payload: Dict[str, str] = {}
        for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field, value in mapped.items():
                payload[f"{role}{field}"] = value
        return payload


def create_domain_api_client(registrar: str, **config: Any) -> DomainAPIClient:
    """Create a registrar API client from generic config."""
    normalized = registrar.lower().strip()
    if normalized == "porkbun":
        api_key = config.get("api_key")
        api_secret = config.get("api_secret") or config.get("secret_key")
        if not api_key or not api_secret:
            raise ValueError("Porkbun requires api_key and api_secret")
        return PorkbunAPIClient(api_key, api_secret)

    if normalized == "namecheap":
        api_key = config.get("api_key")
        username = config.get("username") or config.get("api_username")
        client_ip = config.get("client_ip")
        if not api_key or not username or not client_ip:
            raise ValueError("Namecheap requires api_key, username, and client_ip")
        return NamecheapAPIClient(
            api_key=api_key,
            username=username,
            client_ip=client_ip,
            contact_profile=config.get("contact_profile"),
            sandbox=bool(config.get("sandbox", False))
        )

    raise ValueError(f"Unsupported registrar: {registrar}")


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0, registrar: Optional[str] = None):
        self.api_client = api_client
        self.registrar = registrar
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if self.api_client and not self.registrar:
            if isinstance(self.api_client, PorkbunAPIClient):
                self.registrar = "porkbun"
            elif isinstance(self.api_client, NamecheapAPIClient):
                self.registrar = "namecheap"

    def set_api_client(self, api_client: DomainAPIClient, registrar: Optional[str] = None):
        """Set the domain API client"""
        self.api_client = api_client
        if registrar:
            self.registrar = registrar

    def configure(
        self,
        registrar: str = "porkbun",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Configure manager with registrar credentials.
        Supports both Porkbun and Namecheap.
        """
        config = dict(kwargs)
        if api_key:
            config["api_key"] = api_key
        if api_secret:
            config["api_secret"] = api_secret

        api_client = create_domain_api_client(registrar, **config)
        self.set_api_client(api_client, registrar=registrar.lower())

        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return non-secret domain configuration metadata."""
        config: Dict[str, Any] = {
            "registrar": self.registrar or "unconfigured",
            "configured": self.api_client is not None,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "has_api_key": bool(self.api_client and self.api_client.api_key)
        }

        if self.registrar == "porkbun":
            config["has_api_secret"] = bool(self.api_client and self.api_client.api_secret)

        if self.registrar == "namecheap" and isinstance(self.api_client, NamecheapAPIClient):
            config["username"] = self.api_client.username
            config["client_ip"] = self.api_client.client_ip

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
                price = self._normalize_price(result.get("price"))
                if price is None:
                    pricing = self.api_client.get_pricing(tld)
                    price = self._normalize_price(pricing.get("registration"))
                if price is not None and price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "currency": result.get("currency", "USD")
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

    @staticmethod
    def _normalize_price(raw_price: Any) -> Optional[float]:
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if isinstance(raw_price, str):
            cleaned = (
                raw_price.strip()
                .replace("$", "")
                .replace("€", "")
                .replace(",", "")
            )
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
