"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Sequence, Tuple
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
        raise NotImplementedError("search_domain must be implemented by child classes")
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("purchase_domain must be implemented by child classes")
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError("get_pricing must be implemented by child classes")


class NamecheapAPIClient(DomainAPIClient):
    """
    Namecheap API client for domain management.
    Uses Namecheap XML API: https://www.namecheap.com/support/api/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        api_user: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        contact_profile: Optional[Dict[str, str]] = None,
        use_sandbox: bool = False
    ):
        super().__init__(api_key, None)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.contact_profile = contact_profile or {}
        self.base_url = self.SANDBOX_URL if use_sandbox else self.BASE_URL
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict] = None) -> Dict:
        """Make Namecheap XML API request and parse root response"""
        params = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command
        }
        if data:
            params.update(data)

        try:
            response = self.session.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            status = root.attrib.get("Status", "ERROR")
            errors = [node.text for node in root.findall(".//{*}Error") if node.text]
            return {
                "status": "SUCCESS" if status == "OK" else "ERROR",
                "xml": root,
                "errors": errors
            }
        except Exception as exc:
            logger.error(f"Namecheap API request failed: {exc}")
            return {"status": "ERROR", "message": str(exc), "errors": [str(exc)]}

    def _domain_to_parts(self, domain: str) -> Tuple[Optional[str], Optional[str]]:
        if "." not in domain:
            return None, None
        parts = domain.split(".")
        return parts[0], ".".join(parts[1:])

    def _extract_price(self, value: Optional[object]) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (float, int)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace("€", "")
            if cleaned:
                try:
                    return float(cleaned)
                except ValueError:
                    return None
        return None

    def _build_contact_params(self) -> Optional[Dict[str, str]]:
        required_fields = [
            "first_name", "last_name", "address1", "city", "state_province",
            "postal_code", "country", "phone", "email_address"
        ]
        missing = [field for field in required_fields if not self.contact_profile.get(field)]
        if missing:
            logger.error(
                "Namecheap contact profile is incomplete, missing fields: %s",
                ", ".join(missing)
            )
            return None

        role_prefixes = ("Registrant", "Tech", "Admin", "AuxBilling")
        field_map = {
            "FirstName": "first_name",
            "LastName": "last_name",
            "Address1": "address1",
            "Address2": "address2",
            "City": "city",
            "StateProvince": "state_province",
            "PostalCode": "postal_code",
            "Country": "country",
            "Phone": "phone",
            "EmailAddress": "email_address",
            "OrganizationName": "organization_name"
        }

        params: Dict[str, str] = {}
        for role in role_prefixes:
            for api_field, profile_key in field_map.items():
                value = self.contact_profile.get(profile_key, "")
                params[f"{role}{api_field}"] = value
        return params

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available"""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        xml_root = result.get("xml")
        if result.get("status") != "SUCCESS" or xml_root is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": "namecheap"
            }

        check_node = xml_root.find(".//{*}DomainCheckResult")
        available = (
            check_node is not None
            and check_node.attrib.get("Available", "false").lower() == "true"
        )
        premium_price = None
        if check_node is not None:
            premium_price = (
                check_node.attrib.get("PremiumRegistrationPrice")
                or check_node.attrib.get("PremiumRegistrationPricePrice")
            )

        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        price = self._extract_price(premium_price)
        if price is None and tld:
            pricing = self.get_pricing(tld)
            price = self._extract_price(pricing.get("registration"))

        return {
            "domain": domain,
            "available": available,
            "price": price,
            "currency": "USD",
            "provider": "namecheap"
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase a domain from Namecheap.
        Requires contact profile fields to be configured.
        """
        sld, tld = self._domain_to_parts(domain)
        if not sld or not tld:
            return {
                "success": False,
                "domain": domain,
                "message": "Invalid domain format"
            }

        contact_params = self._build_contact_params()
        if contact_params is None:
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap contact profile is incomplete"
            }

        payload: Dict[str, object] = {
            "DomainName": domain,
            "SLD": sld,
            "TLD": tld,
            "Years": years
        }
        payload.update(contact_params)

        result = self._make_request("namecheap.domains.create", payload)
        xml_root = result.get("xml")
        if result.get("status") != "SUCCESS" or xml_root is None:
            message = ", ".join(result.get("errors", [])) or result.get("message", "")
            return {
                "success": False,
                "domain": domain,
                "message": message or "Namecheap purchase failed"
            }

        create_result = xml_root.find(".//{*}DomainCreateResult")
        was_successful = (
            create_result is not None
            and create_result.attrib.get("Registered", "false").lower() == "true"
        )
        charged_amount = None
        if create_result is not None:
            charged_amount = (
                create_result.attrib.get("ChargedAmount")
                or create_result.attrib.get("ChargedAmountNoTax")
            )

        return {
            "success": was_successful,
            "domain": domain,
            "message": "Domain registered" if was_successful else "Registration failed",
            "order_id": None,
            "charged_amount": charged_amount
        }

    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD via Namecheap users.getPricing endpoint"""
        normalized_tld = tld.lstrip(".")
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ActionName": "REGISTER",
                "ProductName": normalized_tld
            }
        )
        xml_root = result.get("xml")
        if result.get("status") != "SUCCESS" or xml_root is None:
            return {}

        registration_price = None
        renewal_price = None
        transfer_price = None

        # API shape varies by account and endpoint version; select 1-year prices when present.
        for price_node in xml_root.findall(".//{*}Price"):
            duration = price_node.attrib.get("Duration")
            if duration and duration != "1":
                continue
            registration_price = (
                registration_price
                or price_node.attrib.get("YourPrice")
                or price_node.attrib.get("Price")
            )
            renewal_price = (
                renewal_price
                or price_node.attrib.get("YourPrice")
                or price_node.attrib.get("Price")
            )
            transfer_price = (
                transfer_price
                or price_node.attrib.get("YourPrice")
                or price_node.attrib.get("Price")
            )
            if registration_price and renewal_price and transfer_price:
                break

        return {
            "tld": normalized_tld,
            "registration": registration_price,
            "renewal": renewal_price,
            "transfer": transfer_price,
            "currency": "USD"
        }


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


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.default_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None

        if api_client:
            self.add_api_client("default", api_client, make_default=True)
    
    def set_api_client(self, api_client: DomainAPIClient, provider: str = "default"):
        """Set the domain API client"""
        self.api_client = api_client
        self.add_api_client(provider, api_client, make_default=True)

    def add_api_client(
        self,
        provider: str,
        api_client: DomainAPIClient,
        make_default: bool = False
    ) -> None:
        """Register an API client by provider name"""
        self.api_clients[provider] = api_client
        if make_default or self.default_provider is None:
            self.default_provider = provider
            self.api_client = api_client

    def get_registered_providers(self) -> List[str]:
        """Get list of configured registrar providers"""
        return list(self.api_clients.keys())

    def get_api_client(self, provider: Optional[str] = None) -> Optional[DomainAPIClient]:
        """Get API client by provider or default"""
        if provider:
            return self.api_clients.get(provider)
        if self.default_provider:
            return self.api_clients.get(self.default_provider)
        return self.api_client

    def configure(
        self,
        provider: str = "porkbun",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        secret_key: Optional[str] = None,
        monthly_budget: Optional[float] = None,
        **kwargs
    ) -> Dict:
        """
        Configure and register a domain provider in-memory.
        Supports legacy secret_key naming for compatibility.
        """
        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        provider_name = provider.lower()
        if provider_name == "porkbun":
            effective_secret = api_secret or secret_key
            if not api_key or not effective_secret:
                raise ValueError("Porkbun configuration requires api_key and api_secret")
            client = PorkbunAPIClient(api_key, effective_secret)
            self.add_api_client("porkbun", client, make_default=True)
        elif provider_name == "namecheap":
            api_user = kwargs.get("api_user")
            username = kwargs.get("username")
            client_ip = kwargs.get("client_ip", "127.0.0.1")
            use_sandbox = bool(kwargs.get("use_sandbox", False))
            contact_profile = kwargs.get("contact_profile")
            if not api_key or not api_user:
                raise ValueError("Namecheap configuration requires api_key and api_user")
            client = NamecheapAPIClient(
                api_key=api_key,
                api_user=api_user,
                username=username,
                client_ip=client_ip,
                contact_profile=contact_profile,
                use_sandbox=use_sandbox
            )
            self.add_api_client("namecheap", client, make_default=True)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        return {
            "success": True,
            "provider": provider_name,
            "monthly_budget": self.monthly_budget
        }

    def get_config(self) -> Dict:
        """
        Return non-secret in-memory configuration status.
        This is safe to use in route responses/templates.
        """
        return {
            "configured": bool(self.api_clients or self.api_client),
            "default_provider": self.default_provider,
            "providers": self.get_registered_providers(),
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain
        }
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def _normalize_price(self, raw_price: object) -> Optional[float]:
        """Normalize raw API price values into float or None"""
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if isinstance(raw_price, str):
            cleaned = raw_price.strip().replace("$", "").replace("€", "")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def _provider_order(self, providers: Optional[Sequence[str]] = None) -> List[str]:
        if providers:
            return list(providers)
        configured = self.get_registered_providers()
        if self.default_provider and self.default_provider in configured:
            return [self.default_provider] + [
                name for name in configured if name != self.default_provider
            ]
        return configured
    
    def find_cheap_available_domain(self, max_price: float = 5.0, 
                                   max_attempts: int = 10,
                                   providers: Optional[Sequence[str]] = None) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        provider_order = self._provider_order(providers)
        if not provider_order:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for _ in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            for provider in provider_order:
                client = self.get_api_client(provider)
                if not client:
                    continue

                result = client.search_domain(domain)
                if not result.get("available"):
                    continue

                price = self._normalize_price(result.get("price"))
                if price is None:
                    pricing = client.get_pricing(tld)
                    price = self._normalize_price(pricing.get("registration"))

                if price is not None and price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": provider
                    }
        
        return None
    
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
        client = self.get_api_client(provider)
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
                "provider": provider or self.default_provider,
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
    
    def rotate_domain(self, provider: Optional[str] = None) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        providers = [provider] if provider else None

        # Find cheap domain
        domain_info = self.find_cheap_available_domain(providers=providers)
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"],
            provider=domain_info.get("provider")
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
            "default_provider": self.default_provider,
            "providers": self.get_registered_providers()
        }


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
