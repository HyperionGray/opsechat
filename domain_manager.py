"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import ipaddress
import logging
import os
import random
import string
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

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


def _strip_xml_namespace(tag_name: str) -> str:
    """Return XML tag name without namespace."""
    if "}" in tag_name:
        return tag_name.rsplit("}", 1)[1]
    return tag_name


def _parse_price(value: Any) -> Optional[float]:
    """Parse mixed price formats into a float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    sanitized = value.strip().replace("$", "").replace("€", "").replace(",", "")
    if not sanitized:
        return None
    try:
        return float(sanitized)
    except ValueError:
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
        availability = str(result.get("isAvailable", "")).lower()

        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and availability in {"true", "yes", "1"},
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
    Docs: https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        api_user: str,
        username: str,
        client_ip: str,
        contact_info: Optional[Dict[str, str]] = None
    ):
        super().__init__(api_key)
        self.api_user = api_user
        self.username = username
        self.client_ip = client_ip
        self.contact_info = contact_info or {}
        self.session = requests.Session()
        self._validate_client_ip(client_ip)

    @staticmethod
    def _validate_client_ip(client_ip: str):
        try:
            ipaddress.ip_address(client_ip)
        except ValueError as exc:
            raise ValueError(f"Invalid Namecheap client_ip: {client_ip}") from exc

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> ET.Element:
        query = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command
        }
        if params:
            query.update(params)

        url = f"{self.BASE_URL}?{urlencode(query)}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return ET.fromstring(response.text)

    def _collect_errors(self, xml_root: ET.Element) -> List[str]:
        errors: List[str] = []
        for node in xml_root.iter():
            if _strip_xml_namespace(node.tag) == "Error":
                errors.append((node.text or "").strip())
        return [err for err in errors if err]

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        try:
            root = self._make_request(
                "namecheap.domains.check",
                {"DomainList": domain}
            )
        except Exception as exc:
            logger.error(f"Namecheap domain check failed: {exc}")
            return {"domain": domain, "available": False, "error": str(exc)}

        errors = self._collect_errors(root)
        if errors:
            return {"domain": domain, "available": False, "error": "; ".join(errors)}

        for node in root.iter():
            if _strip_xml_namespace(node.tag) != "DomainCheckResult":
                continue
            available = str(node.attrib.get("Available", "false")).lower() == "true"
            return {
                "domain": node.attrib.get("Domain", domain),
                "available": available,
                "premium": str(node.attrib.get("IsPremiumName", "false")).lower() == "true",
                "price": None,
                "currency": "USD"
            }

        return {"domain": domain, "available": False, "error": "No DomainCheckResult returned"}

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain through Namecheap.
        Note: Namecheap requires full contact profile for registration.
        """
        required_fields = [
            "FirstName", "LastName", "Address1", "City", "StateProvince",
            "PostalCode", "Country", "Phone", "EmailAddress"
        ]
        missing = [field for field in required_fields if not self.contact_info.get(field)]
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": f"Missing Namecheap contact_info fields: {', '.join(missing)}"
            }

        params: Dict[str, Any] = {"DomainName": domain, "Years": years}
        for contact_type in ["Registrant", "Tech", "Admin", "AuxBilling"]:
            for field in required_fields:
                params[f"{contact_type}{field}"] = self.contact_info[field]

        try:
            root = self._make_request("namecheap.domains.create", params)
        except Exception as exc:
            logger.error(f"Namecheap purchase failed: {exc}")
            return {"success": False, "domain": domain, "message": str(exc)}

        errors = self._collect_errors(root)
        if errors:
            return {"success": False, "domain": domain, "message": "; ".join(errors)}

        for node in root.iter():
            if _strip_xml_namespace(node.tag) != "DomainCreateResult":
                continue
            registered = str(node.attrib.get("Registered", "false")).lower() == "true"
            return {
                "success": registered,
                "domain": node.attrib.get("Domain", domain),
                "message": "SUCCESS" if registered else "Domain was not registered"
            }

        return {"success": False, "domain": domain, "message": "No DomainCreateResult returned"}

    def get_pricing(self, tld: str) -> Dict:
        """
        Get Namecheap registration pricing for a TLD.
        """
        normalized_tld = tld.lstrip(".")
        try:
            root = self._make_request(
                "namecheap.users.getPricing",
                {
                    "ProductType": "DOMAIN",
                    "ProductCategory": "register",
                    "ActionName": "register"
                }
            )
        except Exception as exc:
            logger.error(f"Namecheap pricing request failed: {exc}")
            return {}

        errors = self._collect_errors(root)
        if errors:
            return {}

        for node in root.iter():
            if _strip_xml_namespace(node.tag) != "Product":
                continue
            if node.attrib.get("Name", "").lower() != normalized_tld.lower():
                continue

            registration = None
            for child in node.iter():
                if _strip_xml_namespace(child.tag) != "Price":
                    continue
                if child.attrib.get("Duration") == "1":
                    registration = child.attrib.get("YourPrice")
                    break

            return {
                "tld": normalized_tld,
                "registration": registration,
                "renewal": None,
                "transfer": None,
                "currency": "USD"
            }

        return {}


def create_domain_api_client(provider: str, **config: Any) -> DomainAPIClient:
    """Factory for domain registrar clients."""
    normalized = provider.strip().lower()
    if normalized == "porkbun":
        api_key = config.get("api_key")
        api_secret = config.get("api_secret")
        if not api_key or not api_secret:
            raise ValueError("Porkbun requires api_key and api_secret")
        return PorkbunAPIClient(api_key=api_key, api_secret=api_secret)

    if normalized == "namecheap":
        api_key = config.get("api_key")
        api_user = config.get("api_user")
        username = config.get("username")
        client_ip = config.get("client_ip")
        if not api_key or not api_user or not username or not client_ip:
            raise ValueError("Namecheap requires api_key, api_user, username, and client_ip")
        return NamecheapAPIClient(
            api_key=api_key,
            api_user=api_user,
            username=username,
            client_ip=client_ip,
            contact_info=config.get("contact_info")
        )

    raise ValueError(f"Unsupported provider: {provider}")


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.provider = "porkbun"
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self._api_config: Dict[str, Any] = {}
    
    def set_api_client(self, api_client: DomainAPIClient, provider: Optional[str] = None):
        """Set the domain API client"""
        self.api_client = api_client
        if provider:
            self.provider = provider

    def configure(self, **config: Any):
        """
        Configure provider, credentials, and budget.
        Accepts either api_secret or secret_key for compatibility.
        """
        provider = config.get("provider", self.provider or "porkbun")
        monthly_budget = config.get("monthly_budget", self.monthly_budget)
        self.monthly_budget = float(monthly_budget)

        api_secret = config.get("api_secret", config.get("secret_key"))
        factory_config = dict(config)
        if api_secret and "api_secret" not in factory_config:
            factory_config["api_secret"] = api_secret

        if provider == "namecheap":
            factory_config.setdefault("api_user", factory_config.get("username", ""))
            factory_config.setdefault("username", factory_config.get("api_user", ""))

        client = create_domain_api_client(provider, **factory_config)
        self.set_api_client(client, provider=provider)

        safe_config = dict(factory_config)
        for key in ["api_key", "api_secret", "secret_key"]:
            if safe_config.get(key):
                safe_config[key] = "***"
        self._api_config = safe_config

    def get_config(self) -> Dict[str, Any]:
        """Return non-sensitive current domain rotation configuration."""
        return {
            "provider": self.provider,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "api_client_configured": self.api_client is not None
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
                price = _parse_price(result.get("price"))
                if price is None:
                    pricing = self.api_client.get_pricing(tld)
                    price = _parse_price(pricing.get("registration"))
                if price is None:
                    price = 999.0
                
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
        parsed_price = _parse_price(price)
        if parsed_price is None:
            logger.error(f"Invalid price for purchase: {price}")
            return False

        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${parsed_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            now = datetime.now()
            self.current_spending += parsed_price
            self.owned_domains.append({
                "domain": domain,
                "price": parsed_price,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365),
                "provider": self.provider
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
