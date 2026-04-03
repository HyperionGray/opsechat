"""
Domain management and API integration.

Supports automated domain purchasing for burner email rotation, including
multi-registrar search fallback.
"""
import logging
import random
import string
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    """Convert registrar price values into float, or return None."""
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
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str,
        api_user: Optional[str] = None,
        sandbox: bool = False,
        default_contact: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key)
        self.username = username
        self.api_user = api_user or username
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.default_contact = default_contact or {}
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Execute a Namecheap API request and return parsed XML payload."""
        url = self.SANDBOX_URL if self.sandbox else self.BASE_URL
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
            response = self.session.get(url, params=query, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception as exc:
            logger.error(f"Namecheap API request failed: {exc}")
            return {"status": "ERROR", "message": str(exc)}

        if root.attrib.get("Status") != "OK":
            error_text = "Unknown Namecheap API error"
            for elem in root.iter():
                if elem.tag.endswith("Error") and (elem.text or "").strip():
                    error_text = elem.text.strip()
                    break
            return {"status": "ERROR", "message": error_text}

        return {"status": "SUCCESS", "root": root}

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        result = self._make_request(
            "namecheap.domains.check",
            {"DomainList": domain},
        )
        if result.get("status") != "SUCCESS":
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": result.get("message"),
            }

        root = result["root"]
        check_node = None
        for elem in root.iter():
            if elem.tag.endswith("DomainCheckResult"):
                check_node = elem
                break

        if check_node is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "error": "Malformed Namecheap response",
            }

        available = str(check_node.attrib.get("Available", "")).lower() == "true"
        # Namecheap's check API does not consistently return a registration price.
        price = _safe_float(
            check_node.attrib.get("PremiumRegistrationPrice")
            or check_node.attrib.get("Price")
        )
        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase a domain.

        Namecheap requires contact fields on create requests. This client accepts
        them through `default_contact` supplied at initialization.
        """
        required = {
            "RegistrantFirstName": "Privacy",
            "RegistrantLastName": "User",
            "RegistrantAddress1": "Unknown",
            "RegistrantCity": "Unknown",
            "RegistrantStateProvince": "Unknown",
            "RegistrantPostalCode": "00000",
            "RegistrantCountry": "US",
            "RegistrantPhone": "+1.5555555555",
            "RegistrantEmailAddress": "noreply@example.com",
        }
        required.update(self.default_contact)

        missing = [key for key in required if not required.get(key)]
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": f"Missing required Namecheap contact fields: {', '.join(missing)}",
                "order_id": None,
            }

        payload = {
            "DomainName": domain,
            "Years": years,
            "AddFreeWhoisguard": "yes",
            "WGEnabled": "yes",
        }
        payload.update(required)

        # Reuse registrant contact for all contact roles.
        for src, dst in [
            ("Registrant", "Tech"),
            ("Registrant", "Admin"),
            ("Registrant", "AuxBilling"),
        ]:
            for field in [
                "FirstName",
                "LastName",
                "Address1",
                "City",
                "StateProvince",
                "PostalCode",
                "Country",
                "Phone",
                "EmailAddress",
            ]:
                payload[f"{dst}{field}"] = payload[f"{src}{field}"]

        result = self._make_request("namecheap.domains.create", payload)
        if result.get("status") != "SUCCESS":
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Purchase failed"),
                "order_id": None,
            }

        order_id = None
        for elem in result["root"].iter():
            if elem.tag.endswith("DomainCreateResult"):
                order_id = elem.attrib.get("OrderID")
                registered = str(elem.attrib.get("Registered", "")).lower() == "true"
                return {
                    "success": registered,
                    "domain": domain,
                    "message": "" if registered else "Namecheap did not confirm registration",
                    "order_id": order_id,
                }

        return {
            "success": False,
            "domain": domain,
            "message": "Malformed Namecheap purchase response",
            "order_id": order_id,
        }

    def get_pricing(self, tld: str) -> Dict:
        """Get registration pricing metadata for a TLD."""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ProductName": tld,
            },
        )
        if result.get("status") != "SUCCESS":
            return {}

        price = None
        root = result["root"]
        for elem in root.iter():
            if elem.tag.endswith("Price") and elem.attrib.get("Duration") == "1":
                price = _safe_float(elem.attrib.get("Price"))
                if price is not None:
                    break

        if price is None:
            return {}

        return {
            "tld": tld,
            "registration": price,
            "renewal": None,
            "transfer": None,
            "currency": "USD",
        }


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
    ):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_registrar: Optional[str] = None
        self.registrar_configs: Dict[str, Dict[str, Any]] = {}

        if api_client:
            registrar = "porkbun" if isinstance(api_client, PorkbunAPIClient) else "primary"
            self.add_api_client(registrar, api_client, make_active=True)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        registrar = "porkbun" if isinstance(api_client, PorkbunAPIClient) else "primary"
        self.add_api_client(registrar, api_client, make_active=True)

    def add_api_client(self, registrar: str, api_client: DomainAPIClient, make_active: bool = False):
        """Add an API client for a registrar."""
        key = registrar.strip().lower()
        self.api_clients[key] = api_client
        if self.api_client is None:
            self.api_client = api_client
        if make_active or self.active_registrar is None:
            self.active_registrar = key

    def get_config(self) -> Dict[str, Any]:
        """Return non-secret configuration/state for API-facing routes."""
        return {
            "active_registrar": self.active_registrar,
            "configured_registrars": sorted(self.api_clients.keys()),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Configure a registrar client.

        Backward-compatible defaults keep existing Porkbun form posts working.
        """
        registrar_key = registrar.strip().lower()
        self.monthly_budget = float(monthly_budget)

        if registrar_key == "porkbun":
            api_secret = kwargs.get("api_secret") or secret_key
            if not api_key or not api_secret:
                raise ValueError("Porkbun configuration requires api_key and secret_key/api_secret")
            client = PorkbunAPIClient(api_key=api_key, api_secret=api_secret)
            self.registrar_configs[registrar_key] = {"api_key": api_key}
        elif registrar_key == "namecheap":
            username = kwargs.get("username")
            api_user = kwargs.get("api_user") or username
            client_ip = kwargs.get("client_ip")
            sandbox = bool(kwargs.get("sandbox", False))
            default_contact = kwargs.get("default_contact", {})
            if not api_key or not username or not client_ip:
                raise ValueError("Namecheap configuration requires api_key, username, and client_ip")
            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                api_user=api_user,
                client_ip=client_ip,
                sandbox=sandbox,
                default_contact=default_contact,
            )
            self.registrar_configs[registrar_key] = {
                "api_key": api_key,
                "username": username,
                "api_user": api_user,
                "client_ip": client_ip,
                "sandbox": sandbox,
            }
        else:
            raise ValueError(f"Unsupported registrar: {registrar}")

        self.add_api_client(registrar_key, client, make_active=True)
        return {"success": True, "registrar": registrar_key}

    def _ordered_clients(self, preferred_registrar: Optional[str] = None) -> List[Tuple[str, DomainAPIClient]]:
        """
        Return clients in search order: preferred -> active -> remaining.
        """
        ordered: List[Tuple[str, DomainAPIClient]] = []
        seen = set()

        for candidate in [preferred_registrar, self.active_registrar]:
            if candidate:
                key = candidate.strip().lower()
                client = self.api_clients.get(key)
                if client and key not in seen:
                    ordered.append((key, client))
                    seen.add(key)

        for key, client in self.api_clients.items():
            if key not in seen:
                ordered.append((key, client))
                seen.add(key)

        if not ordered and self.api_client:
            ordered.append(("primary", self.api_client))

        return ordered

    def _get_tld_registration_price(self, api_client: DomainAPIClient, tld: str) -> Optional[float]:
        """Try to derive a TLD registration price from registrar pricing APIs."""
        pricing = api_client.get_pricing(tld)
        return _safe_float(pricing.get("registration"))
    
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
        if not self.api_client and not self.api_clients:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        clients = self._ordered_clients(preferred_registrar=preferred_registrar)

        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for registrar, client in clients:
                result = client.search_domain(domain)
                if not result.get("available"):
                    continue

                price = _safe_float(result.get("price"))
                if price is None:
                    price = self._get_tld_registration_price(client, tld)

                # Some registrars do not expose check-time pricing. In that case,
                # treat it as max_price so budget checks still gate the purchase.
                if price is None:
                    price = max_price

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
        registrar: Optional[str] = None,
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        key = registrar.strip().lower() if registrar else self.active_registrar
        api_client = self.api_clients.get(key) if key else self.api_client
        if api_client is None:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "registrar": key or "primary",
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
    
    def rotate_domain(self, preferred_registrar: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(preferred_registrar=preferred_registrar)
        
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
            if domain_info.get("registrar"):
                self.active_registrar = domain_info["registrar"]
            return self.active_domain
        
        return None

    def rotate_domain_with_details(self, preferred_registrar: Optional[str] = None) -> Dict[str, Any]:
        """Rotate to a new domain and return API-friendly response details."""
        new_domain = self.rotate_domain(preferred_registrar=preferred_registrar)
        if not new_domain:
            return {"success": False, "error": "Could not rotate domain"}

        return {
            "success": True,
            "domain": new_domain,
            "registrar": self.active_registrar,
            "budget": self.get_budget_status(),
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
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
