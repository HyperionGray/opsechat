"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
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
    Namecheap API client for domain management
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        api_username: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        default_contact: Optional[Dict] = None,
    ):
        super().__init__(api_key, None)
        self.api_username = api_username
        self.username = username or api_username
        self.client_ip = client_ip
        self.default_contact = default_contact or {}
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict] = None) -> Dict:
        """Make Namecheap API request and parse XML response"""
        query = {
            "ApiUser": self.api_username,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            query.update(params)

        try:
            response = self.session.get(self.base_url, params=query, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            errors = [node.text.strip() for node in root.findall(".//Errors/Error") if node.text]
            return {
                "success": root.attrib.get("Status") == "OK" and not errors,
                "errors": errors,
                "root": root,
            }
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return {"success": False, "errors": [str(e)], "root": None}

    @staticmethod
    def _parse_price(value) -> Optional[float]:
        """Normalize numeric price values from API payloads"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace("$", "").replace(",", "").strip())
        except (TypeError, ValueError):
            return None

    def _build_contact_fields(self) -> Optional[Dict]:
        """Build required contact fields for namecheap.domains.create"""
        required = [
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
        missing = [field for field in required if not self.default_contact.get(field)]
        if missing:
            logger.error(
                "Namecheap purchase requires contact details; missing fields: %s",
                ", ".join(missing),
            )
            return None

        fields = {}
        for prefix in ["Registrant", "Tech", "Admin", "AuxBilling"]:
            for key in required:
                fields[f"{prefix}{key}"] = self.default_contact[key]
        return fields

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available"""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not result["success"] or result["root"] is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "; ".join(result["errors"]) if result["errors"] else "API request failed",
            }

        node = result["root"].find(".//DomainCheckResult")
        if node is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "Malformed Namecheap response",
            }

        available = node.attrib.get("Available", "").lower() == "true"
        price = self._parse_price(node.attrib.get("PremiumRegistrationPrice"))

        # Non-premium domains often omit a price in check results; estimate via pricing API.
        if available and price is None and "." in domain:
            tld = domain.split(".", 1)[1]
            pricing = self.get_pricing(tld)
            price = self._parse_price(pricing.get("registration"))

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain (requires Namecheap contact profile fields)"""
        contact_fields = self._build_contact_fields()
        if contact_fields is None:
            return {
                "success": False,
                "domain": domain,
                "message": "Missing required Namecheap contact details",
                "order_id": None,
            }

        payload = {"DomainName": domain, "Years": years}
        payload.update(contact_fields)
        result = self._make_request("namecheap.domains.create", payload)

        if not result["success"] or result["root"] is None:
            return {
                "success": False,
                "domain": domain,
                "message": "; ".join(result["errors"]) if result["errors"] else "Purchase failed",
                "order_id": None,
            }

        order_node = result["root"].find(".//OrderID")
        return {
            "success": True,
            "domain": domain,
            "message": "SUCCESS",
            "order_id": order_node.text if order_node is not None else None,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get registration pricing for a TLD"""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductName": tld.lower(),
            },
        )
        if not result["success"] or result["root"] is None:
            return {}

        target = tld.lower()
        product_node = None
        for product in result["root"].findall(".//Product"):
            if product.attrib.get("Name", "").lower() == target:
                product_node = product
                break

        if product_node is None:
            return {}

        return {
            "tld": tld,
            "registration": product_node.attrib.get("YourPrice") or product_node.attrib.get("Price"),
            "renewal": product_node.attrib.get("YourRenewPrice") or product_node.attrib.get("RenewPrice"),
            "transfer": product_node.attrib.get("YourTransferPrice") or product_node.attrib.get("TransferPrice"),
            "currency": product_node.attrib.get("Currency", "USD"),
        }

    def list_domains(self) -> List[str]:
        """List owned domains"""
        result = self._make_request("namecheap.domains.getList", {"PageSize": 100})
        if not result["success"] or not result["root"]:
            return []
        return [d.attrib.get("Name") for d in result["root"].findall(".//Domain") if d.attrib.get("Name")]


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_registrar: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        if api_client:
            # Backward-compatible default registrar if only one client is provided.
            self.add_api_client("default", api_client, make_active=True)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set single domain API client (backward-compatible helper)"""
        self.api_client = api_client
        self.add_api_client("default", api_client, make_active=True)

    def add_api_client(self, registrar: str, api_client: DomainAPIClient, make_active: bool = False):
        """Register an API client for a registrar name"""
        key = registrar.strip().lower()
        self.api_clients[key] = api_client
        if self.api_client is None:
            self.api_client = api_client
        if make_active or self.active_registrar is None:
            self.active_registrar = key

    def set_active_registrar(self, registrar: str):
        """Set default registrar used for purchase attempts"""
        key = registrar.strip().lower()
        if key not in self.api_clients:
            raise ValueError(f"Registrar not configured: {registrar}")
        self.active_registrar = key

    def get_available_registrars(self) -> List[str]:
        """Return configured registrar names"""
        return list(self.api_clients.keys())

    @staticmethod
    def _normalize_price(price_value) -> Optional[float]:
        """Normalize API price values into float"""
        if price_value is None:
            return None
        if isinstance(price_value, (int, float)):
            return float(price_value)
        if isinstance(price_value, str):
            try:
                return float(price_value.replace("$", "").replace("€", "").replace(",", "").strip())
            except ValueError:
                return None
        return None

    def _get_registrar_order(self, registrar_preference: Optional[str] = None) -> List[str]:
        """Get registrar search/purchase order honoring explicit preference"""
        order: List[str] = []
        if registrar_preference:
            preferred = registrar_preference.strip().lower()
            if preferred in self.api_clients:
                order.append(preferred)
        if self.active_registrar and self.active_registrar in self.api_clients and self.active_registrar not in order:
            order.append(self.active_registrar)
        for key in self.api_clients:
            if key not in order:
                order.append(key)
        if not order and self.api_client:
            # Legacy mode where only self.api_client is set
            self.add_api_client("default", self.api_client, make_active=True)
            order.append("default")
        return order
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"
    
    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        registrar_preference: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_clients and self.api_client:
            self.add_api_client("default", self.api_client, make_active=True)
        if not self.api_clients:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        registrar_order = self._get_registrar_order(registrar_preference)
        if not registrar_order:
            logger.error("No registrar clients configured")
            return None
        
        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for registrar in registrar_order:
                result = self.api_clients[registrar].search_domain(domain)

                if result.get("available"):
                    price = self._normalize_price(result.get("price"))
                    if price is None:
                        continue

                    if price <= max_price:
                        return {
                            "domain": result.get("domain", domain),
                            "price": price,
                            "tld": tld,
                            "registrar": registrar,
                        }
        
        return None
    
    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        registrar: Optional[str] = None,
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_clients and self.api_client:
            self.add_api_client("default", self.api_client, make_active=True)
        if not self.api_clients:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        registrar_order = self._get_registrar_order(registrar)
        if registrar and registrar.strip().lower() not in self.api_clients:
            logger.error(f"Registrar not configured: {registrar}")
            return False

        if not registrar_order:
            logger.error("No registrar available for purchase")
            return False

        # Attempt purchase, optionally with fallback across configured registrars
        result = None
        purchased_with = None
        for reg in registrar_order:
            attempt = self.api_clients[reg].purchase_domain(domain, years=1)
            if attempt.get("success"):
                result = attempt
                purchased_with = reg
                break
            # If caller explicitly chose a registrar, don't fail over silently.
            if registrar:
                result = attempt
                break
            result = attempt
        
        if result and result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "registrar": purchased_with or self.active_registrar or "default",
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            if purchased_with:
                self.active_registrar = purchased_with
            
            logger.info(
                f"Successfully purchased domain: {domain} for ${price} via {purchased_with or 'unknown'}"
            )
            return True
        else:
            error_msg = result.get("message") if isinstance(result, dict) else "unknown error"
            logger.error(f"Failed to purchase domain: {error_msg}")
            return False
    
    def rotate_domain(self, registrar_preference: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(registrar_preference=registrar_preference)
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"],
            registrar=domain_info.get("registrar"),
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

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        **kwargs,
    ) -> Dict:
        """
        Configure and register an API client for a registrar.
        This keeps compatibility with existing route code expecting configure().
        """
        self.monthly_budget = monthly_budget
        reg = registrar.strip().lower()

        if reg == "porkbun":
            if not api_key or not secret_key:
                raise ValueError("Porkbun requires api_key and secret_key")
            client = PorkbunAPIClient(api_key, secret_key)
        elif reg == "namecheap":
            api_username = kwargs.get("api_username") or kwargs.get("username") or kwargs.get("api_user")
            if not api_key or not api_username:
                raise ValueError("Namecheap requires api_key and api_username")
            client = NamecheapAPIClient(
                api_key=api_key,
                api_username=api_username,
                username=kwargs.get("username"),
                client_ip=kwargs.get("client_ip", "127.0.0.1"),
                sandbox=kwargs.get("sandbox", False),
                default_contact=kwargs.get("default_contact"),
            )
        else:
            raise ValueError(f"Unsupported registrar: {registrar}")

        self.add_api_client(reg, client, make_active=True)
        return {
            "success": True,
            "active_registrar": self.active_registrar,
            "configured_registrars": self.get_available_registrars(),
        }

    def get_config(self) -> Dict:
        """Return domain manager configuration summary for UI/routes"""
        return {
            "configured_registrars": self.get_available_registrars(),
            "active_registrar": self.active_registrar,
            "active_domain": self.active_domain,
            "budget_status": self.get_budget_status(),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
