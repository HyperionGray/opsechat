"""
Domain management and API integration.

Supports automated domain purchasing for burner email rotation with
pluggable registrar clients.
"""
import logging
import random
import string
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available."""
        return {
            "domain": domain,
            "available": False,
            "error": "search_domain is unsupported for this client",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain."""
        return {
            "success": False,
            "domain": domain,
            "message": "purchase_domain is unsupported for this client",
        }

    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD."""
        return {}


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

    API docs:
    https://www.namecheap.com/support/api/methods/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        api_user: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key)
        self.username = username
        self.api_user = api_user or username
        self.client_ip = client_ip
        self.contact_profile = contact_profile or {}
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> str:
        """Make API request and return XML payload."""
        params: Dict[str, Any] = {
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
            return response.text
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return ""

    @staticmethod
    def _parse_xml(xml_payload: str) -> Optional[ET.Element]:
        if not xml_payload:
            return None

        try:
            return ET.fromstring(xml_payload)
        except ET.ParseError as exc:
            logger.error("Failed to parse Namecheap XML response: %s", exc)
            return None

    @staticmethod
    def _extract_errors(root: ET.Element) -> List[str]:
        return [elem.text.strip() for elem in root.findall(".//{*}Error") if elem.text]

    def search_domain(self, domain: str) -> Dict:
        """Check whether a domain is available."""
        xml_payload = self._make_request("namecheap.domains.check", {"DomainList": domain})
        root = self._parse_xml(xml_payload)

        if root is None:
            return {"domain": domain, "available": False, "error": "API request failed"}

        errors = self._extract_errors(root)
        if errors:
            return {
                "domain": domain,
                "available": False,
                "error": "; ".join(errors),
            }

        result = root.find(".//{*}DomainCheckResult")
        if result is None:
            return {"domain": domain, "available": False, "error": "Malformed API response"}

        available = result.attrib.get("Available", "false").lower() == "true"
        is_premium = result.attrib.get("IsPremiumName", "false").lower() == "true"

        tld = domain.split(".")[-1] if "." in domain else "com"
        pricing = self.get_pricing(tld)

        return {
            "domain": domain,
            "available": available and not is_premium,
            "premium": is_premium,
            "price": pricing.get("registration"),
            "currency": pricing.get("currency", "USD"),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase a domain.

        Note: Namecheap requires contact profile details to complete a purchase.
        """
        required_fields = [
            "RegistrantFirstName",
            "RegistrantLastName",
            "RegistrantAddress1",
            "RegistrantCity",
            "RegistrantStateProvince",
            "RegistrantPostalCode",
            "RegistrantCountry",
            "RegistrantPhone",
            "RegistrantEmailAddress",
        ]
        missing_fields = [field for field in required_fields if not self.contact_profile.get(field)]
        if missing_fields:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Namecheap purchases require contact_profile fields: "
                    + ", ".join(missing_fields)
                ),
            }

        payload: Dict[str, Any] = {"DomainName": domain, "Years": years}
        payload.update(self.contact_profile)

        xml_payload = self._make_request("namecheap.domains.create", payload)
        root = self._parse_xml(xml_payload)
        if root is None:
            return {"success": False, "domain": domain, "message": "API request failed"}

        errors = self._extract_errors(root)
        if errors:
            return {"success": False, "domain": domain, "message": "; ".join(errors)}

        result = root.find(".//{*}DomainCreateResult")
        if result is None:
            return {"success": False, "domain": domain, "message": "Malformed API response"}

        registered = result.attrib.get("Registered", "false").lower() == "true"
        order_id = result.attrib.get("OrderID")
        return {
            "success": registered,
            "domain": domain,
            "message": "SUCCESS" if registered else "Domain purchase was not completed",
            "order_id": order_id,
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get registration/renewal/transfer pricing when available."""
        xml_payload = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ProductName": tld,
                "ActionName": "register",
            },
        )
        root = self._parse_xml(xml_payload)
        if root is None:
            return {}

        errors = self._extract_errors(root)
        if errors:
            logger.warning("Namecheap pricing request returned errors: %s", "; ".join(errors))
            return {}

        registration_price: Optional[str] = None
        renewal_price: Optional[str] = None
        transfer_price: Optional[str] = None

        for price_node in root.findall(".//{*}ProductPrice"):
            action_name = price_node.attrib.get("Name", "").lower()
            your_price = price_node.attrib.get("YourPrice") or price_node.attrib.get("Price")

            if not your_price:
                continue

            if action_name in ("register", "registration"):
                registration_price = your_price
            elif action_name in ("renew", "renewal"):
                renewal_price = your_price
            elif action_name == "transfer":
                transfer_price = your_price
            elif registration_price is None:
                # Fallback for responses that omit explicit action names.
                registration_price = your_price

        return {
            "tld": tld,
            "registration": registration_price,
            "renewal": renewal_price,
            "transfer": transfer_price,
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
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client:
            self.add_api_client("default", api_client, make_active=True)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the default domain API client."""
        self.api_client = api_client
        self.add_api_client("default", api_client, make_active=True)

    def add_api_client(self, provider: str, api_client: DomainAPIClient,
                       make_active: bool = False):
        """Register a provider API client."""
        normalized_provider = provider.strip().lower()
        if not normalized_provider:
            raise ValueError("Provider name cannot be empty")

        self.api_clients[normalized_provider] = api_client
        self.api_client = api_client

        if make_active or self.active_provider is None:
            self.active_provider = normalized_provider

    def get_config(self) -> Dict:
        """Get current domain rotation configuration."""
        return {
            "active_provider": self.active_provider,
            "providers": sorted(self.api_clients.keys()),
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
    ) -> Dict:
        """Create and set a configured registrar client."""
        registrar_name = registrar.strip().lower()
        self.monthly_budget = float(monthly_budget)

        if registrar_name == "porkbun":
            if not secret_key:
                raise ValueError("Porkbun requires secret_key/api_secret")
            client = PorkbunAPIClient(api_key, secret_key)
            provider = kwargs.get("provider", "porkbun")
        elif registrar_name == "namecheap":
            username = kwargs.get("username") or kwargs.get("user_name")
            if not username:
                raise ValueError("Namecheap requires username")
            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                api_user=kwargs.get("api_user"),
                client_ip=kwargs.get("client_ip", "127.0.0.1"),
                sandbox=bool(kwargs.get("sandbox", False)),
                contact_profile=kwargs.get("contact_profile"),
            )
            provider = kwargs.get("provider", "namecheap")
        else:
            raise ValueError(f"Unsupported registrar: {registrar}")

        self.add_api_client(provider, client, make_active=True)
        return self.get_config()

    def load_state(
        self,
        owned_domains: Optional[List[Dict]] = None,
        current_spending: float = 0.0,
        active_domain: Optional[str] = None,
    ):
        """Load persisted state into the manager."""
        self.current_spending = float(current_spending or 0.0)
        self.owned_domains = []

        for domain_info in owned_domains or []:
            if not isinstance(domain_info, dict):
                continue
            normalized = dict(domain_info)
            normalized.setdefault("provider", self.active_provider or "default")
            self.owned_domains.append(normalized)

        self.active_domain = active_domain

    @staticmethod
    def _normalize_price(raw_price: Any) -> Optional[float]:
        """Normalize vendor price formats to float."""
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if isinstance(raw_price, str):
            cleaned = (
                raw_price.strip()
                .replace("$", "")
                .replace("€", "")
                .replace(",", "")
            )
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _iter_provider_clients(
        self, preferred_provider: Optional[str] = None
    ) -> List[Tuple[str, DomainAPIClient]]:
        """Return provider/client tuples with preferred provider first."""
        if not self.api_clients and self.api_client:
            self.add_api_client("default", self.api_client, make_active=True)

        if not self.api_clients:
            return []

        provider_order: List[str] = []
        if preferred_provider and preferred_provider in self.api_clients:
            provider_order.append(preferred_provider)
        if self.active_provider and self.active_provider in self.api_clients and self.active_provider not in provider_order:
            provider_order.append(self.active_provider)
        for provider in self.api_clients:
            if provider not in provider_order:
                provider_order.append(provider)

        return [(provider, self.api_clients[provider]) for provider in provider_order]

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
                                    preferred_provider: Optional[str] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        providers = self._iter_provider_clients(preferred_provider=preferred_provider)
        if not providers:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            for provider_name, provider_client in providers:
                result = provider_client.search_domain(domain)

                if result.get("available"):
                    price = self._normalize_price(result.get("price"))

                    if price is None:
                        logger.warning(
                            "Skipping domain %s from %s due to missing/invalid price",
                            domain,
                            provider_name,
                        )
                        continue

                    if price <= max_price:
                        return {
                            "domain": domain,
                            "price": price,
                            "tld": tld,
                            "provider": provider_name,
                        }
        
        return None
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float,
                                         provider: Optional[str] = None) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        providers = self._iter_provider_clients(preferred_provider=provider)
        if not providers:
            logger.error("No API client configured")
            return False

        provider_name, provider_client = providers[0]
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = provider_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            now = datetime.utcnow()
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "provider": provider_name,
                "purchased_at": now.isoformat() + "Z",
                "expires_at": (now + timedelta(days=365)).isoformat() + "Z",
            })
            
            # Set as active if no active domain
            self.active_domain = domain
            self.active_provider = provider_name
            
            logger.info(
                "Successfully purchased domain: %s via %s for $%s",
                domain,
                provider_name,
                price,
            )
            return True

        logger.error("Failed to purchase domain via %s: %s", provider_name, result.get("message"))
        return False
    
    def rotate_domain(self, preferred_provider: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(preferred_provider=preferred_provider)
        
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
            self.active_provider = domain_info.get("provider", self.active_provider)
            return self.active_domain
        
        return None

    def rotate_domain_with_details(self, preferred_provider: Optional[str] = None) -> Dict:
        """
        Rotate to a new domain and return structured details.
        """
        domain_info = self.find_cheap_available_domain(preferred_provider=preferred_provider)
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain",
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider=domain_info.get("provider"),
        )
        if not success:
            return {
                "success": False,
                "error": "Domain purchase failed",
                "domain": domain_info["domain"],
                "provider": domain_info.get("provider"),
            }

        return {
            "success": True,
            "domain": domain_info["domain"],
            "price": domain_info["price"],
            "provider": domain_info.get("provider"),
        }
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return list(self.owned_domains)
    
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
