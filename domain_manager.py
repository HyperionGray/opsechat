"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import ipaddress
import logging
import random
import re
import string
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

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
    API docs: https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str = "127.0.0.1",
        api_user: Optional[str] = None,
        sandbox: bool = False
    ):
        super().__init__(api_key, api_secret=None)
        self.username = username
        self.client_ip = client_ip
        self.api_user = api_user or username
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.session = requests.Session()

    @staticmethod
    def _strip_namespace(tag: str) -> str:
        """Remove XML namespace prefix from tag names."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def _iter_by_tag(cls, root: ET.Element, tag_name: str):
        """Yield elements matching tag name regardless of namespace."""
        for element in root.iter():
            if cls._strip_namespace(element.tag) == tag_name:
                yield element

    def _make_request(self, command: str, params: Optional[Dict] = None) -> Dict:
        """Make API request and parse XML response."""
        payload = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command
        }
        if params:
            payload.update(params)

        try:
            response = self.session.get(self.base_url, params=payload, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)

            status = root.attrib.get("Status", "ERROR").upper()
            success = status == "OK"
            errors = [
                error.text.strip()
                for error in self._iter_by_tag(root, "Error")
                if error.text and error.text.strip()
            ]

            command_response = next(self._iter_by_tag(root, "CommandResponse"), None)
            return {
                "status": "SUCCESS" if success else "ERROR",
                "errors": errors,
                "message": "; ".join(errors) if errors else "",
                "command_response": command_response
            }
        except Exception as e:
            logger.error(f"Namecheap API request failed: {e}")
            return {"status": "ERROR", "message": str(e), "errors": [str(e)]}

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        result = self._make_request(
            "namecheap.domains.check",
            {"DomainList": domain}
        )

        if result.get("status") != "SUCCESS":
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": result.get("message", "Search failed")
            }

        command_response = result.get("command_response")
        if command_response is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "Invalid Namecheap response: missing CommandResponse"
            }

        check_result = next(
            self._iter_by_tag(command_response, "DomainCheckResult"),
            None
        )
        if check_result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "Invalid Namecheap response: missing DomainCheckResult"
            }

        available = str(check_result.attrib.get("Available", "false")).lower() == "true"
        # Namecheap may return either standard or premium price attributes.
        price = (
            check_result.attrib.get("PremiumRegistrationPrice")
            or check_result.attrib.get("Price")
            or check_result.attrib.get("RegularPrice")
        )

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD"
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain.
        Note: This actually places a purchase order and may charge your account.
        """
        result = self._make_request(
            "namecheap.domains.create",
            {"DomainName": domain, "Years": years}
        )

        if result.get("status") != "SUCCESS":
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Purchase failed"),
                "order_id": None
            }

        command_response = result.get("command_response")
        create_result = (
            next(self._iter_by_tag(command_response, "DomainCreateResult"), None)
            if command_response is not None else None
        )
        registered = (
            str(create_result.attrib.get("Registered", "false")).lower() == "true"
            if create_result is not None else False
        )

        return {
            "success": registered,
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": None
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """
        Get pricing for a TLD.
        Namecheap's response is complex; return minimum useful shape.
        """
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "REGISTER"
            }
        )

        if result.get("status") != "SUCCESS":
            return {}

        command_response = result.get("command_response")
        if command_response is None:
            return {}

        # Look for the first ProductPrice record matching the requested TLD.
        # Namecheap can return many products; we match by Name attribute.
        for product in self._iter_by_tag(command_response, "Product"):
            name_attr = (product.attrib.get("Name") or "").lower()
            if name_attr in {tld.lower(), f".{tld.lower()}"}:
                product_price = next(self._iter_by_tag(product, "Price"), None)
                if product_price is None:
                    break
                return {
                    "tld": tld,
                    "registration": product_price.attrib.get("Price"),
                    "renewal": product_price.attrib.get("Price"),
                    "transfer": product_price.attrib.get("Price"),
                    "currency": "USD"
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
        self.primary_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False
        self.last_rotation_result: Optional[Dict[str, Any]] = None

        if api_client:
            provider = "primary"
            if isinstance(api_client, PorkbunAPIClient):
                provider = "porkbun"
            elif isinstance(api_client, NamecheapAPIClient):
                provider = "namecheap"
            self.add_api_client(provider, api_client, make_primary=True)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        provider = "primary"
        if isinstance(api_client, PorkbunAPIClient):
            provider = "porkbun"
        elif isinstance(api_client, NamecheapAPIClient):
            provider = "namecheap"
        self.add_api_client(provider, api_client, make_primary=True)

    def add_api_client(
        self,
        provider_name: str,
        api_client: DomainAPIClient,
        make_primary: bool = False
    ):
        """Register an API client for a provider."""
        normalized_name = provider_name.strip().lower()
        self.api_clients[normalized_name] = api_client
        if make_primary or not self.primary_provider:
            self.primary_provider = normalized_name
            self.api_client = api_client

    def set_primary_provider(self, provider_name: str) -> bool:
        """Set the provider used by default for search/purchase."""
        normalized_name = provider_name.strip().lower()
        client = self.api_clients.get(normalized_name)
        if not client:
            return False
        self.primary_provider = normalized_name
        self.api_client = client
        return True

    def get_available_providers(self) -> List[str]:
        """Get configured provider names."""
        return sorted(self.api_clients.keys())

    def set_test_mode(self, enabled: bool):
        """Enable/disable test mode (no real purchases)."""
        self.test_mode = bool(enabled)

    @staticmethod
    def _normalize_price(price: Optional[object]) -> Optional[float]:
        """Normalize mixed price formats into a float."""
        if price is None:
            return None
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            cleaned = re.sub(r"[^0-9.]", "", price)
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _get_provider_clients(self, provider: Optional[str] = None) -> List[Tuple[str, DomainAPIClient]]:
        """Get provider/client pairs to query in priority order."""
        if provider:
            normalized_name = provider.strip().lower()
            client = self.api_clients.get(normalized_name)
            if client:
                return [(normalized_name, client)]
            return []

        if self.primary_provider and self.primary_provider in self.api_clients:
            ordered = [(self.primary_provider, self.api_clients[self.primary_provider])]
            ordered.extend(
                (name, client)
                for name, client in self.api_clients.items()
                if name != self.primary_provider
            )
            return ordered

        if self.api_client:
            return [("primary", self.api_client)]

        return []

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        monthly_budget: float = 50.0,
        provider: str = "porkbun",
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        api_user: Optional[str] = None,
        sandbox: bool = False
    ) -> Dict:
        """
        Configure registrar credentials and domain rotation budget.
        Supports provider='porkbun' and provider='namecheap'.
        """
        if monthly_budget <= 0:
            raise ValueError("Monthly budget must be greater than zero")
        self.monthly_budget = monthly_budget

        normalized_provider = provider.strip().lower()
        if normalized_provider == "porkbun":
            resolved_secret = secret_key or api_secret
            if not api_key or not resolved_secret:
                raise ValueError("Porkbun requires api_key and secret_key")
            client = PorkbunAPIClient(api_key, resolved_secret)
        elif normalized_provider == "namecheap":
            if not api_key or not username:
                raise ValueError("Namecheap requires api_key and username")
            ipaddress.ip_address(client_ip)
            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                api_user=api_user,
                sandbox=sandbox
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self.add_api_client(normalized_provider, client, make_primary=True)
        return self.get_config()

    def get_config(self) -> Dict:
        """Get sanitized domain rotation configuration for UI/API display."""
        return {
            "configured": bool(self.api_clients or self.api_client),
            "primary_provider": self.primary_provider,
            "providers": self.get_available_providers(),
            "has_api_client": bool(self._get_provider_clients()),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode
        }
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        """Compatibility alias for docs/examples."""
        return self.generate_random_domain(tld=tld, length=length)

    def generate_domain_from_pattern(self, pattern: str, tld: str = "xyz") -> str:
        """
        Generate domain using placeholders:
        - {timestamp}: UTC timestamp in YYYYMMDDHHMMSS
        - {random}: 4 random lowercase/digit characters
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_token = ''.join(
            random.choice(string.ascii_lowercase + string.digits) for _ in range(4)
        )
        label = pattern.replace("{timestamp}", timestamp).replace("{random}", random_token)
        # Keep only valid domain label chars and normalize separators.
        allowed_chars = string.ascii_lowercase + string.digits + "-"
        normalized = ''.join(ch.lower() if ch.lower() in allowed_chars else "-" for ch in label)
        normalized = normalized.strip("-")
        if not normalized:
            normalized = random_token
        return f"{normalized}.{tld}"
    
    def find_cheap_available_domain(self, max_price: float = 5.0, 
                                   max_attempts: int = 10,
                                   provider: Optional[str] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        provider_clients = self._get_provider_clients(provider=provider)
        if not provider_clients:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website", "space"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            for provider_name, client in provider_clients:
                result = client.search_domain(domain)

                if result.get("available"):
                    price = self._normalize_price(result.get("price"))
                    if price is None:
                        pricing = client.get_pricing(tld)
                        price = self._normalize_price(pricing.get("registration")) if pricing else None
                    if price is None:
                        # Some providers omit price in availability checks.
                        # Use max_price as a conservative default so the domain
                        # can still be considered for rotation.
                        price = max_price

                    if price <= max_price:
                        return {
                            "domain": domain,
                            "price": price,
                            "tld": tld,
                            "provider": provider_name
                        }
        
        return None

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 10,
        provider: Optional[str] = None
    ) -> List[Dict]:
        """
        Search for multiple cheap available domains without purchasing.
        """
        if limit <= 0:
            return []

        selected_tlds = tlds or ["xyz", "club", "online", "site", "website", "space"]
        provider_clients = self._get_provider_clients(provider=provider)
        if not provider_clients:
            logger.error("No API client configured")
            return []

        results: List[Dict] = []
        seen_domains = set()
        max_attempts = max(limit * 5, 20)

        for _ in range(max_attempts):
            tld = random.choice(selected_tlds)
            domain = self.generate_random_domain(tld)
            if domain in seen_domains:
                continue

            for provider_name, client in provider_clients:
                search_result = client.search_domain(domain)
                if not search_result.get("available"):
                    continue

                price = self._normalize_price(search_result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
                    price = self._normalize_price(pricing.get("registration")) if pricing else None
                if price is None:
                    price = max_price
                if price > max_price:
                    continue

                entry = {
                    "domain": domain,
                    "price": price,
                    "tld": tld,
                    "provider": provider_name
                }
                results.append(entry)
                seen_domains.add(domain)
                break

            if len(results) >= limit:
                break

        return results

    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        provider: Optional[str] = None
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        provider_clients = self._get_provider_clients(provider=provider)
        if not provider_clients:
            logger.error("No API client configured")
            return False
        provider_name, client = provider_clients[0]
        normalized_price = self._normalize_price(price)
        if normalized_price is None:
            logger.error(f"Invalid domain price for purchase: {price}")
            return False
        
        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        if self.test_mode:
            result = {
                "success": True,
                "domain": domain,
                "message": "Test mode enabled: purchase simulated",
                "order_id": "test-order"
            }
        else:
            result = client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            purchased_at = datetime.now()
            self.current_spending += normalized_price
            self.owned_domains.append({
                "domain": domain,
                "price": normalized_price,
                "provider": provider_name,
                "purchased_at": purchased_at,
                "expires_at": purchased_at + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(
                f"Successfully purchased domain: {domain} from "
                f"{provider_name} for ${normalized_price}"
            )
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False

    def rotate_domain(
        self,
        provider: Optional[str] = None,
        max_price: float = 5.0,
        max_attempts: int = 10
    ) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=max_attempts,
            provider=provider
        )
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            self.last_rotation_result = {"success": False, "error": "No cheap available domain found"}
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"],
            provider=domain_info.get("provider")
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            self.last_rotation_result = {
                "success": True,
                "domain": self.active_domain,
                "cost": domain_info["price"],
                "provider": domain_info.get("provider")
            }
            return self.active_domain
        
        self.last_rotation_result = {
            "success": False,
            "error": "Purchase failed or budget exceeded",
            "domain": domain_info["domain"],
            "provider": domain_info.get("provider")
        }
        return None

    def rotate_to_new_domain(
        self,
        provider: Optional[str] = None,
        max_price: float = 5.0,
        max_attempts: int = 10
    ) -> Dict:
        """
        Rotate to a new domain and return API-friendly result payload.
        """
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=max_attempts,
            provider=provider
        )
        if not domain_info:
            result = {"success": False, "error": "No cheap available domain found"}
            self.last_rotation_result = result
            return result

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
            provider=domain_info.get("provider")
        )

        if not success:
            result = {"success": False, "error": "Purchase failed or budget exceeded"}
            self.last_rotation_result = result
            return result

        self.active_domain = domain_info["domain"]
        result = {
            "success": True,
            "domain": self.active_domain,
            "cost": domain_info["price"],
            "provider": domain_info.get("provider")
        }
        self.last_rotation_result = result
        return result
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return self.owned_domains
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        percentage_used = 0.0
        if self.monthly_budget > 0:
            percentage_used = (self.current_spending / self.monthly_budget) * 100
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains),
            "percentage_used": round(percentage_used, 2)
        }

    def get_last_rotation_result(self) -> Optional[Dict[str, Any]]:
        """Return the latest structured rotate-domain result."""
        return self.last_rotation_result


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
