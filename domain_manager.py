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
from copy import deepcopy
from typing import Dict, List, Optional, Any
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
    Namecheap API client for domain management.
    Uses XML API:
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_BASE_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str,
        sandbox: bool = True,
        contact_profile_id: Optional[str] = None
    ):
        super().__init__(api_key, None)
        self.username = username
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.contact_profile_id = contact_profile_id
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make Namecheap API request and parse XML response."""
        url = self.SANDBOX_BASE_URL if self.sandbox else self.BASE_URL
        payload = {
            "ApiUser": self.username,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            payload.update(params)

        try:
            response = self.session.get(url, params=payload, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)

            errors = [el.text or "" for el in root.findall(".//{*}Errors/{*}Error")]
            success = root.attrib.get("Status", "").upper() == "OK" and not errors
            return {
                "success": success,
                "root": root,
                "errors": errors,
                "message": "; ".join(errors) if errors else "",
            }
        except Exception as exc:
            logger.error(f"Namecheap API request failed: {exc}")
            return {"success": False, "message": str(exc), "errors": [str(exc)], "root": None}

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check whether a domain is available."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if not result.get("success") or result.get("root") is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": result.get("message", "API request failed"),
            }

        node = result["root"].find(".//{*}DomainCheckResult")
        available = bool(node is not None and str(node.attrib.get("Available", "")).lower() == "true")
        return {
            "domain": domain,
            "available": available,
            "price": None,  # pricing is fetched via get_pricing
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase domain via Namecheap.
        Requires contact_profile_id to be configured.
        """
        if not self.contact_profile_id:
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap purchase requires contact_profile_id",
            }

        params = {
            "DomainName": domain,
            "Years": years,
            "RegistrantProfileId": self.contact_profile_id,
            "TechProfileId": self.contact_profile_id,
            "AdminProfileId": self.contact_profile_id,
            "AuxBillingProfileId": self.contact_profile_id,
        }
        result = self._make_request("namecheap.domains.create", params)
        if not result.get("success") or result.get("root") is None:
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Purchase failed"),
            }

        created = result["root"].find(".//{*}DomainCreateResult")
        was_registered = bool(created is not None and str(created.attrib.get("Registered", "")).lower() == "true")
        return {
            "success": was_registered,
            "domain": domain,
            "message": "Domain purchased" if was_registered else "Domain not purchased",
            "order_id": created.attrib.get("OrderID") if created is not None else None,
        }

    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get registration price for a TLD."""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductCategory": "DOMAINS",
                "ProductName": tld.lstrip(".").lower(),
            },
        )
        if not result.get("success") or result.get("root") is None:
            return {}

        # Namecheap returns tiered pricing; take first available register price.
        for price_node in result["root"].findall(".//{*}Price"):
            category = str(price_node.attrib.get("Category", "")).upper()
            if category == "REGISTER":
                return {
                    "tld": tld.lstrip(".").lower(),
                    "registration": price_node.attrib.get("Price"),
                    "renewal": price_node.attrib.get("YourPrice"),
                    "transfer": None,
                    "currency": "USD",
                }
        return {}


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
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        if api_client:
            self.add_api_client("primary", api_client, set_active=True)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.add_api_client("primary", api_client, set_active=True)

    def add_api_client(self, provider: str, api_client: DomainAPIClient, set_active: bool = False):
        """Add an API client for a provider."""
        provider_key = provider.strip().lower()
        self.api_clients[provider_key] = api_client
        if set_active or not self.active_provider:
            self.active_provider = provider_key
            self.api_client = api_client

    def set_active_provider(self, provider: str) -> bool:
        """Set active provider by name."""
        provider_key = provider.strip().lower()
        if provider_key not in self.api_clients:
            return False
        self.active_provider = provider_key
        self.api_client = self.api_clients[provider_key]
        return True

    def configure(
        self,
        api_key: str,
        secret_key: str = "",
        monthly_budget: float = 50.0,
        provider: str = "porkbun",
        **kwargs
    ) -> bool:
        """
        Configure domain provider credentials and budget.
        Supported providers: porkbun, namecheap.
        """
        provider_key = provider.strip().lower()
        self.monthly_budget = float(monthly_budget)

        if provider_key == "porkbun":
            if not api_key or not secret_key:
                raise ValueError("Porkbun requires api_key and secret_key")
            self.add_api_client(
                "porkbun",
                PorkbunAPIClient(api_key, secret_key),
                set_active=True,
            )
            return True

        if provider_key == "namecheap":
            username = kwargs.get("username", "").strip()
            client_ip = kwargs.get("client_ip", "").strip()
            contact_profile_id = kwargs.get("contact_profile_id")
            sandbox = bool(kwargs.get("sandbox", True))
            if not api_key or not username or not client_ip:
                raise ValueError("Namecheap requires api_key, username, and client_ip")
            self.add_api_client(
                "namecheap",
                NamecheapAPIClient(
                    api_key=api_key,
                    username=username,
                    client_ip=client_ip,
                    sandbox=sandbox,
                    contact_profile_id=contact_profile_id,
                ),
                set_active=True,
            )
            return True

        raise ValueError(f"Unsupported provider: {provider}")

    def get_config(self) -> Dict[str, Any]:
        """Return current domain rotation configuration and status."""
        return {
            "provider": self.active_provider,
            "api_configured": self.api_client is not None,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "providers_configured": sorted(self.api_clients.keys()),
            "budget_status": self.get_budget_status(),
        }

    def serialize_state(self) -> Dict[str, Any]:
        """Serialize manager state to JSON-safe dictionary."""
        serialized_domains: List[Dict[str, Any]] = []
        for domain in self.owned_domains:
            item = deepcopy(domain)
            for key in ("purchased_at", "expires_at"):
                value = item.get(key)
                if isinstance(value, datetime):
                    item[key] = value.isoformat()
            serialized_domains.append(item)
        return {
            "monthly_budget": float(self.monthly_budget),
            "current_spending": float(self.current_spending),
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "active_provider": self.active_provider,
        }

    def load_state(self, state: Optional[Dict[str, Any]]) -> None:
        """Load serialized state produced by serialize_state()."""
        if not state:
            return
        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))
        self.current_spending = float(state.get("current_spending", self.current_spending))
        self.active_domain = state.get("active_domain", self.active_domain)
        loaded_provider = state.get("active_provider")
        if loaded_provider:
            self.set_active_provider(loaded_provider)

        domains: List[Dict[str, Any]] = []
        for domain in state.get("owned_domains", []):
            item = deepcopy(domain)
            for key in ("purchased_at", "expires_at"):
                raw = item.get(key)
                if isinstance(raw, str):
                    try:
                        item[key] = datetime.fromisoformat(raw)
                    except ValueError:
                        pass
            domains.append(item)
        self.owned_domains = domains
    
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
                price = self._normalize_price(result.get("price"))
                if price is None:
                    pricing = self.api_client.get_pricing(tld)
                    price = self._normalize_price(pricing.get("registration"))
                if price is None:
                    continue
                
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None

    def _normalize_price(self, value: Any) -> Optional[float]:
        """Normalize registrar price value to float."""
        if isinstance(value, (float, int)):
            return float(value)
        if isinstance(value, str):
            cleaned = re.sub(r"[^0-9.]", "", value)
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
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
                "provider": self.active_provider or "primary",
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

    def rotate_domain_result(self) -> Dict[str, Any]:
        """Rotate domain and return structured result."""
        domain = self.rotate_domain()
        if not domain:
            return {
                "success": False,
                "error": "Could not rotate domain",
                "provider": self.active_provider,
                "budget_status": self.get_budget_status(),
            }
        return {
            "success": True,
            "domain": domain,
            "provider": self.active_provider,
            "budget_status": self.get_budget_status(),
        }
    
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
            "remaining": max(self.monthly_budget - self.current_spending, 0.0),
            "domains_owned": len(self.owned_domains)
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
