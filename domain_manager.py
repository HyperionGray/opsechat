"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
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
    Namecheap API client for domain management
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_BASE_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: str,
        client_ip: str,
        use_sandbox: bool = False,
    ):
        super().__init__(api_key)
        self.api_user = api_user
        self.username = username
        self.client_ip = client_ip
        self.base_url = self.SANDBOX_BASE_URL if use_sandbox else self.BASE_URL
        self.session = requests.Session()

    @staticmethod
    def _tag_name(tag: str) -> str:
        """Remove XML namespace prefix from element tags."""
        return tag.split("}", 1)[-1] if "}" in tag else tag

    @staticmethod
    def _to_float(value) -> Optional[float]:
        """Parse prices returned as strings with optional symbols."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace("$", "").replace("€", "")
        try:
            return float(text)
        except ValueError:
            return None

    def _make_request(self, command: str, params: Optional[Dict] = None) -> Dict:
        """Make a Namecheap XML API request and parse errors."""
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
            # Some responses include leading whitespace/newlines before XML prolog.
            root = ET.fromstring(response.text.lstrip())
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return {"success": False, "message": str(e), "root": None}

        errors = []
        for element in root.iter():
            if self._tag_name(element.tag) == "Error" and element.text:
                errors.append(element.text.strip())

        if errors:
            return {"success": False, "message": "; ".join(errors), "root": root}

        return {"success": True, "message": "", "root": root}

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not result.get("success"):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": result.get("message", ""),
            }

        root = result.get("root")
        available = False
        price = None
        currency = "USD"

        for element in root.iter():
            if self._tag_name(element.tag) == "DomainCheckResult":
                available = str(element.attrib.get("Available", "")).lower() == "true"
                # Premium names may return explicit pricing.
                premium_price = element.attrib.get("PremiumRegistrationPrice")
                if premium_price:
                    price = self._to_float(premium_price)
                break

        if available and price is None:
            tld = domain.rsplit(".", 1)[-1]
            pricing = self.get_pricing(tld)
            price = self._to_float(pricing.get("registration"))
            currency = pricing.get("currency", "USD")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": currency,
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase a domain."""
        result = self._make_request(
            "namecheap.domains.create",
            {
                "DomainName": domain,
                "Years": years,
            },
        )
        if not result.get("success"):
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", ""),
                "order_id": None,
                "charged_amount": None,
            }

        root = result.get("root")
        success = False
        order_id = None
        charged_amount = None

        for element in root.iter():
            if self._tag_name(element.tag) == "DomainCreateResult":
                success = str(element.attrib.get("Registered", "")).lower() == "true"
                order_id = element.attrib.get("OrderID")
                charged_amount = self._to_float(element.attrib.get("ChargedAmount"))
                break

        return {
            "success": success,
            "domain": domain,
            "message": "" if success else "Domain purchase failed",
            "order_id": order_id,
            "charged_amount": charged_amount,
        }

    def get_pricing(self, tld: str) -> Dict:
        """Get registration pricing for a TLD."""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductName": tld.upper(),
            },
        )
        if not result.get("success"):
            return {}

        root = result.get("root")
        price = None
        currency = "USD"

        for element in root.iter():
            tag_name = self._tag_name(element.tag)
            if tag_name in ("ProductPrice", "Price"):
                duration = element.attrib.get("Duration")
                if duration == "1":
                    price = self._to_float(
                        element.attrib.get("YourPrice") or element.attrib.get("Price")
                    )
                    if price is not None:
                        break
            elif tag_name == "ApiResponse":
                currency = element.attrib.get("Currency", currency)

        if price is None:
            return {}

        return {
            "tld": tld.lower(),
            "registration": price,
            "renewal": None,
            "transfer": None,
            "currency": currency,
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self._primary_provider: Optional[str] = None
        if api_client:
            self.add_api_client("primary", api_client)
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    @property
    def api_client(self) -> Optional[DomainAPIClient]:
        """Backward-compatible single-client accessor."""
        if not self._primary_provider:
            return None
        return self.api_clients.get(self._primary_provider)

    @api_client.setter
    def api_client(self, api_client: Optional[DomainAPIClient]):
        """Backward-compatible setter that replaces configured providers."""
        self.api_clients = {}
        self._primary_provider = None
        if api_client:
            self.add_api_client("primary", api_client)

    def set_api_client(self, api_client: DomainAPIClient, provider_name: str = "primary"):
        """Set the domain API client"""
        self.api_clients = {}
        self._primary_provider = None
        self.add_api_client(provider_name, api_client)

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient):
        """Add (or replace) an API client for a provider."""
        self.api_clients[provider_name] = api_client
        if not self._primary_provider:
            self._primary_provider = provider_name

    def set_primary_provider(self, provider_name: str) -> bool:
        """Set primary provider used for default operations."""
        if provider_name not in self.api_clients:
            return False
        self._primary_provider = provider_name
        return True

    def get_provider_names(self) -> List[str]:
        """List configured provider names."""
        return list(self.api_clients.keys())

    def get_api_client(self, provider_name: Optional[str] = None) -> Optional[DomainAPIClient]:
        """Get API client by provider name (or primary)."""
        if provider_name and provider_name != "auto":
            return self.api_clients.get(provider_name)
        return self.api_client

    @staticmethod
    def _parse_price(value) -> Optional[float]:
        """Parse numeric domain price values."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.replace("$", "").replace("€", "").strip()
            try:
                return float(text)
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
    
    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        provider_name: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_clients:
            logger.error("No API clients configured")
            return None

        if provider_name and provider_name != "auto":
            selected_client = self.get_api_client(provider_name)
            if not selected_client:
                logger.error(f"Unknown provider: {provider_name}")
                return None
            providers = [(provider_name, selected_client)]
        else:
            providers = list(self.api_clients.items())
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            provider, client = random.choice(providers)
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = client.search_domain(domain)
            
            if result.get("available"):
                price = self._parse_price(result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
                    price = self._parse_price(pricing.get("registration"))
                
                if price is not None and price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider,
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider_name: Optional[str] = None,
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_clients:
            logger.error("No API clients configured")
            return False

        client = self.get_api_client(provider_name)
        if not client:
            logger.error(
                f"No API client configured for provider: {provider_name or 'primary'}"
            )
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            provider = provider_name or self._primary_provider or "unknown"
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": provider,
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
    
    def rotate_domain(self, provider_name: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(provider_name=provider_name)
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"],
            provider_name=domain_info.get("provider"),
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
