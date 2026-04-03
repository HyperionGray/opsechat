"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _coerce_price(value: object, default: float = 999.0) -> float:
    """Parse mixed price formats into a float for budget checks."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.]+", "", value)
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
    Namecheap API client for domain management.
    API docs: https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        default_contacts: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key=api_key, api_secret=None)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.default_contacts = default_contacts or {}
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict] = None) -> Dict:
        """Make Namecheap XML API request and parse response metadata."""
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
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            return {
                "status": root.attrib.get("Status", "ERROR"),
                "errors": [err.text or "" for err in root.findall(".//Errors/Error")],
                "root": root,
            }
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return {"status": "ERROR", "errors": [str(e)], "root": None}

    def _extract_tld_price(self, root: Optional[ET.Element], tld: str) -> Optional[str]:
        """Extract first-year price for a TLD from pricing response XML."""
        if root is None:
            return None
        normalized_tld = tld.lower().lstrip(".")
        for product in root.findall(".//Product"):
            if product.attrib.get("Name", "").lower() != normalized_tld:
                continue
            for price in product.findall(".//Price"):
                if price.attrib.get("Duration") == "1":
                    return price.attrib.get("YourPrice")
        return None

    def _get_action_price(self, tld: str, action_name: str) -> Optional[str]:
        """Get a TLD price for one Namecheap pricing action."""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "DOMAINS",
                "ActionName": action_name,
            },
        )
        if result.get("status") != "OK":
            return None
        return self._extract_tld_price(result.get("root"), tld)

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available on Namecheap."""
        result = self._make_request(
            "namecheap.domains.check",
            {"DomainList": domain},
        )
        root = result.get("root")
        domain_result = root.find(".//DomainCheckResult") if root is not None else None
        available = False
        if domain_result is not None:
            available = domain_result.attrib.get("Available", "false").lower() == "true"

        price = None
        tld = domain.rsplit(".", 1)[-1]
        if available:
            premium_price = (
                domain_result.attrib.get("PremiumRegistrationPrice")
                if domain_result is not None
                else None
            )
            if premium_price and _coerce_price(premium_price, default=0.0) > 0.0:
                price = premium_price
            else:
                pricing = self.get_pricing(tld)
                price = pricing.get("registration")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "message": "; ".join(result.get("errors", [])),
            "registrar": "namecheap",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain via Namecheap.
        Requires contact details in default_contacts.
        """
        required_fields = {
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
        missing_fields = sorted(required_fields - set(self.default_contacts.keys()))
        if missing_fields:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Namecheap purchase requires contact details in default_contacts. "
                    f"Missing fields: {', '.join(missing_fields)}"
                ),
            }

        payload = {
            "DomainName": domain,
            "Years": years,
            "AddFreeWhoisguard": "yes",
            "WGEnabled": "yes",
        }
        for prefix in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field in required_fields:
                payload[f"{prefix}{field}"] = self.default_contacts[field]

        result = self._make_request("namecheap.domains.create", payload)
        root = result.get("root")
        create_result = root.find(".//DomainCreateResult") if root is not None else None
        success = result.get("status") == "OK" and create_result is not None
        return {
            "success": success,
            "domain": domain,
            "message": "; ".join(result.get("errors", [])),
            "order_id": create_result.attrib.get("OrderID") if create_result is not None else None,
        }

    def get_pricing(self, tld: str) -> Dict:
        """Get registration, renewal, and transfer prices for a TLD."""
        registration = self._get_action_price(tld, "REGISTER")
        renewal = self._get_action_price(tld, "RENEW")
        transfer = self._get_action_price(tld, "TRANSFER")
        if not any((registration, renewal, transfer)):
            return {}
        return {
            "tld": tld.lstrip("."),
            "registration": registration,
            "renewal": renewal,
            "transfer": transfer,
            "currency": "USD",
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
                price = _coerce_price(result.get("price", 999), default=999.0)
                
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
