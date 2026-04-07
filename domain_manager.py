"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class DomainAPIClient(ABC):
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        # Backward compatibility for older code paths.
        self.secret_key = api_secret
    
    @abstractmethod
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        raise NotImplementedError
    
    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError
    
    @abstractmethod
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
    Uses Namecheap XML API:
    https://www.namecheap.com/support/api/intro/
    """

    BASE_URL = "https://api.namecheap.com/xml.response"

    def __init__(
        self,
        api_key: str,
        username: str,
        client_ip: str = "127.0.0.1",
        api_user: Optional[str] = None,
    ):
        super().__init__(api_key)
        self.username = username
        self.api_user = api_user or username
        self.client_ip = client_ip
        self.session = requests.Session()

    def _make_request(self, command: str, params: Optional[Dict] = None) -> Dict:
        """Make Namecheap XML API request."""
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
            response = self.session.get(self.BASE_URL, params=payload, timeout=30)
            response.raise_for_status()
            return self._parse_xml_response(response.text)
        except Exception as e:
            logger.error("Namecheap API request failed: %s", e)
            return {"success": False, "error": str(e)}

    def _parse_xml_response(self, xml_content: str) -> Dict:
        """Parse simple fields from Namecheap XML response."""
        # Lightweight parsing keeps this dependency-free.
        result: Dict[str, object] = {"raw_xml": xml_content}
        lowered = xml_content.lower()
        result["success"] = 'status="ok"' in lowered
        return result

    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available for registration."""
        parts = domain.rsplit(".", 1)
        if len(parts) != 2:
            return {
                "domain": domain,
                "available": False,
                "price": None,
                "currency": "USD",
                "provider": "namecheap",
            }

        sld, tld = parts[0], parts[1]
        response = self._make_request(
            "namecheap.domains.check", {"DomainList": f"{sld}.{tld}"}
        )
        raw_xml = str(response.get("raw_xml", ""))
        available = 'Available="true"' in raw_xml or 'available="true"' in raw_xml
        return {
            "domain": domain,
            "available": available,
            "price": None,
            "currency": "USD",
            "provider": "namecheap",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Attempt domain purchase via Namecheap."""
        parts = domain.rsplit(".", 1)
        if len(parts) != 2:
            return {"success": False, "domain": domain, "message": "Invalid domain format"}

        sld, tld = parts[0], parts[1]
        response = self._make_request(
            "namecheap.domains.create",
            {
                "DomainName": f"{sld}.{tld}",
                "Years": years,
            },
        )
        return {
            "success": bool(response.get("success")),
            "domain": domain,
            "message": "Purchase submitted" if response.get("success") else "Purchase failed",
            "provider": "namecheap",
        }

    def get_pricing(self, tld: str = "com") -> Dict:
        """Get Namecheap pricing summary for a TLD."""
        response = self._make_request("namecheap.users.getPricing", {"ProductType": "DOMAIN"})
        if not response.get("success"):
            return {}
        return {"tld": tld, "registration": None, "renewal": None, "transfer": None, "currency": "USD"}


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        if api_client is not None:
            self.api_clients["default"] = api_client
        self.active_api_client_name: Optional[str] = "default" if api_client else None
        self.test_mode = False
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.domain_dns_configs: Dict[str, Dict[str, str]] = {}
        self._config: Dict[str, Optional[object]] = {
            "api_key": None,
            "secret_key": None,
            "monthly_budget": monthly_budget,
            "provider": None,
        }
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self.api_clients["default"] = api_client
        self.active_api_client_name = "default"

    def set_test_mode(self, enabled: bool):
        """Enable/disable dry-run mode where purchases are simulated."""
        self.test_mode = bool(enabled)

    def add_api_client(self, name: str, api_client: DomainAPIClient):
        """Register an additional API client provider."""
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("Provider name cannot be empty")
        self.api_clients[normalized] = api_client
        if self.api_client is None:
            self.api_client = api_client
            self.active_api_client_name = normalized

    def set_active_api_client(self, name: str) -> bool:
        """Switch active provider to a registered API client by name."""
        normalized = name.strip().lower()
        client = self.api_clients.get(normalized)
        if client is None:
            return False
        self.api_client = client
        self.active_api_client_name = normalized
        return True

    def get_registered_clients(self) -> List[str]:
        """List configured API client provider names."""
        return sorted(self.api_clients.keys())

    def get_config(self) -> Dict:
        """Expose current in-memory config for routes/UI."""
        return {
            **self._config,
            "monthly_budget": self.monthly_budget,
            "active_domain": self.active_domain,
            "active_provider": self.active_api_client_name,
            "registered_providers": self.get_registered_clients(),
            "budget_status": self.get_budget_status(),
        }

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 10.0,
        provider: str = "porkbun",
        **kwargs,
    ):
        """
        Configure domain management credentials and budget.
        Currently supports porkbun and namecheap providers.
        """
        provider_name = provider.strip().lower() if provider else "porkbun"
        self.monthly_budget = float(monthly_budget)
        self._config.update(
            {
                "api_key": api_key,
                "secret_key": secret_key,
                "monthly_budget": self.monthly_budget,
                "provider": provider_name,
            }
        )

        if provider_name == "namecheap":
            username = kwargs.get("username")
            if not username:
                raise ValueError("namecheap provider requires username")
            client_ip = kwargs.get("client_ip", "127.0.0.1")
            client = NamecheapAPIClient(
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                api_user=kwargs.get("api_user"),
            )
        elif provider_name == "porkbun":
            client = PorkbunAPIClient(api_key=api_key, api_secret=secret_key)
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")

        self.add_api_client(provider_name, client)
        self.set_active_api_client(provider_name)

    class _BudgetManagerAdapter:
        """Compatibility adapter for older budget_manager API usage."""

        def __init__(self, manager: "DomainRotationManager"):
            self._manager = manager

        @property
        def monthly_budget(self) -> float:
            return self._manager.monthly_budget

        def set_monthly_budget(self, monthly_budget: float):
            self._manager.set_monthly_budget(monthly_budget)

        def get_month_spending(self) -> float:
            return self._manager.current_spending

        def get_remaining_budget(self) -> float:
            return self._manager.monthly_budget - self._manager.current_spending

    @property
    def budget_manager(self) -> "DomainRotationManager._BudgetManagerAdapter":
        """Back-compat interface used by older docs and scripts."""
        return self._BudgetManagerAdapter(self)
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    # Backward-compat alias used by older/manual scripts
    def generate_domain_name(self, tld: str = "xyz", length: int = 8) -> str:
        return self.generate_random_domain(tld=tld, length=length)

    # Legacy alias kept for documentation/script compatibility
    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        return self.generate_random_domain(tld=tld, length=length)

    def generate_domain_from_pattern(self, pattern: str, tld: str = "xyz") -> str:
        """
        Generate a domain from a simple template pattern.
        Supported placeholders:
        - {timestamp}: UTC timestamp in YYYYMMDDHHMMSS format
        - {random}: 6 random lowercase alnum characters
        """
        rendered = pattern.replace(
            "{timestamp}",
            datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        )
        if "{random}" in rendered:
            random_token = "".join(
                random.choice(string.ascii_lowercase + string.digits) for _ in range(6)
            )
            rendered = rendered.replace("{random}", random_token)
        # Keep only DNS-safe characters.
        safe = "".join(ch if (ch.isalnum() or ch == "-") else "-" for ch in rendered.lower())
        safe = safe.strip("-") or self.generate_random_domain(tld=tld).split(".")[0]
        return f"{safe}.{tld}"

    def _coerce_price(self, raw_price: object) -> float:
        """Convert provider price data to a comparable float."""
        if isinstance(raw_price, (int, float)):
            return float(raw_price)
        if isinstance(raw_price, str):
            cleaned = raw_price.replace("$", "").replace("€", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 999.0
        return 999.0
    
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
                price = self._coerce_price(result.get("price", 999))
                # Some APIs do not return a search price. Allow fallback selection.
                if result.get("price") is None:
                    price = 0.0

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "provider": self.active_api_client_name,
                    }
        
        return None

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 5,
        max_attempts: int = 20,
    ) -> List[Dict]:
        """
        Return a list of cheap available domains.
        This is a convenience wrapper used by docs and scripts.
        """
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        results: List[Dict] = []
        attempts = 0

        while len(results) < limit and attempts < max_attempts:
            attempts += 1
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld=tld)

            if not self.api_client:
                logger.error("No API client configured")
                break

            candidate = self.api_client.search_domain(domain)
            if not candidate.get("available"):
                continue

            raw_price = candidate.get("price")
            parsed_price = 0.0 if raw_price is None else self._coerce_price(raw_price)
            if parsed_price > max_price:
                continue

            results.append(
                {
                    "domain": domain,
                    "price": parsed_price,
                    "tld": tld,
                    "provider": self.active_api_client_name,
                }
            )

        return results
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False

        normalized_price = self._coerce_price(price)

        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(
                f"Budget exceeded. Current: ${self.current_spending}, "
                f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}"
            )
            return False

        # Test mode simulates a successful purchase without hitting provider APIs.
        if self.test_mode:
            self.current_spending += normalized_price
            self.owned_domains.append(
                {
                    "domain": domain,
                    "price": normalized_price,
                    "purchased_at": datetime.now(timezone.utc),
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=365),
                    "provider": self.active_api_client_name,
                    "test_mode": True,
                }
            )
            if not self.active_domain:
                self.active_domain = domain
            logger.info(
                "Simulated domain purchase in test mode: %s for $%s via %s",
                domain,
                normalized_price,
                self.active_api_client_name or "default",
            )
            return True

        result = self.api_client.purchase_domain(domain, years=1)
        if result.get("success"):
            self.current_spending += normalized_price
            self.owned_domains.append(
                {
                    "domain": domain,
                    "price": normalized_price,
                    "purchased_at": datetime.now(timezone.utc),
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=365),
                    "provider": self.active_api_client_name,
                }
            )
            if not self.active_domain:
                self.active_domain = domain

            logger.info(
                "Successfully purchased domain: %s for $%s via %s",
                domain,
                normalized_price,
                self.active_api_client_name or "default",
            )
            return True

        logger.error(f"Failed to purchase domain: {result.get('message')}")
        return False
    
    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        domain_info = self.find_cheap_available_domain()
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
        )
        if success:
            self.active_domain = domain_info["domain"]
            return self.active_domain
        return None

    def rotate_to_new_domain(self) -> Dict:
        """
        Backward-compatible rotation API used in docs/manual scripts.
        Returns a status dictionary instead of a bare domain string.
        """
        domain = self.rotate_domain()
        if domain is None:
            return {
                "success": False,
                "error": "Could not find or purchase a suitable domain",
                "provider": self.active_api_client_name,
            }

        latest_price = self.owned_domains[-1].get("price") if self.owned_domains else None
        return {
            "success": True,
            "domain": domain,
            "cost": latest_price,
            "provider": self.active_api_client_name,
        }

    def configure_domain_dns(
        self,
        domain: str,
        mx_record: Optional[str] = None,
        txt_record: Optional[str] = None,
        records: Optional[Dict[str, str]] = None,
        provider: Optional[str] = None,
        mx_records: Optional[List[Dict[str, object]]] = None,
        a_records: Optional[List[Dict[str, object]]] = None,
    ) -> Dict:
        """
        Store desired DNS settings and optionally push to provider if supported.
        Accepts either explicit `mx_record`/`txt_record` or a generic `records` dict.
        """
        if provider and not self.set_active_api_client(provider):
            return {"success": False, "error": f"Unknown provider: {provider}"}

        record_map = dict(records or {})
        if mx_record:
            record_map["mx_record"] = mx_record
        if txt_record is not None:
            record_map["txt_record"] = txt_record

        mx_value = record_map.get("mx_record") or record_map.get("mx")
        if not mx_value and mx_records:
            first_mx = mx_records[0] if mx_records else {}
            host = first_mx.get("host") if isinstance(first_mx, dict) else None
            if host:
                mx_value = str(host)
                record_map["mx_record"] = str(host)
            if isinstance(first_mx, dict) and "priority" in first_mx:
                record_map["mx_priority"] = str(first_mx["priority"])
        if a_records:
            record_map["a_records"] = str(a_records)
        if not domain or not mx_value:
            return {"success": False, "error": "Both domain and mx_record are required"}

        normalized_records = {
            "mx_record": str(mx_value),
            "txt_record": str(record_map.get("txt_record") or record_map.get("txt") or ""),
            "provider": self.active_api_client_name or "",
        }
        self.domain_dns_configs[domain] = normalized_records

        if self.api_client and hasattr(self.api_client, "configure_dns"):
            try:
                self.api_client.configure_dns(domain, normalized_records)  # type: ignore[attr-defined]
            except Exception as exc:
                return {
                    "success": False,
                    "error": str(exc),
                    "domain": domain,
                    "dns": normalized_records,
                }

        return {"success": True, "domain": domain, "dns": normalized_records}
    
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

    # Backward-compat helper used by older scripts
    def set_monthly_budget(self, monthly_budget: float):
        self.monthly_budget = float(monthly_budget)
        self._config["monthly_budget"] = self.monthly_budget


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
