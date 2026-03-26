"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    
    provider_name = "generic"

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
    provider_name = "porkbun"
    
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
    Namecheap requires an allowlisted public client IP.
    https://www.namecheap.com/support/api/intro/
    """

    provider_name = "namecheap"
    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_BASE_URL = "https://api.sandbox.namecheap.com/xml.response"

    # Conservative defaults used when pricing API is unavailable.
    DEFAULT_TLD_PRICING = {
        "xyz": 2.49,
        "club": 4.98,
        "online": 5.98,
        "site": 4.98,
        "website": 4.98,
        "com": 10.98,
        "net": 12.98,
        "org": 10.98,
    }

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str,
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key)
        self.username = username
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make Namecheap API request and return parsed XML root."""
        base_url = self.SANDBOX_BASE_URL if self.sandbox else self.BASE_URL
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
            response = self.session.get(base_url, params=payload, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            status = root.attrib.get("Status", "ERROR")
            return {
                "status": status,
                "root": root,
                "raw": response.text,
            }
        except Exception as exc:
            logger.error("Namecheap API request failed: %s", exc)
            return {"status": "ERROR", "message": str(exc)}

    @staticmethod
    def _iter_nodes(root: ET.Element, node_name: str):
        """Iterate XML nodes by local-name, ignoring namespaces."""
        for node in root.iter():
            if node.tag.endswith(node_name):
                yield node

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        if result.get("status") != "OK":
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": self.provider_name,
                "message": result.get("message", "API error"),
            }

        check_result = None
        for node in self._iter_nodes(result["root"], "DomainCheckResult"):
            if node.attrib.get("Domain", "").lower() == domain.lower():
                check_result = node
                break

        if check_result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": self.provider_name,
                "message": "No check result returned",
            }

        available = check_result.attrib.get("Available", "false").lower() == "true"
        premium_price = check_result.attrib.get("PremiumRegistrationPrice")
        return {
            "domain": domain,
            "available": available,
            "price": premium_price if premium_price else None,
            "currency": "USD",
            "provider": self.provider_name,
            "is_premium": check_result.attrib.get("IsPremiumName", "false").lower() == "true",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain.
        Requires a complete Namecheap contact profile.
        """
        required_contact_fields = [
            "FirstName",
            "LastName",
            "Address1",
            "City",
            "StateProvince",
            "PostalCode",
            "Country",
            "Phone",
            "EmailAddress",
        ]

        missing_fields = [field for field in required_contact_fields if not self.contact_profile.get(field)]
        if missing_fields:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Namecheap purchase requires contact profile fields: "
                    + ", ".join(missing_fields)
                ),
            }

        params: Dict[str, Any] = {
            "DomainName": domain,
            "Years": years,
        }

        contact_types = ["Registrant", "Tech", "Admin", "AuxBilling"]
        for contact_type in contact_types:
            for field in required_contact_fields:
                params[f"{contact_type}{field}"] = self.contact_profile[field]
            if self.contact_profile.get("OrganizationName"):
                params[f"{contact_type}OrganizationName"] = self.contact_profile["OrganizationName"]

        result = self._make_request("namecheap.domains.create", params)
        if result.get("status") != "OK":
            return {
                "success": False,
                "domain": domain,
                "message": result.get("message", "Namecheap API error"),
            }

        root = result["root"]
        create_result = None
        for node in self._iter_nodes(root, "DomainCreateResult"):
            create_result = node
            break

        if create_result is None:
            return {
                "success": False,
                "domain": domain,
                "message": "No create result returned by Namecheap",
            }

        registered = create_result.attrib.get("Registered", "false").lower() == "true"
        return {
            "success": registered,
            "domain": domain,
            "message": "SUCCESS" if registered else "Domain purchase failed",
            "order_id": create_result.attrib.get("OrderID"),
        }

    def get_pricing(self, tld: str) -> Dict:
        """
        Get pricing for TLD.
        Falls back to conservative static pricing when API parsing fails.
        """
        tld = tld.lstrip(".").lower()
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "register",
            },
        )

        if result.get("status") == "OK":
            for node in self._iter_nodes(result["root"], "Product"):
                product_name = (
                    node.attrib.get("Name")
                    or node.attrib.get("ProductName")
                    or ""
                ).lower()
                if product_name.endswith(f".{tld}") or product_name == tld:
                    register_price = (
                        node.attrib.get("YourPrice")
                        or node.attrib.get("Price")
                        or node.attrib.get("RegularPrice")
                    )
                    if register_price:
                        return {
                            "tld": tld,
                            "registration": register_price,
                            "renewal": node.attrib.get("RegularPrice", register_price),
                            "transfer": node.attrib.get("YourAdditonalCost", ""),
                            "currency": "USD",
                        }

        if tld in self.DEFAULT_TLD_PRICING:
            conservative_price = str(self.DEFAULT_TLD_PRICING[tld])
            return {
                "tld": tld,
                "registration": conservative_price,
                "renewal": conservative_price,
                "transfer": conservative_price,
                "currency": "USD",
            }

        return {}


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
        fallback_clients: Optional[List[DomainAPIClient]] = None,
    ):
        self.api_client = api_client
        self.fallback_clients = fallback_clients or []
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self._configuration: Dict[str, Any] = {
            "primary_provider": getattr(api_client, "provider_name", None),
            "fallback_providers": [getattr(client, "provider_name", "generic") for client in self.fallback_clients],
        }
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self._configuration["primary_provider"] = getattr(api_client, "provider_name", "generic")

    def set_fallback_clients(self, fallback_clients: Optional[List[DomainAPIClient]] = None):
        """Set fallback clients used when the primary registrar cannot fulfill requests."""
        self.fallback_clients = fallback_clients or []
        self._configuration["fallback_providers"] = [
            getattr(client, "provider_name", "generic")
            for client in self.fallback_clients
        ]

    @staticmethod
    def _normalize_price(raw_price: Any) -> Optional[float]:
        """Normalize registrar price values to float."""
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
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _all_clients(self) -> List[DomainAPIClient]:
        clients: List[DomainAPIClient] = []
        if self.api_client:
            clients.append(self.api_client)
        clients.extend(self.fallback_clients)
        return clients

    def _create_client(
        self,
        provider: str,
        api_key: str,
        api_secret: Optional[str] = None,
        username: Optional[str] = None,
        client_ip: Optional[str] = None,
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ) -> DomainAPIClient:
        provider_normalized = (provider or "porkbun").strip().lower()

        if provider_normalized == "porkbun":
            if not api_secret:
                raise ValueError("Porkbun requires secret key")
            return PorkbunAPIClient(api_key, api_secret)

        if provider_normalized == "namecheap":
            effective_username = username or api_secret
            if not effective_username:
                raise ValueError("Namecheap requires username")
            if not client_ip:
                raise ValueError("Namecheap requires allowlisted client IP")
            return NamecheapAPIClient(
                api_key=api_key,
                username=effective_username,
                client_ip=client_ip,
                sandbox=sandbox,
                contact_profile=contact_profile,
            )

        raise ValueError(f"Unsupported registrar provider: {provider}")

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        provider: str = "porkbun",
        username: Optional[str] = None,
        client_ip: Optional[str] = None,
        sandbox: bool = False,
        fallback_provider: Optional[str] = None,
        fallback_api_key: Optional[str] = None,
        fallback_secret_key: Optional[str] = None,
        fallback_api_secret: Optional[str] = None,
        fallback_username: Optional[str] = None,
        fallback_client_ip: Optional[str] = None,
        fallback_sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
        fallback_contact_profile: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Configure primary and optional fallback domain registrar clients.
        """
        effective_secret = api_secret or secret_key
        if not api_key:
            return {"success": False, "message": "Missing API key"}

        try:
            primary_client = self._create_client(
                provider=provider,
                api_key=api_key,
                api_secret=effective_secret,
                username=username,
                client_ip=client_ip,
                sandbox=sandbox,
                contact_profile=contact_profile,
            )
        except Exception as exc:
            logger.error("Primary domain client configuration failed: %s", exc)
            return {"success": False, "message": f"Primary configuration failed: {exc}"}

        fallback_clients: List[DomainAPIClient] = []
        if fallback_provider and fallback_api_key:
            fallback_secret = fallback_api_secret or fallback_secret_key
            try:
                fallback_client = self._create_client(
                    provider=fallback_provider,
                    api_key=fallback_api_key,
                    api_secret=fallback_secret,
                    username=fallback_username,
                    client_ip=fallback_client_ip,
                    sandbox=fallback_sandbox,
                    contact_profile=fallback_contact_profile,
                )
                fallback_clients.append(fallback_client)
            except Exception as exc:
                logger.error("Fallback domain client configuration failed: %s", exc)
                return {"success": False, "message": f"Fallback configuration failed: {exc}"}

        self.set_api_client(primary_client)
        self.set_fallback_clients(fallback_clients)

        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        self._configuration.update(
            {
                "primary_provider": getattr(primary_client, "provider_name", provider),
                "fallback_providers": [
                    getattr(client, "provider_name", "generic")
                    for client in fallback_clients
                ],
                "has_primary_credentials": True,
                "has_fallback_credentials": bool(fallback_clients),
            }
        )
        logger.info(
            "Configured domain rotation with primary provider '%s'%s",
            self._configuration["primary_provider"],
            (
                f" and fallback(s) {self._configuration['fallback_providers']}"
                if self._configuration["fallback_providers"]
                else ""
            ),
        )
        return {"success": True, "message": "Domain rotation configuration updated"}

    def get_config(self) -> Dict[str, Any]:
        """Get non-sensitive domain manager configuration and status."""
        config = dict(self._configuration)
        config.update(
            {
                "configured": self.api_client is not None,
                "monthly_budget": self.monthly_budget,
                "current_spending": self.current_spending,
                "active_domain": self.active_domain,
                "domains_owned": len(self.owned_domains),
            }
        )
        return config
    
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
        clients = self._all_clients()
        if not clients:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for client in clients:
                result = client.search_domain(domain)
                if not result.get("available"):
                    continue

                price = self._normalize_price(result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
                    price = self._normalize_price(pricing.get("registration"))

                if price is None:
                    logger.warning(
                        "Skipping %s from %s because price is unknown",
                        domain,
                        getattr(client, "provider_name", "unknown"),
                    )
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": getattr(client, "provider_name", "unknown"),
                        "api_client": client,
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        api_client: Optional[DomainAPIClient] = None,
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        client = api_client or self.api_client
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
                "provider": getattr(client, "provider_name", "unknown"),
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
            api_client=domain_info.get("api_client"),
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
