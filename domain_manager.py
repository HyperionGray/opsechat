"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def can_purchase(self) -> bool:
        """Whether this client has enough configuration for purchases."""
        return True
    
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
            "currency": result.get("currency", "USD"),
            "registrar": "porkbun"
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


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.api_client_order: List[str] = []
        self.active_registrar: Optional[str] = None
        self.registrar_config: Dict[str, Dict[str, Any]] = {}
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client:
            self.add_api_client("primary", api_client, make_primary=True)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.add_api_client("primary", api_client, make_primary=True)

    def add_api_client(self, name: str, api_client: DomainAPIClient, make_primary: bool = False):
        """Register an API client, optionally as the primary registrar."""
        key = (name or "").strip().lower()
        if not key:
            raise ValueError("Registrar name is required")

        self.api_clients[key] = api_client
        if key in self.api_client_order:
            self.api_client_order.remove(key)

        if make_primary:
            self.api_client_order.insert(0, key)
            self.active_registrar = key
        else:
            self.api_client_order.append(key)
            if not self.active_registrar:
                self.active_registrar = key

        # Keep backwards-compatible alias for older callers.
        self.api_client = self.api_clients[self.api_client_order[0]]

    def _get_clients_in_priority_order(self, preferred: Optional[str] = None) -> List[Tuple[str, DomainAPIClient]]:
        """Return registered clients in priority order with optional preferred first."""
        if not self.api_client_order:
            return []

        order = list(self.api_client_order)
        if preferred:
            preferred_key = preferred.strip().lower()
            if preferred_key in order:
                order.remove(preferred_key)
                order.insert(0, preferred_key)

        return [(name, self.api_clients[name]) for name in order if name in self.api_clients]

    @staticmethod
    def _parse_price(price: Any, default: float = 999.0) -> float:
        """Normalize registrar price formats into float."""
        if price is None:
            return default

        if isinstance(price, (int, float)):
            return float(price)

        if isinstance(price, str):
            normalized = (
                price.replace("$", "")
                .replace("€", "")
                .replace(",", "")
                .strip()
            )
            try:
                return float(normalized)
            except ValueError:
                return default

        return default
    
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
        clients = self._get_clients_in_priority_order(self.active_registrar)
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

                price = self._parse_price(result.get("price"))
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "registrar": registrar_name
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        registrar: Optional[str] = None
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        clients = self._get_clients_in_priority_order(registrar or self.active_registrar)
        if not clients:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        for registrar_name, client in clients:
            if not client.can_purchase():
                logger.info(f"Registrar '{registrar_name}' is configured for lookup-only mode")
                continue

            result = client.purchase_domain(domain, years=1)
            if result.get("success"):
                self.current_spending += price
                self.owned_domains.append({
                    "domain": domain,
                    "price": price,
                    "registrar": registrar_name,
                    "purchased_at": datetime.now(),
                    "expires_at": datetime.now() + timedelta(days=365)
                })

                if not self.active_domain:
                    self.active_domain = domain

                self.active_registrar = registrar_name
                logger.info(
                    f"Successfully purchased domain: {domain} for ${price} via {registrar_name}"
                )
                return True

            logger.error(
                f"Failed to purchase domain via {registrar_name}: {result.get('message')}"
            )

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
            domain_info["price"],
            registrar=domain_info.get("registrar")
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            self.active_registrar = domain_info.get("registrar", self.active_registrar)
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

    def search_cheap_domains(self, max_price: float = 5.0, limit: int = 5) -> List[Dict]:
        """
        Search multiple available cheap domains.
        Uses repeated random attempts and returns unique results.
        """
        results: List[Dict] = []
        seen = set()

        # Bound total attempts to avoid unbounded loops if no domains are found.
        max_total_attempts = max(limit * 10, 10)
        attempts = 0
        while len(results) < limit and attempts < max_total_attempts:
            attempts += 1
            candidate = self.find_cheap_available_domain(max_price=max_price, max_attempts=1)
            if not candidate:
                continue
            domain = candidate.get("domain")
            if domain and domain not in seen:
                seen.add(domain)
                results.append(candidate)

        return results

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict:
        """
        Structured rotation result for API/UI use-cases.
        Keeps rotate_domain() backward-compatible for older callers.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain"
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            registrar=domain_info.get("registrar")
        )
        if not success:
            return {
                "success": False,
                "error": "Failed to purchase domain",
                "domain": domain_info["domain"],
                "price": domain_info["price"],
                "registrar": domain_info.get("registrar")
            }

        self.active_domain = domain_info["domain"]
        self.active_registrar = domain_info.get("registrar", self.active_registrar)
        return {
            "success": True,
            "domain": self.active_domain,
            "cost": domain_info["price"],
            "registrar": self.active_registrar
        }

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        **kwargs
    ) -> Dict:
        """
        Configure registrar credentials and budget.
        Supports both porkbun and namecheap registrars.
        """
        registrar_name = (registrar or "porkbun").strip().lower()
        self.monthly_budget = float(monthly_budget)

        if registrar_name == "porkbun":
            effective_secret = api_secret or secret_key
            if not api_key or not effective_secret:
                raise ValueError("Porkbun requires api_key and secret_key")

            client = PorkbunAPIClient(api_key, effective_secret)
            self.add_api_client("porkbun", client, make_primary=kwargs.get("make_primary", True))
            self.registrar_config["porkbun"] = {
                "configured": True,
                "api_key_suffix": api_key[-4:] if len(api_key) >= 4 else api_key,
            }
        elif registrar_name == "namecheap":
            username = kwargs.get("username") or kwargs.get("namecheap_username")
            client_ip = kwargs.get("client_ip") or kwargs.get("namecheap_client_ip")
            api_user = kwargs.get("api_user")
            sandbox = bool(kwargs.get("sandbox", False))
            contact_profile = kwargs.get("contact_profile")
            if not api_key or not username or not client_ip:
                raise ValueError("Namecheap requires api_key, username, and client_ip")

            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                api_user=api_user,
                sandbox=sandbox,
                contact_profile=contact_profile
            )
            self.add_api_client("namecheap", client, make_primary=kwargs.get("make_primary", True))
            self.registrar_config["namecheap"] = {
                "configured": True,
                "username": username,
                "client_ip": client_ip,
                "sandbox": sandbox,
                "purchase_enabled": bool(contact_profile),
                "api_key_suffix": api_key[-4:] if len(api_key) >= 4 else api_key,
            }
        else:
            raise ValueError(f"Unsupported registrar: {registrar_name}")

        return self.get_config()

    def get_config(self) -> Dict:
        """Return current domain rotation configuration (without raw secrets)."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "active_registrar": self.active_registrar,
            "domains_owned": len(self.owned_domains),
            "registrars": self.registrar_config,
            "has_api_client": bool(self.api_client_order),
            "client_order": list(self.api_client_order),
        }


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap API client.
    Uses XML API: https://www.namecheap.com/support/api/intro/
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
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key, None)
        self.username = username
        self.client_ip = client_ip
        self.api_user = api_user or username
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    def can_purchase(self) -> bool:
        required = {
            "first_name",
            "last_name",
            "address1",
            "city",
            "state_province",
            "postal_code",
            "country",
            "phone",
            "email_address",
        }
        return required.issubset(set(self.contact_profile.keys()))

    @staticmethod
    def _split_domain(domain: str) -> Optional[Tuple[str, str]]:
        if not domain or "." not in domain:
            return None
        sld, tld = domain.rsplit(".", 1)
        if not sld or not tld:
            return None
        return sld, tld

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict:
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
            status = root.attrib.get("Status", "").upper()
            if status == "OK":
                return {"status": "SUCCESS", "xml": root}

            errors = [node.text for node in root.findall(".//Errors/Error") if node.text]
            message = "; ".join(errors) if errors else "Unknown Namecheap API error"
            return {"status": "ERROR", "message": message}
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return {"status": "ERROR", "message": str(e)}

    def _build_contact_payload(self) -> Dict[str, str]:
        base = {
            "FirstName": self.contact_profile["first_name"],
            "LastName": self.contact_profile["last_name"],
            "Address1": self.contact_profile["address1"],
            "City": self.contact_profile["city"],
            "StateProvince": self.contact_profile["state_province"],
            "PostalCode": self.contact_profile["postal_code"],
            "Country": self.contact_profile["country"],
            "Phone": self.contact_profile["phone"],
            "EmailAddress": self.contact_profile["email_address"],
        }
        contact_payload: Dict[str, str] = {}
        for prefix in ("Registrant", "Admin", "Tech", "AuxBilling"):
            for key, value in base.items():
                contact_payload[f"{prefix}{key}"] = value
        return contact_payload

    def search_domain(self, domain: str) -> Dict:
        parts = self._split_domain(domain)
        if not parts:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "registrar": "namecheap",
            }

        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if result.get("status") != "SUCCESS":
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "registrar": "namecheap",
                "error": result.get("message"),
            }

        xml_root = result["xml"]
        check_result = xml_root.find(".//DomainCheckResult")
        if check_result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "registrar": "namecheap",
            }

        available_value = (check_result.attrib.get("Available", "false") or "false").lower()
        available = available_value in {"true", "yes", "1"}
        price = check_result.attrib.get("PremiumRegistrationPrice")
        if not price:
            pricing = self.get_pricing(parts[1])
            price = pricing.get("registration")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "registrar": "namecheap",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        if not self.can_purchase():
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Namecheap purchase requires contact_profile with billing/contact fields"
                ),
            }

        parts = self._split_domain(domain)
        if not parts:
            return {
                "success": False,
                "domain": domain,
                "message": "Invalid domain format",
            }

        sld, tld = parts
        payload: Dict[str, Any] = {
            "DomainName": domain,
            "Years": years,
            "SLD": sld,
            "TLD": tld,
            "AddFreeWhoisguard": "yes",
            "WGEnabled": "yes",
        }
        payload.update(self._build_contact_payload())

        result = self._make_request("namecheap.domains.create", payload)
        if result.get("status") != "SUCCESS":
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Unknown error"),
            }

        xml_root = result["xml"]
        create_result = xml_root.find(".//DomainCreateResult")
        registered = (
            (create_result.attrib.get("Registered", "false") if create_result is not None else "false")
            .lower()
            in {"true", "yes", "1"}
        )
        return {
            "success": registered,
            "domain": domain,
            "message": "Domain purchased" if registered else "Domain purchase not confirmed",
            "order_id": None,
        }

    def get_pricing(self, tld: str) -> Dict:
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "register",
                "ProductName": f".{tld}",
            },
        )

        if result.get("status") != "SUCCESS":
            return {}

        xml_root = result["xml"]
        # Namecheap may nest Price nodes under Product with different durations/types.
        # Prefer 1-year registration if available.
        one_year = xml_root.find(".//Price[@Duration='1']")
        any_price = xml_root.find(".//Price")
        price_node = one_year if one_year is not None else any_price
        if price_node is None:
            return {}

        registration = (
            price_node.attrib.get("YourPrice")
            or price_node.attrib.get("Price")
            or price_node.attrib.get("PriceValue")
        )
        return {
            "tld": tld,
            "registration": registration,
            "renewal": None,
            "transfer": None,
            "currency": "USD",
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
