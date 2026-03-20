"""
Domain management and API integration.

Supports automated domain purchasing for burner email rotation across
multiple registrar providers.
"""
import logging
import random
import string
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def _coerce_price(raw_price: Any) -> Optional[float]:
    """Convert common price formats to float."""
    if raw_price is None:
        return None

    if isinstance(raw_price, (int, float)):
        return float(raw_price)

    if not isinstance(raw_price, str):
        return None

    cleaned = (
        raw_price.strip()
        .replace("$", "")
        .replace("€", "")
        .replace("USD", "")
        .replace("usd", "")
        .replace(",", "")
    )

    try:
        return float(cleaned)
    except ValueError:
        return None


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    name = "generic"

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

    def list_domains(self) -> List[str]:
        """List owned domains for this provider"""
        return []


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management
    https://porkbun.com/api/json/v3/documentation
    """
    name = "porkbun"

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
    https://www.namecheap.com/support/api/intro/
    """

    name = "namecheap"
    PRODUCTION_BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_BASE_URL = "https://api.sandbox.namecheap.com/xml.response"
    REQUIRED_CONTACT_FIELDS = [
        "first_name",
        "last_name",
        "address1",
        "city",
        "state_province",
        "postal_code",
        "country",
        "phone",
        "email_address",
    ]

    def __init__(
        self,
        api_user: str,
        api_key: str,
        client_ip: str,
        username: Optional[str] = None,
        use_sandbox: bool = False,
        default_contact: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key=api_key)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.use_sandbox = use_sandbox
        self.base_url = self.SANDBOX_BASE_URL if use_sandbox else self.PRODUCTION_BASE_URL
        self.default_contact = default_contact or {}
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Send request and parse Namecheap XML response."""
        query = {
            "ApiUser": self.api_user,
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

            if root.attrib.get("Status") != "OK":
                errors = [node.text for node in root.findall(".//{*}Error") if node.text]
                message = "; ".join(errors) if errors else "Unknown Namecheap API error"
                return {"status": "ERROR", "message": message}

            return {"status": "SUCCESS", "xml": root}
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return {"status": "ERROR", "message": str(exc)}

    def _build_contact_params(self) -> Optional[Dict[str, str]]:
        """
        Build required contact payload for domain purchase.
        Namecheap requires all roles (Registrant/Admin/Tech/AuxBilling).
        """
        missing = [key for key in self.REQUIRED_CONTACT_FIELDS if not self.default_contact.get(key)]
        if missing:
            logger.warning(
                "Namecheap contact profile incomplete. Missing fields: %s",
                ", ".join(missing),
            )
            return None

        mapping = {
            "FirstName": self.default_contact["first_name"],
            "LastName": self.default_contact["last_name"],
            "Address1": self.default_contact["address1"],
            "City": self.default_contact["city"],
            "StateProvince": self.default_contact["state_province"],
            "PostalCode": self.default_contact["postal_code"],
            "Country": self.default_contact["country"],
            "Phone": self.default_contact["phone"],
            "EmailAddress": self.default_contact["email_address"],
        }
        organization = self.default_contact.get("organization_name", "")

        params: Dict[str, str] = {}
        for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for field, value in mapping.items():
                params[f"{role}{field}"] = value
            params[f"{role}OrganizationName"] = organization

        return params

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if result.get("status") != "SUCCESS":
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "registrar": self.name,
                "error": result.get("message", "API error"),
            }

        check_node = result["xml"].find(".//{*}DomainCheckResult")
        available = (
            check_node is not None
            and check_node.attrib.get("Available", "false").lower() == "true"
        )
        price = None
        if available and "." in domain:
            tld = domain.rsplit(".", 1)[1]
            pricing = self.get_pricing(tld)
            price = pricing.get("registration")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "registrar": self.name,
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain via Namecheap API."""
        contact_params = self._build_contact_params()
        if not contact_params:
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap contact profile missing required fields",
                "registrar": self.name,
            }

        result = self._make_request(
            "namecheap.domains.create",
            {
                "DomainName": domain,
                "Years": years,
                **contact_params,
            },
        )
        if result.get("status") != "SUCCESS":
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "API error"),
                "registrar": self.name,
            }

        create_node = result["xml"].find(".//{*}DomainCreateResult")
        success = (
            create_node is not None
            and create_node.attrib.get("Registered", "false").lower() == "true"
        )
        order_id_node = result["xml"].find(".//{*}OrderID")

        return {
            "success": success,
            "domain": domain,
            "message": "Purchase completed" if success else "Purchase unsuccessful",
            "order_id": order_id_node.text if order_id_node is not None else None,
            "registrar": self.name,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get registration pricing for a TLD."""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ProductName": tld.lower(),
                "ActionName": "register",
            },
        )
        if result.get("status") != "SUCCESS":
            return {}

        product_price = result["xml"].find(".//{*}ProductPrice")
        registration = None
        if product_price is not None:
            registration = _coerce_price(product_price.attrib.get("Price"))

        return {
            "tld": tld,
            "registration": registration,
            "renewal": None,
            "transfer": None,
            "currency": "USD",
        }

    def list_domains(self) -> List[str]:
        """List owned Namecheap domains."""
        result = self._make_request("namecheap.domains.getList", {"PageSize": 100})
        if result.get("status") != "SUCCESS":
            return []

        domains = []
        for node in result["xml"].findall(".//{*}Domain"):
            name = node.attrib.get("Name")
            if name:
                domains.append(name)
        return domains


class MultiRegistrarClient(DomainAPIClient):
    """Client that routes to the cheapest available configured registrar."""

    name = "multi"

    def __init__(self, clients: List[DomainAPIClient]):
        if not clients:
            raise ValueError("At least one registrar client is required")
        self.clients = clients
        self._domain_routing: Dict[str, DomainAPIClient] = {}

    def search_domain(self, domain: str) -> Dict:
        """Search all registrars and pick cheapest available option."""
        best_result: Optional[Dict[str, Any]] = None
        best_client: Optional[DomainAPIClient] = None
        best_price: Optional[float] = None

        for client in self.clients:
            result = client.search_domain(domain) or {}
            if not result.get("available"):
                continue

            candidate_price = _coerce_price(result.get("price"))
            if best_result is None:
                best_result = dict(result)
                best_client = client
                best_price = candidate_price
                continue

            # Prefer lower known price; unknown prices are treated as less desirable.
            if best_price is None and candidate_price is not None:
                best_result = dict(result)
                best_client = client
                best_price = candidate_price
            elif (
                best_price is not None
                and candidate_price is not None
                and candidate_price < best_price
            ):
                best_result = dict(result)
                best_client = client
                best_price = candidate_price

        if best_result is None or best_client is None:
            return {"domain": domain, "available": False, "price": None}

        best_result.setdefault("registrar", best_client.name)
        self._domain_routing[domain] = best_client
        return best_result

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase through registrar selected during search."""
        client = self._domain_routing.get(domain, self.clients[0])
        result = client.purchase_domain(domain, years=years)
        result.setdefault("registrar", client.name)
        return result

    def get_pricing(self, tld: str) -> Dict:
        """Return best-known pricing across all registrars."""
        best_pricing = None
        best_price = None
        for client in self.clients:
            pricing = client.get_pricing(tld) or {}
            price = _coerce_price(pricing.get("registration"))
            if price is None:
                continue
            if best_price is None or price < best_price:
                best_price = price
                best_pricing = pricing
        return best_pricing or {}

    def list_domains(self) -> List[str]:
        """Aggregate owned domains from all configured registrars."""
        all_domains: List[str] = []
        for client in self.clients:
            all_domains.extend(client.list_domains())
        return sorted(set(all_domains))


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
                price = _coerce_price(result.get("price"))
                if price is None:
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "registrar": result.get("registrar"),
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
                "registrar": result.get("registrar"),
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
