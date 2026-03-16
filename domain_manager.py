"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.provider_name = "generic"
    
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        raise NotImplementedError("Subclasses must implement search_domain()")
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("Subclasses must implement purchase_domain()")
    
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
        self.provider_name = "porkbun"
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

    NOTE:
    Namecheap's domain purchase API requires detailed contact data.
    This client supports availability + pricing out of the box, and purchase
    when a contact profile is supplied.
    """

    BASE_URL = "https://api.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str,
        api_user: Optional[str] = None,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key, None)
        self.provider_name = "namecheap"
        self.username = username
        self.client_ip = client_ip
        self.api_user = api_user or username
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, str]] = None) -> Optional[str]:
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
            response = self.session.get(self.BASE_URL, params=payload, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return None

    @staticmethod
    def _parse_xml(xml_payload: Optional[str]) -> Optional[ET.Element]:
        if not xml_payload:
            return None
        try:
            return ET.fromstring(xml_payload)
        except ET.ParseError as e:
            logger.error(f"Namecheap XML parse failed: {e}")
            return None

    @staticmethod
    def _find_first_by_suffix(root: ET.Element, suffix: str) -> Optional[ET.Element]:
        for element in root.iter():
            if element.tag.endswith(suffix):
                return element
        return None

    @staticmethod
    def _to_float(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value.strip().replace("$", ""))
        except (TypeError, ValueError, AttributeError):
            return None

    def search_domain(self, domain: str) -> Dict:
        xml_payload = self._make_request(
            "namecheap.domains.check",
            {"DomainList": domain},
        )
        root = self._parse_xml(xml_payload)
        if root is None:
            return {"domain": domain, "available": False, "provider": self.provider_name}

        result_el = self._find_first_by_suffix(root, "DomainCheckResult")
        if result_el is None:
            return {"domain": domain, "available": False, "provider": self.provider_name}

        available = str(result_el.attrib.get("Available", "")).lower() in {"true", "yes", "1"}
        price = self._to_float(
            result_el.attrib.get("PremiumRegistrationPrice")
            or result_el.attrib.get("Price")
            or result_el.attrib.get("RegistrationPrice")
        )

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "provider": self.provider_name,
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        required_keys = {
            "RegistrantFirstName",
            "RegistrantLastName",
            "RegistrantAddress1",
            "RegistrantCity",
            "RegistrantStateProvince",
            "RegistrantPostalCode",
            "RegistrantCountry",
            "RegistrantPhone",
            "RegistrantEmailAddress",
        }
        if not required_keys.issubset(self.contact_profile.keys()):
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Namecheap purchase requires full contact profile; "
                    "configure contact_profile or use Porkbun for one-step purchases."
                ),
            }

        params = {
            "DomainName": domain,
            "Years": str(years),
        }
        params.update(self.contact_profile)

        xml_payload = self._make_request("namecheap.domains.create", params)
        root = self._parse_xml(xml_payload)
        if root is None:
            return {"success": False, "domain": domain, "message": "Request/parse error"}

        status = root.attrib.get("Status", "").upper()
        success = status == "OK"
        return {
            "success": success,
            "domain": domain,
            "message": "Purchased" if success else "Purchase failed",
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        xml_payload = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "register",
                "ProductName": tld.lstrip("."),
            },
        )
        root = self._parse_xml(xml_payload)
        if root is None:
            return {}

        price_el = self._find_first_by_suffix(root, "Price")
        if price_el is None:
            return {}

        registration_price = self._to_float(price_el.attrib.get("Price"))
        return {
            "tld": tld.lstrip("."),
            "registration": registration_price,
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
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        if api_client:
            provider = getattr(api_client, "provider_name", api_client.__class__.__name__.lower())
            self.api_clients[provider] = api_client
            self.active_provider = provider
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        provider = getattr(api_client, "provider_name", api_client.__class__.__name__.lower())
        self.api_clients = {provider: api_client}
        self.active_provider = provider

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient, make_active: bool = False):
        """Add a named registrar client."""
        normalized = provider_name.strip().lower()
        self.api_clients[normalized] = api_client
        if make_active or not self.active_provider:
            self.active_provider = normalized
            self.api_client = api_client

    def get_config(self) -> Dict:
        """Return non-secret runtime configuration."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "active_provider": self.active_provider,
            "configured_providers": sorted(self.api_clients.keys()),
        }

    def configure(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        provider: str = "porkbun",
        username: Optional[str] = None,
        client_ip: Optional[str] = None,
        api_user: Optional[str] = None,
    ):
        """
        Configure registrar client and budget.
        This completes the integration expected by email configuration routes.
        """
        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        provider_name = provider.strip().lower()

        if provider_name == "porkbun":
            if not api_key or not secret_key:
                raise ValueError("Porkbun configuration requires api_key and secret_key")
            self.set_api_client(PorkbunAPIClient(api_key, secret_key))
        elif provider_name == "namecheap":
            if not api_key or not username or not client_ip:
                raise ValueError(
                    "Namecheap configuration requires api_key, username, and client_ip"
                )
            self.set_api_client(
                NamecheapAPIClient(
                    api_key=api_key,
                    username=username,
                    client_ip=client_ip,
                    api_user=api_user,
                )
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def _normalize_price(raw_price, fallback: float = 999.0) -> float:
        """Convert registrar price payloads into a comparable float."""
        if raw_price is None:
            return fallback
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if isinstance(raw_price, str):
            try:
                normalized = raw_price.replace("$", "").replace("€", "").replace(",", "").strip()
                return float(normalized)
            except ValueError:
                return fallback
        return fallback

    def _iter_clients(self, providers: Optional[List[str]] = None) -> List[Tuple[str, DomainAPIClient]]:
        if providers:
            normalized = [provider.lower() for provider in providers]
            pairs = [(name, client) for name, client in self.api_clients.items() if name in normalized]
            return pairs

        if self.api_clients:
            return list(self.api_clients.items())

        if self.api_client:
            provider = getattr(self.api_client, "provider_name", self.api_client.__class__.__name__.lower())
            return [(provider, self.api_client)]

        return []
    
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
                                   providers: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        clients = self._iter_clients(providers=providers)
        if not clients:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            for provider_name, client in clients:
                result = client.search_domain(domain)
                if result.get("available"):
                    price = self._normalize_price(result.get("price"), fallback=max_price + 1.0)
                    if price <= max_price:
                        return {
                            "domain": domain,
                            "price": price,
                            "tld": tld,
                            "provider": provider_name,
                        }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float, provider: Optional[str] = None) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        clients = self._iter_clients(providers=[provider] if provider else None)
        if not clients:
            logger.error("No API client configured")
            return False
        selected_provider, selected_client = clients[0]
        
        normalized_price = self._normalize_price(price)

        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = selected_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += normalized_price
            self.owned_domains.append({
                "domain": domain,
                "price": normalized_price,
                "provider": selected_provider,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            self.active_provider = selected_provider
            logger.info(
                f"Successfully purchased domain: {domain} via {selected_provider} for ${normalized_price}"
            )
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        providers: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=max_attempts,
            providers=providers,
        )
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"],
            provider=domain_info.get("provider"),
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
