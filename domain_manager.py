"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import logging
import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def _mask_secret(value: Optional[str], visible_chars: int = 4) -> str:
    """Mask a secret value while preserving the final few characters."""
    if not value:
        return ""

    if len(value) <= visible_chars:
        return "*" * len(value)

    return f"{'*' * (len(value) - visible_chars)}{value[-visible_chars:]}"


def _normalize_price(price: Any, default: float = 999.0) -> float:
    """
    Convert registrar price values to float.
    Supports numeric values and strings with common currency symbols.
    """
    if isinstance(price, (int, float)):
        return float(price)

    if isinstance(price, str):
        cleaned = (
            price.strip()
            .replace("$", "")
            .replace("€", "")
            .replace("£", "")
            .replace(",", "")
        )
        try:
            return float(cleaned)
        except ValueError:
            return default

    return default


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


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """

    def __init__(
        self,
        api_client: Optional[DomainAPIClient] = None,
        monthly_budget: float = 50.0,
    ):
        self.api_client: Optional[DomainAPIClient] = None
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_client_name: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False

        if api_client:
            self.set_api_client(api_client)

    def _get_active_client(self) -> Optional[DomainAPIClient]:
        """Return the currently active API client."""
        if self.active_client_name and self.active_client_name in self.api_clients:
            self.api_client = self.api_clients[self.active_client_name]
            return self.api_client

        self.api_client = None
        return None

    def set_api_client(
        self,
        api_client: DomainAPIClient,
        name: str = "primary",
        activate: bool = True,
    ) -> None:
        """Set or replace an API client."""
        self.api_clients[name] = api_client
        if activate or not self.active_client_name:
            self.active_client_name = name
        self._get_active_client()

    def add_api_client(self, name: str, api_client: DomainAPIClient) -> None:
        """Register an additional API client."""
        self.set_api_client(api_client, name=name, activate=False)

    def set_active_client(self, name: str) -> bool:
        """Switch active registrar client by name."""
        if name not in self.api_clients:
            return False

        self.active_client_name = name
        self._get_active_client()
        return True

    def set_test_mode(self, enabled: bool) -> None:
        """Enable or disable purchase simulation mode."""
        self.test_mode = bool(enabled)

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 50.0,
        registrar: str = "porkbun",
    ) -> None:
        """
        Configure domain rotation manager from simple credentials.
        Currently supports Porkbun and can be extended with more registrars.
        """
        registrar_key = registrar.strip().lower()
        if registrar_key != "porkbun":
            raise ValueError(f"Unsupported registrar: {registrar}")

        self.monthly_budget = float(monthly_budget)
        self.set_api_client(
            PorkbunAPIClient(api_key, secret_key),
            name=registrar_key,
            activate=True,
        )

    def get_config(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """Return active manager configuration."""
        active_client = self._get_active_client()
        config: Dict[str, Any] = {
            "registrar": self.active_client_name,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode,
        }

        if isinstance(active_client, DomainAPIClient):
            config["api_key"] = (
                _mask_secret(active_client.api_key)
                if mask_secrets
                else active_client.api_key
            )
            config["secret_key"] = (
                _mask_secret(active_client.api_secret)
                if mask_secrets
                else active_client.api_secret
            )

        return config

    def export_state(self) -> Dict[str, Any]:
        """Serialize manager state for persistence."""
        serialized_domains: List[Dict[str, Any]] = []
        for domain in self.owned_domains:
            item = dict(domain)
            purchased_at = item.get("purchased_at")
            expires_at = item.get("expires_at")

            if isinstance(purchased_at, datetime):
                item["purchased_at"] = purchased_at.isoformat()
            if isinstance(expires_at, datetime):
                item["expires_at"] = expires_at.isoformat()

            serialized_domains.append(item)

        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
            "test_mode": self.test_mode,
            "active_client": self.active_client_name,
        }

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Parse datetime from state payload."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def import_state(self, state: Optional[Dict[str, Any]]) -> None:
        """Load manager state from a persisted payload."""
        if not state:
            return

        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))
        self.current_spending = float(state.get("current_spending", 0.0))
        self.active_domain = state.get("active_domain")
        self.test_mode = bool(state.get("test_mode", False))

        imported_domains = []
        for item in state.get("owned_domains", []):
            if not isinstance(item, dict):
                continue
            parsed = dict(item)
            parsed_purchased = self._parse_datetime(parsed.get("purchased_at"))
            parsed_expiry = self._parse_datetime(parsed.get("expires_at"))
            if parsed_purchased:
                parsed["purchased_at"] = parsed_purchased
            if parsed_expiry:
                parsed["expires_at"] = parsed_expiry
            imported_domains.append(parsed)

        self.owned_domains = imported_domains

        saved_client = state.get("active_client")
        if isinstance(saved_client, str) and saved_client in self.api_clients:
            self.set_active_client(saved_client)
        else:
            self._get_active_client()

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
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
        api_client = self._get_active_client()
        if not api_client:
            logger.error("No API client configured")
            return None

        # Try cheap TLDs
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]

        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)

            result = api_client.search_domain(domain)
            if result.get("available"):
                price = _normalize_price(result.get("price", 999))
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }

            logger.debug("Attempt %s failed for domain %s", attempt + 1, domain)

        return None

    def search_cheap_domains(
        self,
        max_price: float = 5.0,
        limit: int = 5,
        tlds: Optional[List[str]] = None,
        max_attempts: int = 25,
    ) -> List[Dict]:
        """
        Search for multiple cheap available domains.
        Returns up to `limit` unique domain candidates.
        """
        results: List[Dict] = []
        seen = set()
        attempts = 0

        while len(results) < limit and attempts < max_attempts:
            attempts += 1
            domain_info = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=tlds,
            )
            if not domain_info:
                continue

            domain_name = domain_info.get("domain")
            if not domain_name or domain_name in seen:
                continue

            seen.add(domain_name)
            results.append(domain_info)

        return results

    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        api_client = self._get_active_client()
        if not api_client and not self.test_mode:
            logger.error("No API client configured")
            return False
        normalized_price = _normalize_price(price)

        # Check budget
        if self.current_spending + normalized_price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${normalized_price}, Budget: ${self.monthly_budget}")
            return False

        # Attempt purchase (or simulate in test mode)
        if self.test_mode:
            result = {
                "success": True,
                "domain": domain,
                "message": "Simulated purchase (test mode)",
                "order_id": "test-mode",
            }
        else:
            result = api_client.purchase_domain(domain, years=1)

        if result.get("success"):
            now = datetime.now()
            self.current_spending += normalized_price
            self.owned_domains.append({
                "domain": domain,
                "price": normalized_price,
                "purchased_at": now,
                "expires_at": now + timedelta(days=365),
                "registrar": self.active_client_name or "unknown",
                "order_id": result.get("order_id"),
                "test_mode": self.test_mode,
            })

            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain

            logger.info("Successfully purchased domain: %s for $%s", domain, normalized_price)
            return True
        logger.error("Failed to purchase domain: %s", result.get("message"))
        return False

    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        result = self.rotate_to_new_domain()
        if not result.get("success"):
            return None
        return result.get("domain")

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Rotate to a new domain and return structured result payload.
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {
                "success": False,
                "error": "Could not find available cheap domain",
            }

        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"],
        )

        if success:
            self.active_domain = domain_info["domain"]
            return {
                "success": True,
                "domain": self.active_domain,
                "cost": domain_info["price"],
                "test_mode": self.test_mode,
            }

        return {
            "success": False,
            "error": "Purchase failed or budget exceeded",
            "domain": domain_info.get("domain"),
            "cost": domain_info.get("price"),
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


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
