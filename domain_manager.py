"""
Domain management and API integration.

Supports automated domain purchasing for burner email rotation.
"""
import logging
import random
import string
import xml.etree.ElementTree as ET
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
        ...
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        ...
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        ...


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management
    https://porkbun.com/api/json/v3/documentation
    """
    
    BASE_URL = "https://porkbun.com/api/json/v3"
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        # Backward-compatible alias used by some maintenance scripts.
        self.secret_key = api_secret
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
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_BASE_URL = "https://api.sandbox.namecheap.com/xml.response"
    REQUIRED_CONTACT_FIELDS = (
        "FirstName",
        "LastName",
        "Address1",
        "City",
        "StateProvince",
        "PostalCode",
        "Country",
        "Phone",
        "EmailAddress",
    )

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: str,
        client_ip: str,
        contact_profile: Optional[Dict[str, str]] = None,
        sandbox: bool = False,
    ):
        super().__init__(api_key=api_key)
        self.api_user = api_user
        self.username = username
        self.client_ip = client_ip
        self.contact_profile = contact_profile or {}
        self.sandbox = sandbox
        self.base_url = self.SANDBOX_BASE_URL if sandbox else self.BASE_URL
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a Namecheap API request and parse XML response."""
        payload: Dict[str, Any] = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            payload.update(params)

        try:
            response = self.session.get(self.base_url, params=payload, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            status = root.attrib.get("Status", "").upper()
            errors = [
                error.text.strip()
                for error in self._iter_elements_with_suffix(root, "Error")
                if error.text and error.text.strip()
            ]
            return {
                "success": status == "OK" and not errors,
                "status": status or "ERROR",
                "errors": errors,
                "root": root,
            }
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return {
                "success": False,
                "status": "ERROR",
                "errors": [str(exc)],
                "root": None,
            }

    @staticmethod
    def _iter_elements_with_suffix(root: ET.Element, suffix: str):
        for element in root.iter():
            if element.tag.endswith(suffix):
                yield element

    @classmethod
    def _find_first_with_suffix(cls, root: Optional[ET.Element], suffix: str) -> Optional[ET.Element]:
        if root is None:
            return None
        for element in cls._iter_elements_with_suffix(root, suffix):
            return element
        return None

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check if a domain is available."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        root = result.get("root")

        if not result.get("success") or root is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "; ".join(result.get("errors", [])) or "Domain check failed",
            }

        domain_result = self._find_first_with_suffix(root, "DomainCheckResult")
        if domain_result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "Unexpected Namecheap response format",
            }

        available = str(domain_result.attrib.get("Available", "false")).lower() == "true"
        is_premium = str(domain_result.attrib.get("IsPremiumName", "false")).lower() == "true"

        return {
            "domain": domain,
            "available": available and not is_premium,
            "price": None,
            "currency": "USD",
            "premium": is_premium,
            "message": "; ".join(result.get("errors", [])),
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get registration pricing for a TLD."""
        tld = tld.lstrip(".")
        sample_domain = f"example.{tld}"
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductName": sample_domain,
            },
        )
        root = result.get("root")
        if not result.get("success") or root is None:
            return {}

        # Pick the first 1-year price if present.
        selected_price = None
        for price_entry in self._iter_elements_with_suffix(root, "Price"):
            duration = str(price_entry.attrib.get("Duration", ""))
            if duration in {"1", "1Y", "1y"}:
                selected_price = (
                    price_entry.attrib.get("YourPrice")
                    or price_entry.attrib.get("Price")
                    or price_entry.attrib.get("YourAdditonalCost")
                )
                break

        if selected_price is None:
            return {}

        return {
            "tld": tld,
            "registration": selected_price,
            "renewal": None,
            "transfer": None,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase a domain using Namecheap.

        Namecheap requires full contact details for registration. Provide these
        via `contact_profile` when constructing this client.
        """
        contact_params, missing = self._build_contact_params(self.contact_profile)
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": "Missing required Namecheap contact fields: " + ", ".join(missing),
                "order_id": None,
            }

        payload: Dict[str, Any] = {
            "DomainName": domain,
            "Years": years,
            "AddFreeWhoisguard": "yes",
            "WGEnabled": "yes",
        }
        payload.update(contact_params)

        result = self._make_request("namecheap.domains.create", payload)
        root = result.get("root")
        order_id = None
        if root is not None:
            order_elem = self._find_first_with_suffix(root, "OrderID")
            if order_elem is not None and order_elem.text:
                order_id = order_elem.text.strip()

        return {
            "success": bool(result.get("success")),
            "domain": domain,
            "message": "; ".join(result.get("errors", [])),
            "order_id": order_id,
        }

    @classmethod
    def _build_contact_params(cls, profile: Dict[str, str]):
        params: Dict[str, str] = {}
        missing: List[str] = []

        for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field in cls.REQUIRED_CONTACT_FIELDS:
                key = f"{role}{field}"
                value = str(profile.get(key, "")).strip()
                if not value:
                    missing.append(key)
                else:
                    params[key] = value

        return params, missing


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0, registrar: str = "porkbun"):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.registrar = registrar
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    def set_monthly_budget(self, monthly_budget: float):
        """Set monthly domain purchase budget."""
        if monthly_budget <= 0:
            raise ValueError("Monthly budget must be greater than zero")
        self.monthly_budget = monthly_budget

    def generate_domain_name(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Backward-compatible alias for random domain generation.
        """
        return self.generate_random_domain(tld=tld, length=length)

    @staticmethod
    def _parse_price(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = (
                value.replace("$", "")
                .replace("€", "")
                .replace(",", "")
                .strip()
            )
            if not normalized:
                return None
            try:
                return float(normalized)
            except ValueError:
                return None
        return None

    def configure(
        self,
        api_key: str = "",
        secret_key: str = "",
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Configure domain registrar client and budget.

        Supports:
        - Porkbun: api_key + secret_key
        - Namecheap: api_key + api_user + username + client_ip (+ optional contact_profile)
        """
        self.set_monthly_budget(float(monthly_budget))
        selected_registrar = registrar.strip().lower() if registrar else "porkbun"

        if selected_registrar == "porkbun":
            if not api_key or not secret_key:
                raise ValueError("Porkbun requires both api_key and secret_key")
            self.api_client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
            self.registrar = "porkbun"
        elif selected_registrar == "namecheap":
            api_user = (
                kwargs.get("api_user")
                or kwargs.get("namecheap_api_user")
                or kwargs.get("username")
                or kwargs.get("namecheap_username")
            )
            username = kwargs.get("username") or kwargs.get("namecheap_username") or api_user
            client_ip = kwargs.get("client_ip") or kwargs.get("namecheap_client_ip")
            contact_profile = kwargs.get("contact_profile")
            sandbox = bool(kwargs.get("sandbox", False))

            if not api_key or not api_user or not username or not client_ip:
                raise ValueError(
                    "Namecheap requires api_key, api_user, username, and client_ip"
                )

            self.api_client = NamecheapAPIClient(
                api_user=str(api_user),
                api_key=api_key,
                username=str(username),
                client_ip=str(client_ip),
                contact_profile=contact_profile,
                sandbox=sandbox,
            )
            self.registrar = "namecheap"
        else:
            raise ValueError(f"Unsupported registrar: {registrar}")

        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return non-sensitive domain configuration status."""
        return {
            "configured": self.api_client is not None,
            "registrar": self.registrar,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
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
                price = self._parse_price(result.get("price"))

                # Some registrars don't return price in search responses.
                if price is None:
                    pricing = self.api_client.get_pricing(tld)
                    price = self._parse_price(pricing.get("registration"))

                if price is None:
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
        
        normalized_price = self._parse_price(price)
        if normalized_price is None:
            logger.error("Invalid price provided for domain %s: %s", domain, price)
            return False

        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += normalized_price
            self.owned_domains.append({
                "domain": domain,
                "price": normalized_price,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${normalized_price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self, return_details: bool = False):
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            if return_details:
                return {"success": False, "error": "Could not find available cheap domain"}
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            if return_details:
                return {
                    "success": True,
                    "domain": self.active_domain,
                    "price": domain_info["price"],
                }
            return self.active_domain
        
        if return_details:
            return {"success": False, "error": "Domain purchase failed"}
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
