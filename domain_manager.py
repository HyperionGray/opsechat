"""
Domain management and API integration.

Supports automated domain purchasing for burner email rotation with
multiple registrar backends.
"""
import logging
import random
import string
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    @abstractmethod
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available."""
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain."""
    
    @abstractmethod
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD."""


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
    Namecheap XML API client for domain management.
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_BASE_URL = "https://api.sandbox.namecheap.com/xml.response"

    REQUIRED_CONTACT_FIELDS = (
        "first_name",
        "last_name",
        "address1",
        "city",
        "state_province",
        "postal_code",
        "country",
        "phone",
        "email_address",
    )

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key, username)
        self.username = username
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    @property
    def base_url(self) -> str:
        return self.SANDBOX_BASE_URL if self.sandbox else self.BASE_URL

    def _make_request(self, command: str, params: Optional[Dict[str, str]] = None) -> str:
        query = {
            "ApiUser": self.username,
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
            return response.text
        except Exception as exc:
            logger.error(f"Namecheap API request failed: {exc}")
            return ""

    def _parse_xml(self, payload: str) -> Optional[ET.Element]:
        if not payload:
            return None
        try:
            return ET.fromstring(payload)
        except ET.ParseError as exc:
            logger.error(f"Namecheap XML parse error: {exc}")
            return None

    @staticmethod
    def _is_success(root: Optional[ET.Element]) -> bool:
        if root is None:
            return False
        return root.attrib.get("Status", "").upper() == "OK"

    @staticmethod
    def _extract_error(root: Optional[ET.Element]) -> str:
        if root is None:
            return "empty response"
        error_node = root.find(".//{*}Error")
        if error_node is not None and error_node.text:
            return error_node.text.strip()
        return "unknown API error"

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        # Namecheap expects +<countrycode>.<number>
        phone = phone.strip()
        if "." in phone and phone.startswith("+"):
            return phone
        digits = "".join(ch for ch in phone if ch.isdigit())
        if not digits:
            return "+1.5555555555"
        if len(digits) <= 10:
            return f"+1.{digits}"
        return f"+{digits[0]}.{digits[1:]}"

    def _missing_contact_fields(self) -> List[str]:
        return [
            field for field in self.REQUIRED_CONTACT_FIELDS
            if not str(self.contact_profile.get(field, "")).strip()
        ]

    def search_domain(self, domain: str) -> Dict:
        result_xml = self._make_request(
            "namecheap.domains.check",
            {"DomainList": domain},
        )
        root = self._parse_xml(result_xml)
        if root is None:
            return {"domain": domain, "available": False, "error": "invalid API response"}
        if not self._is_success(root):
            return {
                "domain": domain,
                "available": False,
                "error": self._extract_error(root),
            }

        check_node = root.find(".//{*}DomainCheckResult")
        if check_node is None:
            return {"domain": domain, "available": False, "error": "missing check result"}

        available = check_node.attrib.get("Available", "").lower() == "true"
        price = check_node.attrib.get("PremiumRegistrationPrice")
        if not price:
            tld = domain.split(".")[-1]
            pricing = self.get_pricing(tld)
            price = pricing.get("registration")

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        result_xml = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductName": "register",
                "ActionName": "register",
            },
        )
        root = self._parse_xml(result_xml)
        if root is None or not self._is_success(root):
            return {}

        target = tld.lower().lstrip(".")
        for product_node in root.findall(".//{*}Product"):
            product_name = product_node.attrib.get("Name", "").lower().lstrip(".")
            if product_name != target:
                continue
            registration = (
                product_node.attrib.get("Price")
                or product_node.attrib.get("YourPrice")
                or product_node.attrib.get("RegularPrice")
            )
            return {
                "tld": target,
                "registration": registration,
                "currency": "USD",
            }

        return {}

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        missing = self._missing_contact_fields()
        if missing:
            return {
                "success": False,
                "domain": domain,
                "message": f"Missing Namecheap contact fields: {', '.join(missing)}",
                "order_id": None,
            }

        contact = self.contact_profile
        params = {
            "DomainName": domain,
            "Years": str(years),
        }

        mapping = {
            "FirstName": contact["first_name"],
            "LastName": contact["last_name"],
            "Address1": contact["address1"],
            "City": contact["city"],
            "StateProvince": contact["state_province"],
            "PostalCode": contact["postal_code"],
            "Country": contact["country"],
            "Phone": self._normalize_phone(contact["phone"]),
            "EmailAddress": contact["email_address"],
        }

        org_name = str(contact.get("organization_name", "")).strip() or "None"

        for role in ("Registrant", "Tech", "Admin", "AuxBilling"):
            for key, value in mapping.items():
                params[f"{role}{key}"] = value
            params[f"{role}OrganizationName"] = org_name

        result_xml = self._make_request("namecheap.domains.create", params)
        root = self._parse_xml(result_xml)
        if root is None:
            return {
                "success": False,
                "domain": domain,
                "message": "invalid API response",
                "order_id": None,
            }

        create_node = root.find(".//{*}DomainCreateResult")
        order_id_node = root.find(".//{*}OrderID")
        success = self._is_success(root) and (
            create_node is not None and create_node.attrib.get("Registered", "").lower() == "true"
        )

        return {
            "success": success,
            "domain": domain,
            "message": "" if success else self._extract_error(root),
            "order_id": order_id_node.text.strip() if order_id_node is not None and order_id_node.text else None,
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
        self.primary_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client:
            self.add_api_client("default", api_client, set_primary=True)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the default API client (backward compatible helper)."""
        self.api_client = api_client
        self.add_api_client("default", api_client, set_primary=True)

    def add_api_client(
        self,
        provider: str,
        api_client: DomainAPIClient,
        set_primary: bool = False,
    ) -> str:
        """Register a provider-specific API client."""
        provider_key = provider.strip().lower()
        self.api_clients[provider_key] = api_client
        if set_primary or not self.primary_provider:
            self.primary_provider = provider_key
        if self.api_client is None:
            self.api_client = api_client
        return provider_key

    def set_primary_provider(self, provider: str) -> bool:
        """Set which configured provider should be used first."""
        provider_key = provider.strip().lower()
        if provider_key not in self.api_clients:
            return False
        self.primary_provider = provider_key
        self.api_client = self.api_clients[provider_key]
        return True

    def _iter_clients(self, provider: Optional[str] = None) -> List[Tuple[str, DomainAPIClient]]:
        if provider:
            provider_key = provider.strip().lower()
            client = self.api_clients.get(provider_key)
            if client:
                return [(provider_key, client)]
            return []

        ordered: List[Tuple[str, DomainAPIClient]] = []
        seen = set()

        if self.primary_provider and self.primary_provider in self.api_clients:
            ordered.append((self.primary_provider, self.api_clients[self.primary_provider]))
            seen.add(self.primary_provider)

        for key, client in self.api_clients.items():
            if key in seen:
                continue
            ordered.append((key, client))
            seen.add(key)

        if not ordered and self.api_client:
            ordered.append(("default", self.api_client))

        return ordered

    @staticmethod
    def _normalize_price(price: Any) -> Optional[float]:
        if isinstance(price, (float, int)):
            return float(price)
        if isinstance(price, str):
            cleaned = (
                price.strip()
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
        provider: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        clients = self._iter_clients(provider)
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

                if not result.get("available"):
                    continue

                price = self._normalize_price(result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
                    price = self._normalize_price(pricing.get("registration"))
                if price is None:
                    logger.warning(f"Could not determine price for {domain} via {provider_name}")
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider_name,
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider: Optional[str] = None,
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        clients = self._iter_clients(provider)
        if not clients:
            logger.error("No API client configured")
            return False

        normalized_price = self._normalize_price(price)
        if normalized_price is None:
            logger.error(f"Invalid domain price: {price}")
            return False
        
        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False

        # Attempt purchase using selected provider or fall back through configured providers
        for provider_name, client in clients:
            result = client.purchase_domain(domain, years=1)

            if result.get("success"):
                now = datetime.now()
                self.current_spending += normalized_price
                self.owned_domains.append({
                    "domain": domain,
                    "price": normalized_price,
                    "provider": provider_name,
                    "purchased_at": now,
                    "expires_at": now + timedelta(days=365),
                })

                # Set as active if no active domain
                if not self.active_domain:
                    self.active_domain = domain

                logger.info(
                    f"Successfully purchased domain via {provider_name}: "
                    f"{domain} for ${normalized_price}"
                )
                return True

            logger.error(
                f"Failed to purchase domain via {provider_name}: {result.get('message')}"
            )

        return False
    
    def rotate_domain(self, provider: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(provider=provider)
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"],
            provider=domain_info.get("provider") or provider,
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
            "providers": sorted(self.api_clients.keys()),
            "primary_provider": self.primary_provider,
        }

    def export_state(self) -> Dict:
        """Export state in a JSON-serializable format."""
        serialized_domains: List[Dict[str, Any]] = []
        for domain in self.owned_domains:
            record = dict(domain)
            purchased_at = record.get("purchased_at")
            expires_at = record.get("expires_at")
            if isinstance(purchased_at, datetime):
                record["purchased_at"] = purchased_at.isoformat()
            if isinstance(expires_at, datetime):
                record["expires_at"] = expires_at.isoformat()
            serialized_domains.append(record)

        return {
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
        }

    def import_state(self, state: Dict) -> None:
        """Import state from JSON-compatible data."""
        if not isinstance(state, dict):
            return

        self.current_spending = float(state.get("current_spending", 0.0))
        self.active_domain = state.get("active_domain")

        imported_domains: List[Dict[str, Any]] = []
        for domain in state.get("owned_domains", []):
            if not isinstance(domain, dict):
                continue
            record = dict(domain)
            for field in ("purchased_at", "expires_at"):
                value = record.get(field)
                if isinstance(value, str):
                    try:
                        record[field] = datetime.fromisoformat(value)
                    except ValueError:
                        # Keep original string if it cannot be parsed.
                        pass
            imported_domains.append(record)
        self.owned_domains = imported_domains


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
