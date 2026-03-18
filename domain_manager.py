"""
Domain management and API integration.
Supports automated domain purchasing for burner email rotation.
"""
import logging
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import requests

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """
    Base class for domain registrar API clients.
    """

    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        # Backward-compatible alias used by some older scripts.
        self.secret_key = api_secret

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search if domain is available."""
        raise NotImplementedError

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase domain."""
        raise NotImplementedError

    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing for TLD."""
        raise NotImplementedError


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management.
    https://porkbun.com/api/json/v3/documentation
    """

    BASE_URL = "https://porkbun.com/api/json/v3"

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()

    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request."""
        url = f"{self.BASE_URL}/{endpoint}"

        payload = {
            "apikey": self.api_key,
            "secretapikey": self.api_secret,
        }

        if data:
            payload.update(data)

        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.error("Porkbun API request failed: %s", exc)
            return {"status": "ERROR", "message": str(exc)}

    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Check if domain is available."""
        result = self._make_request("domain/check", {"domain": domain})

        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and result.get("isAvailable", False),
            "price": result.get("price"),
            "currency": result.get("currency", "USD"),
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """
        Purchase domain.
        Note: This actually purchases the domain and charges your account.
        """
        result = self._make_request("domain/create", {"domain": domain, "years": years})

        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId"),
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        """Get pricing for TLD."""
        result = self._make_request("pricing/get", {"tld": tld})

        if result.get("status") == "SUCCESS":
            pricing = result.get("pricing", {})
            return {
                "tld": tld,
                "registration": pricing.get("registration"),
                "renewal": pricing.get("renewal"),
                "transfer": pricing.get("transfer"),
                "currency": "USD",
            }

        return {}

    def list_domains(self) -> List[str]:
        """List owned domains."""
        result = self._make_request("domain/listAll")

        if result.get("status") == "SUCCESS":
            domains = result.get("domains", [])
            return [domain_item.get("domain") for domain_item in domains if domain_item.get("domain")]

        return []


class DomainBudgetManager:
    """Compatibility wrapper used by older docs/scripts."""

    def __init__(self, manager: "DomainRotationManager"):
        self._manager = manager

    @property
    def monthly_budget(self) -> float:
        return self._manager.monthly_budget

    def set_monthly_budget(self, amount: float) -> None:
        self._manager.set_monthly_budget(amount)

    def get_month_spending(self) -> float:
        return self._manager.current_spending

    def get_remaining_budget(self) -> float:
        return max(self._manager.monthly_budget - self._manager.current_spending, 0.0)


class DomainRotationManager:
    """
    Manage domain rotation for burner emails.
    Automatically purchase cheap domains and rotate them.
    """

    def __init__(self, api_client: Optional[DomainAPIClient] = None, monthly_budget: float = 50.0):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict[str, Any]] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False
        self.provider = "porkbun"
        self._api_key: Optional[str] = None
        self._secret_key: Optional[str] = None
        self.cheap_tlds = ["xyz", "club", "online", "site", "website"]
        self.budget_manager = DomainBudgetManager(self)

    @staticmethod
    def _mask_secret(secret: Optional[str]) -> str:
        if not secret:
            return ""
        if len(secret) <= 4:
            return "*" * len(secret)
        return f"{'*' * (len(secret) - 4)}{secret[-4:]}"

    @staticmethod
    def _parse_price(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace("$", "").replace("€", "").replace("£", "").replace(",", "")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    @staticmethod
    def _format_timestamp(value: Any) -> str:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
            return value.isoformat(timespec="seconds").replace("+00:00", "Z")
        if isinstance(value, str) and value:
            return value
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _record_purchase(self, domain: str, price: float, currency: str = "USD") -> None:
        now = datetime.now(timezone.utc)
        self.current_spending += price
        self.owned_domains.append(
            {
                "domain": domain,
                "price": float(price),
                "currency": currency,
                "purchased_at": now.isoformat(timespec="seconds") + "Z",
                "expires_at": (now + timedelta(days=365)).isoformat(timespec="seconds") + "Z",
            }
        )
        if not self.active_domain:
            self.active_domain = domain

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 50.0,
        provider: str = "porkbun",
    ) -> Dict[str, Any]:
        """
        Configure registrar credentials and budget.
        """
        provider_name = (provider or "porkbun").lower()
        if provider_name != "porkbun":
            raise ValueError(f"Unsupported domain provider: {provider_name}")

        if not api_key or not secret_key:
            raise ValueError("Both api_key and secret_key are required")

        self.provider = provider_name
        self._api_key = api_key
        self._secret_key = secret_key
        self.api_client = PorkbunAPIClient(api_key, secret_key)
        self.set_monthly_budget(monthly_budget)
        return self.get_config(mask_secrets=True)

    def get_config(self, mask_secrets: bool = True) -> Dict[str, Any]:
        """Return current domain manager configuration."""
        api_key = self._api_key if self._api_key is not None else getattr(self.api_client, "api_key", None)
        secret_key = self._secret_key if self._secret_key is not None else getattr(self.api_client, "api_secret", None)

        if mask_secrets:
            api_key = self._mask_secret(api_key)
            secret_key = self._mask_secret(secret_key)

        return {
            "provider": self.provider,
            "configured": self.api_client is not None,
            "api_key": api_key or "",
            "secret_key": secret_key or "",
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "test_mode": self.test_mode,
        }

    def set_api_client(self, api_client: DomainAPIClient) -> None:
        """Set the domain API client."""
        self.api_client = api_client

    def set_monthly_budget(self, amount: float) -> None:
        """Set monthly budget and validate value."""
        try:
            budget = float(amount)
        except (TypeError, ValueError) as exc:
            raise ValueError("monthly_budget must be numeric") from exc
        if budget <= 0:
            raise ValueError("monthly_budget must be greater than zero")
        self.monthly_budget = budget

    def set_test_mode(self, enabled: bool) -> None:
        """Enable or disable simulated purchasing mode."""
        self.test_mode = bool(enabled)

    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name.
        Uses cheap TLDs like .xyz, .club, .online.
        """
        chars = string.ascii_lowercase + string.digits
        random_name = "".join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    # Backward-compatible aliases used by docs/tests.
    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        return self.generate_random_domain(tld=tld, length=length)

    def generate_domain_name(self, tld: str = "xyz", length: int = 8) -> str:
        return self.generate_random_domain(tld=tld, length=length)

    def find_cheap_available_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        tlds: Optional[Sequence[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a cheap available domain.
        Returns domain info or None.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return None

        candidate_tlds = [item.strip(".") for item in (tlds or self.cheap_tlds) if item]
        if not candidate_tlds:
            candidate_tlds = self.cheap_tlds

        for _ in range(max_attempts):
            tld = random.choice(candidate_tlds)
            domain = self.generate_random_domain(tld)

            try:
                result = self.api_client.search_domain(domain)
            except Exception as exc:
                logger.warning("Domain search failed for %s: %s", domain, exc)
                continue

            if result.get("available"):
                parsed_price = self._parse_price(result.get("price"))
                if parsed_price is None:
                    continue
                if parsed_price <= max_price:
                    return {
                        "domain": result.get("domain", domain),
                        "price": parsed_price,
                        "tld": tld,
                        "currency": result.get("currency", "USD"),
                    }
        return None

    def search_cheap_domains(
        self,
        tlds: Optional[Sequence[str]] = None,
        max_price: float = 5.0,
        limit: int = 5,
        max_attempts: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        Search for multiple cheap available domains.
        """
        if limit <= 0:
            return []
        discovered: List[Dict[str, Any]] = []
        seen_domains = set()
        attempts = 0
        total_attempts = max(max_attempts, limit)

        while len(discovered) < limit and attempts < total_attempts:
            attempts += 1
            found = self.find_cheap_available_domain(max_price=max_price, max_attempts=1, tlds=tlds)
            if not found:
                continue
            domain = found.get("domain")
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            discovered.append(found)

        return discovered

    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget.
        Returns True on success.
        """
        parsed_price = self._parse_price(price)
        if parsed_price is None:
            logger.error("Invalid domain price: %s", price)
            return False

        if self.current_spending + parsed_price > self.monthly_budget:
            logger.warning(
                "Budget exceeded. Current: $%s, Requested: $%s, Budget: $%s",
                self.current_spending,
                parsed_price,
                self.monthly_budget,
            )
            return False

        if self.test_mode:
            self._record_purchase(domain=domain, price=parsed_price)
            self.active_domain = domain
            logger.info("Test mode enabled: simulated domain purchase for %s", domain)
            return True

        if not self.api_client:
            logger.error("No API client configured")
            return False

        result = self.api_client.purchase_domain(domain, years=1)

        if result.get("success"):
            self._record_purchase(domain=domain, price=parsed_price)
            self.active_domain = domain
            logger.info("Successfully purchased domain: %s for $%s", domain, parsed_price)
            return True

        logger.error("Failed to purchase domain: %s", result.get("message"))
        return False

    def rotate_to_new_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        tlds: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """
        Rotate to a new domain and return detailed result data.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price, max_attempts=max_attempts, tlds=tlds)
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {"success": False, "error": "Could not find available cheap domain within budget"}

        success = self.purchase_domain_if_budget_allows(domain_info["domain"], domain_info["price"])
        if not success:
            return {
                "success": False,
                "error": "Domain purchase failed or budget exceeded",
                "domain": domain_info["domain"],
                "cost": domain_info["price"],
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "cost": domain_info["price"],
            "currency": domain_info.get("currency", "USD"),
            "remaining_budget": max(self.monthly_budget - self.current_spending, 0.0),
            "test_mode": self.test_mode,
        }

    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain and return only the domain string.
        """
        result = self.rotate_to_new_domain()
        if result.get("success"):
            return result.get("domain")
        return None

    def import_state(self, state: Dict[str, Any]) -> None:
        """Import manager state from a dictionary."""
        if "monthly_budget" in state:
            self.set_monthly_budget(state["monthly_budget"])

        spending = self._parse_price(state.get("current_spending", 0.0))
        self.current_spending = spending if spending is not None else 0.0
        self.active_domain = state.get("active_domain")
        self.test_mode = bool(state.get("test_mode", False))

        imported_domains = state.get("owned_domains", []) or []
        normalized_domains: List[Dict[str, Any]] = []
        for entry in imported_domains:
            if not isinstance(entry, dict):
                continue
            price = self._parse_price(entry.get("price"))
            normalized_domains.append(
                {
                    "domain": entry.get("domain", ""),
                    "price": price if price is not None else 0.0,
                    "currency": entry.get("currency", "USD"),
                    "purchased_at": self._format_timestamp(entry.get("purchased_at")),
                    "expires_at": self._format_timestamp(entry.get("expires_at")),
                }
            )
        self.owned_domains = normalized_domains

        if not self.active_domain and self.owned_domains:
            self.active_domain = self.owned_domains[0].get("domain")

    def export_state(self) -> Dict[str, Any]:
        """Export manager state as JSON-safe dictionary."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": self.owned_domains,
            "active_domain": self.active_domain,
            "test_mode": self.test_mode,
        }

    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain."""
        return self.active_domain

    def get_owned_domains(self) -> List[Dict[str, Any]]:
        """Get list of owned domains."""
        return self.owned_domains

    def get_budget_status(self) -> Dict[str, Any]:
        """Get budget information."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": max(self.monthly_budget - self.current_spending, 0.0),
            "domains_owned": len(self.owned_domains),
        }


# Global domain rotation manager.
domain_rotation_manager = DomainRotationManager()
