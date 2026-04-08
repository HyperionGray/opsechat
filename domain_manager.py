"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

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
    API docs: https://www.namecheap.com/support/api/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(self, api_key: str, username: str, client_ip: str = "127.0.0.1",
                 use_sandbox: bool = False):
        super().__init__(api_key, None)
        self.username = username
        self.client_ip = client_ip
        self.base_url = self.SANDBOX_URL if use_sandbox else self.BASE_URL
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict] = None) -> Optional[ET.Element]:
        query = {
            "ApiUser": self.username,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command
        }
        if params:
            query.update(params)

        try:
            response = self.session.get(self.base_url, params=query, timeout=30)
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as e:
            logger.error(f"Namecheap API request failed ({command}): {e}")
            return None

    @staticmethod
    def _is_success(root: ET.Element) -> bool:
        return root is not None and root.attrib.get("Status") == "OK"

    @staticmethod
    def _safe_float(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def search_domain(self, domain: str) -> Dict:
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not self._is_success(root):
            return {"domain": domain, "available": False, "price": None, "currency": "USD"}

        check_result = root.find(".//{*}DomainCheckResult")
        if check_result is None:
            return {"domain": domain, "available": False, "price": None, "currency": "USD"}

        available = str(check_result.attrib.get("Available", "")).lower() == "true"
        tld = domain.rsplit(".", 1)[-1] if "." in domain else "com"
        pricing = self.get_pricing(tld)

        return {
            "domain": domain,
            "available": available,
            "price": pricing.get("registration"),
            "currency": pricing.get("currency", "USD")
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        sld, tld = domain.split(".", 1) if "." in domain else (domain, "com")
        root = self._make_request(
            "namecheap.domains.create",
            {
                "DomainName": domain,
                "Years": years,
                "DomainName.SLD": sld,
                "DomainName.TLD": tld
            }
        )
        if not self._is_success(root):
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap purchase request failed"
            }

        domain_create = root.find(".//{*}DomainCreateResult")
        success = domain_create is not None and str(domain_create.attrib.get("Registered", "")).lower() == "true"
        return {
            "success": success,
            "domain": domain,
            "message": "" if success else "Domain registration was not confirmed",
            "order_id": domain_create.attrib.get("OrderID") if domain_create is not None else None
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        root = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "DOMAINS",
                "ActionName": "REGISTER",
                "ProductName": tld.upper()
            }
        )
        if not self._is_success(root):
            return {}

        product_price = root.find(".//{*}Product/{*}Price")
        if product_price is None:
            return {}

        return {
            "tld": tld,
            "registration": self._safe_float(product_price.attrib.get("Price")),
            "renewal": self._safe_float(product_price.attrib.get("RegularPrice")),
            "transfer": self._safe_float(product_price.attrib.get("YourPrice")),
            "currency": "USD"
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None,
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.default_registrar: Optional[str] = None
        self._config = {
            "monthly_budget": monthly_budget,
            "default_registrar": None,
            "registrars": {}
        }

        if api_client:
            self.add_api_client("default", api_client)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.api_clients = {"default": api_client}
        self.default_registrar = "default"

    def add_api_client(self, registrar: str, api_client: DomainAPIClient):
        """Add or replace a registrar API client."""
        self.api_clients[registrar] = api_client
        self.api_client = api_client
        if not self.default_registrar:
            self.default_registrar = registrar

    def set_default_registrar(self, registrar: str):
        """Set the default registrar used for purchases/search order."""
        if registrar not in self.api_clients:
            raise ValueError(f"Registrar '{registrar}' is not configured")
        self.default_registrar = registrar
        self._config["default_registrar"] = registrar

    def get_available_registrars(self) -> List[str]:
        """Return configured registrars."""
        return list(self.api_clients.keys())

    def _iter_clients(self, preferred_registrar: Optional[str] = None) -> List[tuple]:
        if not self.api_clients and self.api_client:
            self.api_clients = {"default": self.api_client}
            if not self.default_registrar:
                self.default_registrar = "default"

        if preferred_registrar:
            client = self.api_clients.get(preferred_registrar)
            return [(preferred_registrar, client)] if client else []

        items = list(self.api_clients.items())
        if self.default_registrar:
            items.sort(key=lambda item: item[0] != self.default_registrar)
        return items

    @staticmethod
    def _normalize_price(price: object) -> Optional[float]:
        if price is None:
            return None
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            cleaned = price.replace("$", "").replace("€", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"
    
    def find_cheap_available_domain(self, max_price: float = 5.0,
                                   max_attempts: int = 10,
                                   preferred_registrar: Optional[str] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self._iter_clients(preferred_registrar):
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            for registrar_name, api_client in self._iter_clients(preferred_registrar):
                result = api_client.search_domain(domain)

                if not result.get("available"):
                    continue

                price = self._normalize_price(result.get("price"))
                if price is None:
                    pricing = api_client.get_pricing(tld)
                    price = self._normalize_price(pricing.get("registration"))

                if price is not None and price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "registrar": registrar_name
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float,
                                         registrar: Optional[str] = None) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        clients = self._iter_clients(registrar)
        if not clients:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        selected_registrar, selected_client = clients[0]
        result = selected_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            now = datetime.now(timezone.utc)
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "registrar": selected_registrar,
                "purchased_at": now.isoformat(),
                "expires_at": (now + timedelta(days=365)).isoformat()
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self, preferred_registrar: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(
            preferred_registrar=preferred_registrar
        )
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"],
            registrar=domain_info.get("registrar")
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

    def configure(self, api_key: str, secret_key: Optional[str] = None,
                  monthly_budget: float = 50.0, registrar: str = "porkbun",
                  namecheap_username: Optional[str] = None,
                  namecheap_client_ip: str = "127.0.0.1") -> Dict:
        """
        Configure a registrar and budget at runtime.
        Supported registrar values: porkbun, namecheap.
        """
        self.monthly_budget = monthly_budget
        self._config["monthly_budget"] = monthly_budget

        if registrar == "porkbun":
            if not secret_key:
                raise ValueError("Porkbun requires api_key and secret_key")
            self.add_api_client("porkbun", PorkbunAPIClient(api_key, secret_key))
            self.set_default_registrar("porkbun")
            self._config["registrars"]["porkbun"] = {
                "configured": True,
                "api_key_suffix": api_key[-4:] if api_key else ""
            }
        elif registrar == "namecheap":
            if not namecheap_username:
                raise ValueError("Namecheap requires namecheap_username")
            self.add_api_client(
                "namecheap",
                NamecheapAPIClient(
                    api_key=api_key,
                    username=namecheap_username,
                    client_ip=namecheap_client_ip
                )
            )
            self.set_default_registrar("namecheap")
            self._config["registrars"]["namecheap"] = {
                "configured": True,
                "api_key_suffix": api_key[-4:] if api_key else "",
                "username": namecheap_username,
                "client_ip": namecheap_client_ip
            }
        else:
            raise ValueError(f"Unsupported registrar: {registrar}")

        return self.get_config()

    def get_config(self) -> Dict:
        """Get non-sensitive runtime configuration for UI and APIs."""
        return {
            "monthly_budget": self.monthly_budget,
            "default_registrar": self.default_registrar,
            "available_registrars": self.get_available_registrars(),
            "registrars": self._config.get("registrars", {})
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
