"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _normalize_price(raw_price: Any) -> Optional[float]:
    """Convert registrar price values to float when possible."""
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return float(raw_price)

    if isinstance(raw_price, str):
        cleaned = raw_price.strip()
        for symbol in ("$", "€", "USD", "usd", ","):
            cleaned = cleaned.replace(symbol, "")
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
    Namecheap API client for domain management
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: Optional[str] = None,
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
        api_user: Optional[str] = None,
    ):
        super().__init__(api_key, None)
        self.username = username
        self.api_user = api_user or username
        self.client_ip = client_ip or os.getenv("NAMECHEAP_CLIENT_IP", "127.0.0.1")
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> Optional[ET.Element]:
        """Make Namecheap XML API request."""
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
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as exc:
            logger.error(f"Namecheap API request failed: {exc}")
            return None

    @staticmethod
    def _is_success(root: ET.Element) -> bool:
        return root.attrib.get("Status") == "OK"

    @staticmethod
    def _extract_error(root: Optional[ET.Element]) -> str:
        if root is None:
            return "Request failed before response parsing"
        error_node = root.find(".//Errors/Error")
        if error_node is not None and error_node.text:
            return error_node.text.strip()
        return "Unknown Namecheap API error"

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        root = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if root is None or not self._is_success(root):
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": self._extract_error(root),
            }

        check_result = root.find(".//DomainCheckResult")
        if check_result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "Missing domain check result",
            }

        is_available = check_result.attrib.get("Available", "false").lower() == "true"
        is_premium = check_result.attrib.get("IsPremiumName", "false").lower() == "true"
        premium_price = check_result.attrib.get("PremiumRegistrationPrice")

        return {
            "domain": domain,
            "available": is_available,
            "price": premium_price if is_premium else None,
            "currency": "USD",
            "is_premium": is_premium,
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain.
        Namecheap requires contact profile fields to be provided.
        """
        required_fields = [
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
        missing = [field for field in required_fields if not self.contact_profile.get(field)]
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Missing Namecheap contact profile fields: "
                    + ", ".join(missing)
                ),
            }

        payload = {
            "DomainName": domain,
            "Years": years,
            "AddFreeWhoisguard": "yes",
            "WGEnabled": "yes",
        }
        for prefix in ("Registrant", "Tech", "Admin", "AuxBilling"):
            payload[f"{prefix}FirstName"] = self.contact_profile["first_name"]
            payload[f"{prefix}LastName"] = self.contact_profile["last_name"]
            payload[f"{prefix}Address1"] = self.contact_profile["address1"]
            payload[f"{prefix}City"] = self.contact_profile["city"]
            payload[f"{prefix}StateProvince"] = self.contact_profile["state_province"]
            payload[f"{prefix}PostalCode"] = self.contact_profile["postal_code"]
            payload[f"{prefix}Country"] = self.contact_profile["country"]
            payload[f"{prefix}Phone"] = self.contact_profile["phone"]
            payload[f"{prefix}EmailAddress"] = self.contact_profile["email_address"]

        root = self._make_request("namecheap.domains.create", payload)
        if root is None:
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap API request failed",
            }

        success = self._is_success(root)
        create_result = root.find(".//DomainCreateResult")
        registered = (
            create_result is not None
            and create_result.attrib.get("Registered", "false").lower() == "true"
        )
        order_id = create_result.attrib.get("OrderID") if create_result is not None else None

        return {
            "success": success and registered,
            "domain": domain,
            "message": "Domain purchased successfully" if (success and registered) else self._extract_error(root),
            "order_id": order_id,
        }

    def get_pricing(self, tld: str) -> Dict:
        """Get Namecheap registration pricing for a TLD."""
        product_name = tld.lstrip(".").upper()
        root = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "register",
                "ProductName": product_name,
            },
        )
        if root is None or not self._is_success(root):
            return {}

        registration_price = None
        renewal_price = None
        price_nodes = root.findall(".//ProductPrice")
        if not price_nodes:
            price_nodes = root.findall(".//Price")

        for node in price_nodes:
            duration = node.attrib.get("Duration")
            if duration != "1":
                continue
            if registration_price is None:
                registration_price = (
                    node.attrib.get("YourPrice")
                    or node.attrib.get("Price")
                    or node.attrib.get("RegularPrice")
                )
            if renewal_price is None:
                renewal_price = node.attrib.get("RenewalPrice")
            if registration_price and renewal_price:
                break

        return {
            "tld": tld.lstrip("."),
            "registration": registration_price,
            "renewal": renewal_price,
            "transfer": None,
            "currency": "USD",
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = None
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.preferred_client: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        if api_client:
            self.set_api_client(api_client)
    
    def _resolve_client_name(self, api_client: DomainAPIClient, name: Optional[str] = None) -> str:
        """Resolve normalized registrar key."""
        if name:
            return name.lower()
        return api_client.__class__.__name__.replace("APIClient", "").lower()

    def _get_client_order(self, preferred: Optional[str] = None) -> List[str]:
        """Get ordered registrar keys for fallback attempts."""
        if not self.api_clients and self.api_client:
            # Backward compatibility if legacy code set only api_client
            self.set_api_client(self.api_client)

        if not self.api_clients:
            return []

        order: List[str] = []
        if preferred and preferred in self.api_clients:
            order.append(preferred)
        elif self.preferred_client and self.preferred_client in self.api_clients:
            order.append(self.preferred_client)

        for name in self.api_clients.keys():
            if name not in order:
                order.append(name)
        return order

    def set_api_client(self, api_client: DomainAPIClient, name: Optional[str] = None, preferred: bool = True):
        """Set a registrar API client (and optionally make it preferred)."""
        client_name = self._resolve_client_name(api_client, name)
        self.api_clients[client_name] = api_client
        if preferred or not self.preferred_client:
            self.preferred_client = client_name
            self.api_client = api_client

    def add_api_client(self, name: str, api_client: DomainAPIClient, preferred: bool = False):
        """Add additional registrar client for fallback support."""
        self.set_api_client(api_client, name=name, preferred=preferred)
    
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
        preferred_registrar: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        client_order = self._get_client_order(
            preferred_registrar.lower() if preferred_registrar else None
        )
        if not client_order:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for registrar in client_order:
                client = self.api_clients[registrar]
                result = client.search_domain(domain)

                if not result.get("available"):
                    continue

                price = _normalize_price(result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
                    price = _normalize_price(pricing.get("registration"))

                if price is None:
                    logger.info(
                        "Available domain found but no price from %s for %s",
                        registrar,
                        domain,
                    )
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "registrar": registrar,
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        preferred_registrar: Optional[str] = None,
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        client_order = self._get_client_order(
            preferred_registrar.lower() if preferred_registrar else None
        )
        if not client_order:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase with fallback clients
        for registrar in client_order:
            client = self.api_clients[registrar]
            result = client.purchase_domain(domain, years=1)

            if result.get("success"):
                self.current_spending += price
                self.owned_domains.append({
                    "domain": domain,
                    "price": price,
                    "registrar": registrar,
                    "purchased_at": datetime.now(),
                    "expires_at": datetime.now() + timedelta(days=365)
                })

                # Set as active if no active domain
                if not self.active_domain:
                    self.active_domain = domain

                logger.info(
                    "Successfully purchased domain %s for $%s using %s",
                    domain,
                    price,
                    registrar,
                )
                return True

            logger.warning(
                "Registrar %s failed purchase for %s: %s",
                registrar,
                domain,
                result.get("message"),
            )

        logger.error("Failed to purchase domain across configured registrars")
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
            preferred_registrar=domain_info.get("registrar"),
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
            "preferred_registrar": self.preferred_client,
            "configured_registrars": list(self.api_clients.keys()),
        }

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        namecheap_username: Optional[str] = None,
        namecheap_client_ip: Optional[str] = None,
    ):
        """Configure registrar client and budget from UI inputs."""
        self.monthly_budget = float(monthly_budget)
        registrar_name = (registrar or "porkbun").lower()

        if registrar_name == "porkbun":
            client = PorkbunAPIClient(api_key, secret_key)
        elif registrar_name == "namecheap":
            username = namecheap_username or secret_key
            if not username:
                raise ValueError("namecheap_username is required for Namecheap")
            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                client_ip=namecheap_client_ip,
            )
        else:
            raise ValueError(f"Unsupported registrar: {registrar}")

        self.set_api_client(client, name=registrar_name, preferred=True)

    def get_config(self) -> Dict:
        """Get safe configuration summary for UI display."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "preferred_registrar": self.preferred_client,
            "configured_registrars": list(self.api_clients.keys()),
            "has_client": bool(self.api_clients),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
