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


def _parse_price(value: object) -> Optional[float]:
    """Best-effort parse for API price values."""
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
            return None
    return None


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

    PROD_BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_BASE_URL = "https://api.sandbox.namecheap.com/xml.response"
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
        api_key: str,
        username: str,
        client_ip: str,
        api_user: Optional[str] = None,
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key)
        self.username = username
        self.api_user = api_user or username
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.base_url = self.SANDBOX_BASE_URL if sandbox else self.PROD_BASE_URL
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    @staticmethod
    def _tag_endswith(tag: str, suffix: str) -> bool:
        return tag == suffix or tag.endswith(f"}}{suffix}")

    def _extract_error(self, root: ET.Element) -> str:
        errors = []
        for elem in root.iter():
            if self._tag_endswith(elem.tag, "Error") and (elem.text or "").strip():
                errors.append(elem.text.strip())
        return "; ".join(errors) if errors else "Unknown Namecheap API error"

    def _make_request(self, command: str, params: Optional[Dict] = None) -> Dict:
        payload = {
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
            if root.attrib.get("Status") != "OK":
                return {
                    "status": "ERROR",
                    "message": self._extract_error(root),
                    "xml_root": root,
                }
            return {"status": "SUCCESS", "xml_root": root}
        except Exception as e:
            logger.error("Namecheap API request failed: %s", e)
            return {"status": "ERROR", "message": str(e)}

    def search_domain(self, domain: str) -> Dict:
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        root = result.get("xml_root")
        available = False

        if root is not None:
            for elem in root.iter():
                if self._tag_endswith(elem.tag, "DomainCheckResult"):
                    available = elem.attrib.get("Available", "false").lower() == "true"
                    break

        price = None
        if available:
            tld = domain.rsplit(".", 1)[-1]
            price = self.get_pricing(tld).get("registration")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "registrar": "namecheap",
            "message": result.get("message", ""),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        missing = [
            field for field in self.REQUIRED_CONTACT_FIELDS
            if not self.contact_profile.get(field)
        ]
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Missing Namecheap contact profile fields: "
                    + ", ".join(sorted(missing))
                ),
            }

        params = {
            "DomainName": domain,
            "Years": years,
        }

        for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field in self.REQUIRED_CONTACT_FIELDS:
                params[f"{role}{field}"] = self.contact_profile[field]

        optional_org = self.contact_profile.get("OrganizationName")
        if optional_org:
            for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
                params[f"{role}OrganizationName"] = optional_org

        result = self._make_request("namecheap.domains.create", params)
        if result.get("status") != "SUCCESS":
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Domain purchase failed"),
            }

        root = result.get("xml_root")
        if root is None:
            return {"success": False, "domain": domain, "message": "Invalid API response"}

        for elem in root.iter():
            if self._tag_endswith(elem.tag, "DomainCreateResult"):
                registered = elem.attrib.get("Registered", "false").lower() == "true"
                return {
                    "success": registered,
                    "domain": domain,
                    "message": "Domain purchased successfully" if registered else "Domain purchase failed",
                    "order_id": elem.attrib.get("OrderID"),
                    "transaction_id": elem.attrib.get("TransactionID"),
                }

        return {"success": False, "domain": domain, "message": "Missing purchase result in API response"}

    def get_pricing(self, tld: str) -> Dict:
        normalized_tld = tld.lstrip(".").lower()
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "register",
                "ProductName": normalized_tld,
            },
        )

        root = result.get("xml_root")
        if root is None:
            return {}

        registration_price = None
        for elem in root.iter():
            if self._tag_endswith(elem.tag, "Price"):
                registration_price = (
                    _parse_price(elem.attrib.get("YourPrice"))
                    or _parse_price(elem.attrib.get("Price"))
                    or _parse_price(elem.attrib.get("RegularPrice"))
                    or _parse_price(elem.text)
                )
                if registration_price is not None:
                    break

        return {
            "tld": normalized_tld,
            "registration": registration_price,
            "currency": "USD",
        }

    def list_domains(self) -> List[str]:
        result = self._make_request("namecheap.domains.getList")
        root = result.get("xml_root")
        if root is None:
            return []

        domains: List[str] = []
        for elem in root.iter():
            if self._tag_endswith(elem.tag, "Domain"):
                domain_name = elem.attrib.get("Name")
                if domain_name:
                    domains.append(domain_name)
        return domains


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
        api_clients: Optional[Dict[str, DomainAPIClient]] = None,
        preferred_registrar: Optional[str] = None,
    ):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.preferred_registrar = preferred_registrar.lower() if preferred_registrar else None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_clients:
            for registrar, client in api_clients.items():
                self.add_api_client(registrar, client)
        if api_client:
            inferred = self._infer_registrar_name(api_client)
            self.add_api_client(inferred, api_client)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

        inferred = self._infer_registrar_name(api_client)
        self.add_api_client(inferred, api_client)

    @staticmethod
    def _infer_registrar_name(api_client: DomainAPIClient) -> str:
        if isinstance(api_client, PorkbunAPIClient):
            return "porkbun"
        if isinstance(api_client, NamecheapAPIClient):
            return "namecheap"

        name = api_client.__class__.__name__.lower()
        return name.replace("apiclient", "") or "default"

    def add_api_client(self, registrar: str, api_client: DomainAPIClient):
        """Register an API client for a registrar."""
        key = registrar.lower()
        self.api_clients[key] = api_client
        if not self.api_client:
            self.api_client = api_client
        if not self.preferred_registrar:
            self.preferred_registrar = key

    def set_preferred_registrar(self, registrar: Optional[str]):
        """Set preferred registrar used first during search/purchase."""
        if registrar:
            key = registrar.lower()
            if key not in self.api_clients:
                raise ValueError(f"Registrar '{registrar}' is not configured")
            self.preferred_registrar = key
        else:
            self.preferred_registrar = None

    def get_available_registrars(self) -> List[str]:
        """Get configured registrar names."""
        return sorted(self.api_clients.keys())

    def _iter_clients(self, registrar: Optional[str] = None) -> List[tuple]:
        if registrar:
            key = registrar.lower()
            client = self.api_clients.get(key)
            if client:
                return [(key, client)]
            return []

        ordered_clients: List[tuple] = []
        seen = set()

        if self.preferred_registrar and self.preferred_registrar in self.api_clients:
            ordered_clients.append(
                (self.preferred_registrar, self.api_clients[self.preferred_registrar])
            )
            seen.add(self.preferred_registrar)

        for key, client in self.api_clients.items():
            if key not in seen:
                ordered_clients.append((key, client))
                seen.add(key)

        if not ordered_clients and self.api_client:
            inferred = self._infer_registrar_name(self.api_client)
            ordered_clients.append((inferred, self.api_client))

        return ordered_clients
    
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
        registrar: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        clients = self._iter_clients(registrar)
        if not clients:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            for registrar_name, client in clients:
                result = client.search_domain(domain)
                if not result.get("available"):
                    continue

                price = _parse_price(result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
                    price = _parse_price(pricing.get("registration"))

                if price is None:
                    logger.debug(
                        "Registrar %s had no price for domain %s",
                        registrar_name,
                        domain,
                    )
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "registrar": registrar_name,
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
        clients = self._iter_clients(registrar)
        if not clients:
            logger.error("No API client configured")
            return False
        selected_registrar, selected_client = clients[0]
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = selected_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "registrar": selected_registrar,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(
                "Successfully purchased domain %s via %s for $%s",
                domain,
                selected_registrar,
                price,
            )
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self, registrar: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(registrar=registrar)
        
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
            "domains_owned": len(self.owned_domains),
            "preferred_registrar": self.preferred_registrar,
            "available_registrars": self.get_available_registrars(),
        }

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        registrar: str = "porkbun",
        **kwargs,
    ) -> Dict:
        """Configure and register an API client (compatibility helper)."""
        key = registrar.lower()

        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        if key == "porkbun":
            if not secret_key:
                return {"success": False, "message": "Porkbun requires secret_key"}
            client = PorkbunAPIClient(api_key, secret_key)
        elif key == "namecheap":
            username = kwargs.get("username") or kwargs.get("api_user")
            client_ip = kwargs.get("client_ip")
            if not username or not client_ip:
                return {
                    "success": False,
                    "message": "Namecheap requires username and client_ip",
                }
            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                api_user=kwargs.get("api_user"),
                client_ip=client_ip,
                sandbox=bool(kwargs.get("sandbox", False)),
                contact_profile=kwargs.get("contact_profile"),
            )
        else:
            return {"success": False, "message": f"Unsupported registrar: {registrar}"}

        self.add_api_client(key, client)
        self.preferred_registrar = key
        return {"success": True, "registrar": key}

    def get_config(self) -> Dict:
        """Return non-secret runtime configuration."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "preferred_registrar": self.preferred_registrar,
            "configured_registrars": self.get_available_registrars(),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
