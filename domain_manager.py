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
    
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        raise NotImplementedError
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError

    @staticmethod
    def normalize_price(price) -> Optional[float]:
        """Convert different registrar price formats into float."""
        if price is None:
            return None
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            cleaned = price.replace("$", "").replace("€", "").strip()
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None


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
        normalized_price = self.normalize_price(result.get("price"))
        
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and result.get("isAvailable", False),
            "price": normalized_price if normalized_price is not None else result.get("price"),
            "currency": result.get("currency", "USD"),
            "registrar": "porkbun",
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
    Namecheap API client for domain availability and pricing.

    NOTE:
    Namecheap domain purchases require full contact profile data. This client
    currently supports reliable domain search/pricing and can be extended for
    purchasing once contact fields are provided.
    """

    BASE_URL = "https://api.namecheap.com/xml.response"

    def __init__(self, api_key: str, username: str, client_ip: str):
        super().__init__(api_key, None)
        self.username = username
        self.client_ip = client_ip
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict] = None) -> ET.Element:
        params = {
            "ApiUser": self.username,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if data:
            params.update(data)

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            return ET.fromstring(response.text)
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            raise

    @staticmethod
    def _local_name(tag: str) -> str:
        if "}" in tag:
            return tag.rsplit("}", 1)[-1]
        return tag

    def _find_first(self, root: ET.Element, tag_name: str) -> Optional[ET.Element]:
        for element in root.iter():
            if self._local_name(element.tag) == tag_name:
                return element
        return None

    def search_domain(self, domain: str) -> Dict:
        try:
            root = self._make_request("namecheap.domains.check", {"DomainList": domain})
            result = self._find_first(root, "DomainCheckResult")
            if result is None:
                return {
                    "domain": domain,
                    "available": False,
                    "price": None,
                    "currency": "USD",
                    "registrar": "namecheap",
                    "message": "Malformed Namecheap response",
                }

            available = str(result.attrib.get("Available", "false")).lower() == "true"
            price_raw = (
                result.attrib.get("PremiumRegistrationPrice")
                or result.attrib.get("PremiumRenewalPrice")
                or result.attrib.get("Price")
            )
            return {
                "domain": domain,
                "available": available,
                "price": self.normalize_price(price_raw),
                "currency": "USD",
                "registrar": "namecheap",
            }
        except Exception as e:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "registrar": "namecheap",
                "message": str(e),
            }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        return {
            "success": False,
            "domain": domain,
            "message": (
                "Namecheap purchases require contact profile fields. "
                "Use Porkbun for purchases or extend this client with "
                "namecheap.domains.create contact parameters."
            ),
            "years": years,
        }

    def get_pricing(self, tld: str) -> Dict:
        try:
            root = self._make_request(
                "namecheap.users.getPricing",
                {"ProductType": "DOMAIN", "ActionName": "REGISTER", "ProductName": tld},
            )
            # Pricing XML is complex and may vary by account and promotions.
            # Return minimal normalized metadata that callers can rely on.
            return {
                "tld": tld,
                "registration": None,
                "renewal": None,
                "transfer": None,
                "currency": "USD",
                "status": "SUCCESS" if self._find_first(root, "ApiResponse") is not None else "UNKNOWN",
                "registrar": "namecheap",
            }
        except Exception as e:
            logger.error(f"Failed to get Namecheap pricing for .{tld}: {e}")
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
        if api_client:
            self.api_clients["primary"] = api_client
            self.active_registrar = "primary"
        else:
            self.active_registrar: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient, registrar: str = "primary"):
        """Set (or replace) an API client and make it active by default."""
        self.api_client = api_client
        self.api_clients[registrar] = api_client
        self.active_registrar = registrar

    def add_api_client(self, registrar: str, api_client: DomainAPIClient):
        """Add a registrar client without replacing the current active client."""
        self.api_clients[registrar] = api_client
        if self.api_client is None:
            self.api_client = api_client
            self.active_registrar = registrar

    def set_active_registrar(self, registrar: str) -> bool:
        """Set the active registrar if configured."""
        if registrar not in self.api_clients:
            logger.error(f"Registrar '{registrar}' is not configured")
            return False
        self.active_registrar = registrar
        self.api_client = self.api_clients[registrar]
        return True

    def _iter_clients(self) -> List[Tuple[str, DomainAPIClient]]:
        if not self.api_clients:
            if self.api_client:
                return [("primary", self.api_client)]
            return []

        # Prioritize active registrar first, then the others.
        ordered: List[Tuple[str, DomainAPIClient]] = []
        if self.active_registrar and self.active_registrar in self.api_clients:
            ordered.append((self.active_registrar, self.api_clients[self.active_registrar]))
        for registrar, client in self.api_clients.items():
            if registrar != self.active_registrar:
                ordered.append((registrar, client))
        return ordered

    def _resolve_client_for_purchase(self, registrar: Optional[str] = None) -> Tuple[Optional[str], Optional[DomainAPIClient]]:
        if registrar:
            return registrar, self.api_clients.get(registrar)

        if self.active_registrar and self.active_registrar in self.api_clients:
            return self.active_registrar, self.api_clients[self.active_registrar]

        if self.api_client:
            return "primary", self.api_client

        for reg_name, client in self.api_clients.items():
            return reg_name, client

        return None, None
    
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
        tlds: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        clients = self._iter_clients()
        if not clients:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            for registrar_name, client in clients:
                result = client.search_domain(domain)

                if not result.get("available"):
                    continue

                price = DomainAPIClient.normalize_price(result.get("price"))
                if price is None:
                    price = 999.0

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "registrar": result.get("registrar", registrar_name),
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float, registrar: Optional[str] = None) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        registrar_name, client = self._resolve_client_for_purchase(registrar)
        if not client:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
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
            domain_info["price"],
            registrar=domain_info.get("registrar"),
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            return self.active_domain
        
        return None

    def rotate_to_new_domain(self) -> Dict:
        """Structured response variant used by CLI/web routes."""
        domain = self.rotate_domain()
        if not domain:
            return {"success": False, "error": "Could not rotate domain"}

        latest = self.owned_domains[-1] if self.owned_domains else {}
        return {
            "success": True,
            "domain": domain,
            "cost": latest.get("price", 0.0),
            "registrar": latest.get("registrar"),
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
            "domains_owned": len(self.owned_domains)
        }

    def search_cheap_domains(self, tlds: Optional[List[str]] = None, max_price: float = 5.0, limit: int = 5) -> List[Dict]:
        """
        Search and return multiple candidate domains.
        This is a convenience wrapper around find_cheap_available_domain.
        """
        results: List[Dict] = []
        seen = set()
        candidate_tlds = tlds or ["xyz", "club", "online", "site", "website"]

        attempts = max(limit * 3, 5)
        for _ in range(attempts):
            if len(results) >= limit:
                break

            tld = random.choice(candidate_tlds)
            candidate = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=[tld],
            )
            if candidate and candidate["domain"] not in seen:
                seen.add(candidate["domain"])
                results.append(candidate)

        return results

    def configure(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        registrar: str = "porkbun",
        namecheap_username: Optional[str] = None,
        namecheap_api_key: Optional[str] = None,
        namecheap_client_ip: Optional[str] = None,
    ) -> Dict:
        """
        Configure registrars and budget using in-memory settings.
        This keeps backward compatibility with email routes.
        """
        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        if registrar == "porkbun" and api_key and secret_key:
            self.set_api_client(PorkbunAPIClient(api_key, secret_key), registrar="porkbun")

        if namecheap_username and namecheap_api_key and namecheap_client_ip:
            self.add_api_client(
                "namecheap",
                NamecheapAPIClient(
                    api_key=namecheap_api_key,
                    username=namecheap_username,
                    client_ip=namecheap_client_ip,
                ),
            )

        return self.get_config()

    def get_config(self) -> Dict:
        """Return non-secret configuration and current state."""
        return {
            "active_registrar": self.active_registrar,
            "configured_registrars": sorted(list(self.api_clients.keys())),
            "has_api_client": bool(self._iter_clients()),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
