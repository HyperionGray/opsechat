"""
Domain management and API integration.
Supports automated domain purchasing for burner email rotation.
"""
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
import random
import string
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
        raise NotImplementedError("Subclasses must implement search_domain()")
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("Subclasses must implement purchase_domain()")
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError("Subclasses must implement get_pricing()")


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
    REQUIRED_CONTACT_FIELDS = [
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

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: str,
        client_ip: str,
        use_sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key)
        self.api_user = api_user
        self.username = username
        self.client_ip = client_ip
        self.use_sandbox = use_sandbox
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.split("}", 1)[-1]

    def _find_first(self, root: ET.Element, tag_name: str) -> Optional[ET.Element]:
        for element in root.iter():
            if self._local_name(element.tag) == tag_name:
                return element
        return None

    def _find_all(self, root: ET.Element, tag_name: str) -> List[ET.Element]:
        return [el for el in root.iter() if self._local_name(el.tag) == tag_name]

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return None
        try:
            return float(value.replace("$", "").strip())
        except ValueError:
            return None

    def _extract_errors(self, root: ET.Element) -> List[str]:
        errors: List[str] = []
        for err in self._find_all(root, "Error"):
            if err.text:
                errors.append(err.text.strip())
        return errors

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self.SANDBOX_URL if self.use_sandbox else self.BASE_URL
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
            root = ET.fromstring(response.text)
            errors = self._extract_errors(root)
            if errors:
                return {"status": "ERROR", "errors": errors, "root": root}
            return {"status": "SUCCESS", "root": root}
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return {"status": "ERROR", "errors": [str(exc)]}

    def search_domain(self, domain: str) -> Dict:
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if result.get("status") != "SUCCESS":
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "; ".join(result.get("errors", ["Unknown Namecheap error"])),
            }

        root = result["root"]
        check = self._find_first(root, "DomainCheckResult")
        if check is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "Missing DomainCheckResult in Namecheap response",
            }

        available = str(check.attrib.get("Available", "")).lower() == "true"
        premium_price = check.attrib.get("PremiumRegistrationPrice")
        return {
            "domain": domain,
            "available": available,
            "price": self._to_float(premium_price),
            "currency": "USD",
            "premium": str(check.attrib.get("IsPremiumName", "")).lower() == "true",
        }

    def _get_price_for_action(self, tld: str, action: str) -> Optional[float]:
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": action,
                "ProductName": tld.lower().lstrip("."),
            },
        )
        if result.get("status") != "SUCCESS":
            return None

        root = result["root"]
        product_name = tld.lower().lstrip(".")
        for product in self._find_all(root, "Product"):
            if product.attrib.get("Name", "").lower() != product_name:
                continue
            for price in product:
                if self._local_name(price.tag) != "Price":
                    continue
                if price.attrib.get("Duration") == "1":
                    for candidate in ("YourPrice", "Price", "YourAdditionalCost"):
                        parsed = self._to_float(price.attrib.get(candidate))
                        if parsed is not None:
                            return parsed
        return None

    def get_pricing(self, tld: str = "com") -> Dict:
        return {
            "tld": tld.lower().lstrip("."),
            "registration": self._get_price_for_action(tld, "register"),
            "renewal": self._get_price_for_action(tld, "renew"),
            "transfer": self._get_price_for_action(tld, "transfer"),
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        missing = [f for f in self.REQUIRED_CONTACT_FIELDS if not self.contact_profile.get(f)]
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Missing Namecheap contact profile fields: "
                    + ", ".join(missing)
                ),
                "order_id": None,
            }

        params: Dict[str, Any] = {
            "DomainName": domain,
            "Years": max(1, int(years)),
        }
        for contact_type in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field in self.REQUIRED_CONTACT_FIELDS:
                params[f"{contact_type}{field}"] = self.contact_profile[field]

        result = self._make_request("namecheap.domains.create", params)
        if result.get("status") != "SUCCESS":
            return {
                "success": False,
                "domain": domain,
                "message": "; ".join(result.get("errors", ["Namecheap purchase failed"])),
                "order_id": None,
            }

        root = result["root"]
        create_result = self._find_first(root, "DomainCreateResult")
        order_details = self._find_first(root, "OrderDetails")
        order_id = order_details.attrib.get("OrderID") if order_details is not None else None
        purchase_ok = (
            create_result is not None
            and str(create_result.attrib.get("Registered", "")).lower() == "true"
        )
        return {
            "success": purchase_ok,
            "domain": domain,
            "message": "Success" if purchase_ok else "Namecheap returned an unsuccessful purchase result",
            "order_id": order_id,
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
                price = result.get("price", 999)
                
                if isinstance(price, str):
                    # Remove currency symbols
                    price = float(price.replace("$", "").replace("€", ""))
                
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
