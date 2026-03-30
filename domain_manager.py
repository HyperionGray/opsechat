"""
Domain management and API integration.

Supports automated domain purchasing for burner email rotation with
multi-registrar fallback.
"""
import logging
import random
import re
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    
    CLIENT_NAME = "generic"

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        # Backward-compatible alias used by older test/helpers.
        self.secret_key = api_secret
    
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
    
    CLIENT_NAME = "porkbun"
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

    CLIENT_NAME = "namecheap"
    PROD_URL = "https://api.namecheap.com/xml.response"
    SANDBOX_URL = "https://api.sandbox.namecheap.com/xml.response"

    _CONTACT_TYPES = ("Registrant", "Tech", "Admin", "AuxBilling")
    _CONTACT_FIELDS = (
        "FirstName",
        "LastName",
        "Address1",
        "City",
        "StateProvince",
        "PostalCode",
        "Country",
        "Phone",
        "EmailAddress",
    )

    def __init__(
        self,
        api_user: str,
        api_key: str,
        username: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        sandbox: bool = False,
        contact_profile: Optional[Dict[str, str]] = None,
    ):
        super().__init__(api_key)
        self.api_user = api_user
        self.username = username or api_user
        self.client_ip = client_ip
        self.sandbox = sandbox
        self.contact_profile = contact_profile or {}
        self.session = requests.Session()
        self.base_url = self.SANDBOX_URL if sandbox else self.PROD_URL

    def _make_request(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Make a Namecheap API request and return a parsed result envelope."""
        payload = {
            "ApiUser": self.api_user,
            "ApiKey": self.api_key,
            "UserName": self.username,
            "ClientIp": self.client_ip,
            "Command": command,
        }
        if params:
            payload.update(params)

        try:
            response = self.session.get(self.base_url, params=payload, timeout=30)
            response.raise_for_status()
            root = ElementTree.fromstring(response.text)
            status = root.attrib.get("Status", "ERROR").upper()
            errors = [err.text for err in root.findall(".//Errors/Error") if err.text]
            return {"status": status, "errors": errors, "xml_root": root, "raw": response.text}
        except Exception as exc:
            logger.error(f"Namecheap API request failed: {exc}")
            return {"status": "ERROR", "message": str(exc)}

    @staticmethod
    def _to_bool(value: Any) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes"}

    @staticmethod
    def _parse_price(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = re.sub(r"[^0-9.\-]", "", str(value))
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _build_contact_params(self) -> Tuple[Optional[Dict[str, str]], List[str]]:
        """
        Build Namecheap contact parameters for domain create requests.

        Returns:
            (params, missing_fields)
        """
        missing = [field for field in self._CONTACT_FIELDS if not self.contact_profile.get(field)]
        if missing:
            return None, missing

        params: Dict[str, str] = {}
        for contact_type in self._CONTACT_TYPES:
            for field in self._CONTACT_FIELDS:
                key = f"{contact_type}{field}"
                params[key] = self.contact_profile[field]
            org_name = self.contact_profile.get("OrganizationName", "")
            params[f"{contact_type}OrganizationName"] = org_name
        return params, []

    def search_domain(self, domain: str) -> Dict:
        """Check if a domain is available on Namecheap."""
        result = self._make_request("namecheap.domains.check", {"DomainList": domain})
        root = result.get("xml_root")
        if result.get("status") != "OK" or root is None:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "message": "; ".join(result.get("errors", [])) or result.get("message", ""),
            }

        check = root.find(".//DomainCheckResult")
        if check is None:
            return {"domain": domain, "available": False, "price": None, "currency": "USD"}

        price_value = (
            check.attrib.get("PremiumRegistrationPrice")
            or check.attrib.get("RegularPrice")
            or check.attrib.get("Price")
        )
        return {
            "domain": domain,
            "available": self._to_bool(check.attrib.get("Available", "false")),
            "price": self._parse_price(price_value),
            "currency": "USD",
            "premium": self._to_bool(check.attrib.get("IsPremiumName", "false")),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase a domain on Namecheap.

        Note:
            Namecheap requires detailed contact profile fields. If those are
            not configured this method returns a safe, non-purchasing failure.
        """
        contact_params, missing = self._build_contact_params()
        if not contact_params:
            return {
                "success": False,
                "domain": domain,
                "message": (
                    "Namecheap contact profile incomplete. "
                    f"Missing fields: {', '.join(missing)}"
                ),
                "order_id": None,
            }

        payload = {"DomainName": domain, "Years": years}
        payload.update(contact_params)
        result = self._make_request("namecheap.domains.create", payload)
        root = result.get("xml_root")

        if result.get("status") != "OK" or root is None:
            return {
                "success": False,
                "domain": domain,
                "message": "; ".join(result.get("errors", [])) or result.get("message", ""),
                "order_id": None,
            }

        create_result = root.find(".//DomainCreateResult")
        order_node = root.find(".//OrderID")
        order_id = order_node.text if order_node is not None else None
        created = False
        if create_result is not None:
            created = self._to_bool(create_result.attrib.get("Registered", "false"))

        return {
            "success": created or result.get("status") == "OK",
            "domain": domain,
            "message": "Domain purchase completed" if created else "Domain purchase request sent",
            "order_id": order_id,
        }

    def get_pricing(self, tld: str) -> Dict:
        """Get Namecheap pricing data for a TLD (best-effort)."""
        result = self._make_request(
            "namecheap.users.getPricing",
            {
                "ProductType": "DOMAIN",
                "ProductCategory": "register",
                "ActionName": "register",
                "ProductName": tld,
            },
        )
        root = result.get("xml_root")
        if result.get("status") != "OK" or root is None:
            return {}

        # Namecheap pricing responses include several price nodes. Pick the first
        # available registration entry for display and filtering.
        price_node = root.find(".//Price")
        if price_node is None:
            return {}

        registration = (
            self._parse_price(price_node.attrib.get("YourPrice"))
            or self._parse_price(price_node.attrib.get("Price"))
        )
        renewal = self._parse_price(price_node.attrib.get("YourPrice"))
        return {
            "tld": tld,
            "registration": registration,
            "renewal": renewal,
            "transfer": None,
            "currency": "USD",
        }

    def list_domains(self) -> List[str]:
        """List domains owned in Namecheap account."""
        result = self._make_request("namecheap.domains.getList", {"PageSize": 100})
        root = result.get("xml_root")
        if result.get("status") != "OK" or root is None:
            return []

        domains = []
        for node in root.findall(".//Domain"):
            name = node.attrib.get("Name")
            if name:
                domains.append(name)
        return domains


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client: Optional[DomainAPIClient] = None
        self._api_clients: Dict[str, DomainAPIClient] = {}
        self.primary_registrar: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.last_rotation_details: Dict[str, Any] = {}
        self._config: Dict[str, Any] = {}

        if api_client:
            self.set_api_client(api_client)
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.add_api_client(api_client, name="primary", make_primary=True)

    def add_api_client(
        self,
        api_client: DomainAPIClient,
        name: Optional[str] = None,
        make_primary: bool = False,
    ):
        """Add a registrar client; optionally set it as primary."""
        raw_name: Optional[str] = name
        if raw_name is None:
            candidate = getattr(api_client, "CLIENT_NAME", None)
            if isinstance(candidate, str):
                raw_name = candidate

        client_name = (raw_name or "").strip().lower()
        if not client_name:
            client_name = "primary" if not self._api_clients else f"client_{len(self._api_clients) + 1}"

        self._api_clients[client_name] = api_client
        if make_primary or not self.primary_registrar:
            self.primary_registrar = client_name
            self.api_client = api_client

    def get_api_client(self, name: Optional[str] = None) -> Optional[DomainAPIClient]:
        """Get a configured registrar client by name or primary if omitted."""
        if name:
            key = str(name).strip().lower()
            client = self._api_clients.get(key)
            if client:
                return client
        if self.primary_registrar:
            return self._api_clients.get(self.primary_registrar)
        return self.api_client

    def _iter_api_clients(self) -> List[Tuple[str, DomainAPIClient]]:
        """Return clients in search order (primary first, then fallbacks)."""
        ordered: List[Tuple[str, DomainAPIClient]] = []
        seen = set()
        if self.primary_registrar and self.primary_registrar in self._api_clients:
            ordered.append((self.primary_registrar, self._api_clients[self.primary_registrar]))
            seen.add(self.primary_registrar)
        for name, client in self._api_clients.items():
            if name not in seen:
                ordered.append((name, client))
        # Backward compatibility if only api_client is set directly.
        if not ordered and self.api_client:
            ordered.append(("primary", self.api_client))
        return ordered

    @staticmethod
    def _normalize_price(raw_price: Any) -> Optional[float]:
        """Normalize various registrar price formats into a float."""
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        cleaned = re.sub(r"[^0-9.\-]", "", str(raw_price))
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
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
        tlds: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        clients = self._iter_api_clients()
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

                price = self._normalize_price(result.get("price"))
                # If registrar cannot provide a price, skip for safety.
                if price is None:
                    logger.debug(
                        "Registrar %s did not return price for %s",
                        registrar_name,
                        domain,
                    )
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "registrar": registrar_name,
                    }
        
        return None
    
    def purchase_domain_if_budget_allows(
        self,
        domain: str,
        price: float,
        api_client: Optional[DomainAPIClient] = None,
        registrar_name: Optional[str] = None,
    ) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        client = api_client or self.get_api_client(registrar_name)
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
                "registrar": registrar_name or self.primary_registrar or getattr(client, "CLIENT_NAME", "unknown"),
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
            self.last_rotation_details = {
                "success": False,
                "error": "Could not find available cheap domain",
            }
            return None
        
        # Purchase domain
        registrar_name = domain_info.get("registrar")
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"],
            registrar_name=registrar_name,
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            self.last_rotation_details = {
                "success": True,
                "domain": self.active_domain,
                "price": domain_info["price"],
                "registrar": registrar_name,
            }
            return self.active_domain

        self.last_rotation_details = {
            "success": False,
            "error": "Purchase failed or budget exceeded",
            "domain": domain_info.get("domain"),
            "price": domain_info.get("price"),
            "registrar": registrar_name,
        }
        return None

    def rotate_domain_with_details(self) -> Dict[str, Any]:
        """Rotate domain and return structured result for API/CLI use."""
        domain = self.rotate_domain()
        if domain:
            result = dict(self.last_rotation_details)
            result["budget_status"] = self.get_budget_status()
            return result
        return dict(self.last_rotation_details or {"success": False, "error": "Domain rotation failed"})
    
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

    # --- configuration and compatibility helpers ---

    def set_monthly_budget(self, monthly_budget: float):
        """Set monthly spending budget."""
        self.monthly_budget = float(monthly_budget)

    def generate_domain_name(self, tld: str = "xyz", length: int = 8) -> str:
        """Backward-compatible alias for random domain generation."""
        return self.generate_random_domain(tld=tld, length=length)

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 5,
        max_attempts: int = 25,
    ) -> List[Dict[str, Any]]:
        """Search and return up to `limit` cheap available domains."""
        found: List[Dict[str, Any]] = []
        seen_domains = set()

        for _ in range(max_attempts):
            if len(found) >= limit:
                break
            candidate = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=tlds,
            )
            if not candidate:
                continue
            domain_name = candidate.get("domain")
            if domain_name in seen_domains:
                continue
            seen_domains.add(domain_name)
            found.append(candidate)
        return found

    def rotate_to_new_domain(self) -> Dict[str, Any]:
        """Backward-compatible rotation API returning structured result."""
        details = self.rotate_domain_with_details()
        if details.get("success"):
            return {
                "success": True,
                "domain": details.get("domain"),
                "cost": details.get("price"),
                "registrar": details.get("registrar"),
            }
        return {"success": False, "error": details.get("error", "Domain rotation failed")}

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
        namecheap_api_user: Optional[str] = None,
        namecheap_api_key: Optional[str] = None,
        namecheap_username: Optional[str] = None,
        namecheap_client_ip: str = "127.0.0.1",
        namecheap_sandbox: bool = False,
        namecheap_contact_profile: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Configure registrar clients and budget.

        Supports:
        - primary Porkbun (`registrar="porkbun"`)
        - primary Namecheap (`registrar="namecheap"`)
        - Porkbun primary + Namecheap fallback (`registrar="both"`)
        """
        registrar = (registrar or "porkbun").strip().lower()
        self.set_monthly_budget(monthly_budget)

        configured_registrars: List[str] = []
        if api_key and secret_key:
            porkbun_client = PorkbunAPIClient(api_key, secret_key)
            make_primary = registrar in {"porkbun", "both"}
            self.add_api_client(porkbun_client, name="porkbun", make_primary=make_primary)
            configured_registrars.append("porkbun")

        if namecheap_api_user and namecheap_api_key:
            namecheap_client = NamecheapAPIClient(
                api_user=namecheap_api_user,
                api_key=namecheap_api_key,
                username=namecheap_username,
                client_ip=namecheap_client_ip,
                sandbox=namecheap_sandbox,
                contact_profile=namecheap_contact_profile,
            )
            make_primary = registrar == "namecheap"
            self.add_api_client(namecheap_client, name="namecheap", make_primary=make_primary)
            configured_registrars.append("namecheap")

        if registrar == "namecheap" and "namecheap" not in configured_registrars:
            raise ValueError("registrar='namecheap' requires Namecheap credentials")

        if not configured_registrars:
            raise ValueError("No valid registrar credentials provided")

        self._config = {
            "monthly_budget": self.monthly_budget,
            "primary_registrar": self.primary_registrar,
            "configured_registrars": sorted(self._api_clients.keys()),
            "porkbun_configured": "porkbun" in self._api_clients,
            "namecheap_configured": "namecheap" in self._api_clients,
        }
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        """Return safe (non-secret) configuration and status summary."""
        base = {
            "monthly_budget": self.monthly_budget,
            "primary_registrar": self.primary_registrar,
            "configured_registrars": sorted(self._api_clients.keys()),
            "porkbun_configured": "porkbun" in self._api_clients,
            "namecheap_configured": "namecheap" in self._api_clients,
            "active_domain": self.active_domain,
            "budget_status": self.get_budget_status(),
        }
        if self._config:
            base.update(self._config)
        return base


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
