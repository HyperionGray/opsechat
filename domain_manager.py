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
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        # Backward-compatible alias used by older tests/scripts.
        self.secret_key = api_secret
    
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        raise NotImplementedError("search_domain must be implemented by subclasses")
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError("purchase_domain must be implemented by subclasses")
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError("get_pricing must be implemented by subclasses")


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
        raw_available = result.get("isAvailable", False)
        if isinstance(raw_available, str):
            available = raw_available.lower() in {"1", "true", "yes"}
        else:
            available = bool(raw_available)
        
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and available,
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
    Documentation: https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    def __init__(
        self,
        api_user: str,
        api_key: str,
        client_ip: str,
        username: Optional[str] = None,
        use_sandbox: bool = False,
        contact_details: Optional[Dict[str, str]] = None
    ):
        super().__init__(api_key=api_key)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.contact_details = contact_details or {}
        self.base_url = self.SANDBOX_URL if use_sandbox else self.BASE_URL
        self.session = requests.Session()

    def _make_request(self, command: str, data: Optional[Dict] = None) -> str:
        """Make Namecheap API request and return XML payload."""
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
            return response.text
        except Exception as exc:
            logger.error(f"Namecheap API request failed: {exc}")
            return ""

    @staticmethod
    def _parse_xml(xml_payload: str) -> Optional[ET.Element]:
        if not xml_payload:
            return None
        try:
            return ET.fromstring(xml_payload)
        except ET.ParseError as exc:
            logger.error(f"Failed to parse Namecheap XML response: {exc}")
            return None

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available."""
        xml_payload = self._make_request(
            "namecheap.domains.check",
            {"DomainList": domain}
        )
        root = self._parse_xml(xml_payload)
        if root is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "request_failed"
            }

        result = root.find(".//{*}DomainCheckResult")
        if result is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "invalid_response"
            }

        is_available = result.attrib.get("Available", "false").lower() == "true"
        is_premium = result.attrib.get("IsPremiumName", "false").lower() == "true"
        premium_price = result.attrib.get("PremiumRegistrationPrice")

        return {
            "domain": domain,
            "available": is_available,
            "price": premium_price if is_premium else None,
            "currency": "USD",
            "premium": is_premium
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain through Namecheap API.
        Requires contact_details with Namecheap-required registrant/admin/tech/billing fields.
        """
        if not self.contact_details:
            return {
                "success": False,
                "domain": domain,
                "message": "Namecheap purchase requires contact_details configuration"
            }

        payload: Dict[str, Any] = {
            "DomainName": domain,
            "Years": years,
        }
        payload.update(self.contact_details)

        xml_payload = self._make_request("namecheap.domains.create", payload)
        root = self._parse_xml(xml_payload)
        if root is None:
            return {"success": False, "domain": domain, "message": "request_failed"}

        status = root.attrib.get("Status", "ERROR")
        error_nodes = root.findall(".//{*}Errors/{*}Error")
        errors = [node.text for node in error_nodes if node.text]

        order_id = None
        order_node = root.find(".//{*}OrderID")
        if order_node is not None:
            order_id = order_node.text

        success = status == "OK" and not errors
        return {
            "success": success,
            "domain": domain,
            "message": "; ".join(errors) if errors else "ok",
            "order_id": order_id,
        }

    def get_pricing(self, tld: str) -> Dict:
        """Get Namecheap pricing for one TLD."""
        normalized_tld = tld.lstrip(".")
        xml_payload = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ProductName": normalized_tld,
                "ActionName": "register",
            }
        )
        root = self._parse_xml(xml_payload)
        if root is None:
            return {}

        price_node = root.find(".//{*}Price")
        if price_node is None:
            return {}

        return {
            "tld": normalized_tld,
            "registration": price_node.attrib.get("YourPrice"),
            "renewal": None,
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
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.registrar = self._detect_registrar(api_client)

    @staticmethod
    def _detect_registrar(api_client: Optional[DomainAPIClient]) -> str:
        if isinstance(api_client, NamecheapAPIClient):
            return "namecheap"
        return "porkbun"

    @staticmethod
    def _mask_sensitive(value: Optional[str]) -> str:
        if not value:
            return ""
        if len(value) <= 4:
            return "*" * len(value)
        return f"{'*' * (len(value) - 4)}{value[-4:]}"
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.registrar = self._detect_registrar(api_client)

    def set_monthly_budget(self, monthly_budget: float):
        """Backward-compatible budget setter for older scripts."""
        if monthly_budget <= 0:
            raise ValueError("monthly_budget must be positive")
        self.monthly_budget = monthly_budget
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def generate_domain_name(self, tld: str = "xyz", length: int = 8) -> str:
        """Backward-compatible alias used by older test utilities."""
        return self.generate_random_domain(tld=tld, length=length)
    
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
                price = result.get("price", 999)
                
                if price is None:
                    price = 999

                if isinstance(price, str):
                    # Remove currency symbols
                    normalized = price.replace("$", "").replace("€", "").strip()
                    try:
                        price = float(normalized)
                    except ValueError:
                        logger.warning(f"Ignoring non-numeric domain price: {price}")
                        continue
                elif not isinstance(price, (int, float)):
                    continue
                
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }
        
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

    @staticmethod
    def _deserialize_datetime(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value
        return value

    @classmethod
    def _serialize_domain_entry(cls, domain_entry: Dict[str, Any]) -> Dict[str, Any]:
        serialized = dict(domain_entry)
        for field in ("purchased_at", "expires_at"):
            field_value = serialized.get(field)
            if isinstance(field_value, datetime):
                serialized[field] = field_value.isoformat()
        return serialized

    @classmethod
    def _deserialize_domain_entry(cls, domain_entry: Dict[str, Any]) -> Dict[str, Any]:
        deserialized = dict(domain_entry)
        for field in ("purchased_at", "expires_at"):
            deserialized[field] = cls._deserialize_datetime(deserialized.get(field))
        return deserialized

    def export_state(self) -> Dict[str, Any]:
        """Export state in a JSON-safe shape for CLI/file persistence."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": [
                self._serialize_domain_entry(entry)
                for entry in self.owned_domains
            ],
            "active_domain": self.active_domain,
            "registrar": self.registrar,
        }

    def load_state(self, state: Dict[str, Any]):
        """Load persisted manager state from JSON-safe data."""
        if "monthly_budget" in state:
            self.monthly_budget = float(state["monthly_budget"])
        self.current_spending = float(state.get("current_spending", 0.0))
        self.owned_domains = [
            self._deserialize_domain_entry(entry)
            for entry in state.get("owned_domains", [])
            if isinstance(entry, dict)
        ]
        self.active_domain = state.get("active_domain")
        self.registrar = state.get("registrar", self.registrar)

    def configure(
        self,
        api_key: str,
        secret_key: Optional[str] = None,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        **kwargs: Any
    ) -> bool:
        """
        Configure manager with registrar credentials.
        Maintains compatibility with older route handlers.
        """
        registrar = (registrar or "porkbun").strip().lower()
        self.set_monthly_budget(float(monthly_budget))

        if registrar == "porkbun":
            if not secret_key:
                raise ValueError("secret_key is required for Porkbun configuration")
            self.set_api_client(PorkbunAPIClient(api_key=api_key, api_secret=secret_key))
            return True

        if registrar == "namecheap":
            api_user = (kwargs.get("api_user") or kwargs.get("username") or "").strip()
            client_ip = (kwargs.get("client_ip") or "").strip()
            if not api_user or not client_ip:
                raise ValueError("api_user and client_ip are required for Namecheap")
            self.set_api_client(
                NamecheapAPIClient(
                    api_user=api_user,
                    api_key=api_key,
                    client_ip=client_ip,
                    username=kwargs.get("username"),
                    use_sandbox=bool(kwargs.get("use_sandbox", False)),
                    contact_details=kwargs.get("contact_details"),
                )
            )
            return True

        raise ValueError(f"Unsupported registrar: {registrar}")

    def get_config(self) -> Dict[str, Any]:
        """Return non-sensitive configuration and runtime status."""
        config: Dict[str, Any] = {
            "registrar": self.registrar,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "configured": self.api_client is not None,
        }

        if isinstance(self.api_client, PorkbunAPIClient):
            config["api_key"] = self._mask_sensitive(self.api_client.api_key)
            config["secret_key"] = self._mask_sensitive(self.api_client.api_secret)
        elif isinstance(self.api_client, NamecheapAPIClient):
            config["api_user"] = self.api_client.api_user
            config["api_key"] = self._mask_sensitive(self.api_client.api_key)
            config["client_ip"] = self.api_client.client_ip

        return config


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
