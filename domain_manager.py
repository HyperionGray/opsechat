"""
Domain management and API integration.

Supports automated domain purchasing for burner email rotation and exposes
both a Python API and a lightweight CLI (`python -m domain_manager`).
"""
import argparse
import json
import logging
import os
import random
import string
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now()


def _to_float_price(value: Any, fallback: float = 999.0) -> float:
    """Convert registrar price values to float safely."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace("€", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return fallback
    return fallback


class DomainAPIClient(ABC):
    """Base class for domain registrar API clients."""

    provider_name = "base"

    def __init__(self, api_key: str = "", api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    def search_domain(self, domain: str) -> Dict[str, Any]:
        """Search if a domain is available."""
        ...

    @abstractmethod
    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        """Purchase a domain."""
        ...

    @abstractmethod
    def get_pricing(self, tld: str) -> Dict[str, Any]:
        """Get pricing for a TLD."""
        ...

    def list_domains(self) -> List[str]:
        """Return owned domains when provider supports listing."""
        return []


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management
    https://porkbun.com/api/json/v3/documentation
    """
    
    provider_name = "porkbun"
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


class MockRegistrarAPIClient(DomainAPIClient):
    """
    Local mock registrar for offline testing and dry-runs.
    Useful in automation where live registrar credentials are unavailable.
    """

    provider_name = "mock"

    def __init__(self):
        super().__init__(api_key="mock", api_secret="mock")
        self._owned: Dict[str, Dict[str, Any]] = {}
        self._tld_pricing = {
            "xyz": 1.49,
            "club": 2.49,
            "online": 1.99,
            "site": 1.79,
            "website": 1.69,
            "com": 9.99,
        }

    def search_domain(self, domain: str) -> Dict[str, Any]:
        tld = domain.split(".")[-1] if "." in domain else "com"
        return {
            "domain": domain,
            "available": domain not in self._owned,
            "price": self._tld_pricing.get(tld, 4.99),
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1) -> Dict[str, Any]:
        if domain in self._owned:
            return {
                "success": False,
                "domain": domain,
                "message": "Domain already owned",
            }

        self._owned[domain] = {
            "domain": domain,
            "years": years,
            "purchased_at": _now().isoformat(),
        }
        return {
            "success": True,
            "domain": domain,
            "message": "Mock purchase successful",
            "order_id": f"mock-{len(self._owned)}",
        }

    def get_pricing(self, tld: str = "com") -> Dict[str, Any]:
        price = self._tld_pricing.get(tld, 4.99)
        return {
            "tld": tld,
            "registration": price,
            "renewal": price,
            "transfer": price,
            "currency": "USD",
        }

    def list_domains(self) -> List[str]:
        return sorted(self._owned.keys())


class _BudgetAdapter:
    """Backward-compatible budget helper exposed as manager.budget_manager."""

    def __init__(self, manager: "DomainRotationManager"):
        self._manager = manager

    @property
    def monthly_budget(self) -> float:
        return self._manager.monthly_budget

    def set_monthly_budget(self, amount: float):
        self._manager.monthly_budget = float(amount)

    def get_month_spending(self) -> float:
        return self._manager.current_spending

    def get_remaining_budget(self) -> float:
        return self._manager.monthly_budget - self._manager.current_spending


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_clients: Dict[str, DomainAPIClient] = {}
        self.active_provider: Optional[str] = None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.test_mode = False
        self._config: Dict[str, Any] = {
            "provider": "porkbun",
            "monthly_budget": monthly_budget,
            "api_key": "",
            "secret_key": "",
        }
        self.budget_manager = _BudgetAdapter(self)

        if api_client:
            provider = getattr(api_client, "provider_name", "default")
            self.add_api_client(provider, api_client, set_active=True)

    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        provider = getattr(api_client, "provider_name", "default")
        self.add_api_client(provider, api_client, set_active=True)

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient, set_active: bool = False):
        """Register an API client for a provider."""
        key = provider_name.lower()
        self.api_clients[key] = api_client
        if set_active or not self.active_provider:
            self.active_provider = key
            self.api_client = api_client
        logger.info("Registered domain provider: %s", key)

    def set_active_provider(self, provider_name: str) -> bool:
        """Set which registered provider is used for operations."""
        key = provider_name.lower()
        client = self.api_clients.get(key)
        if not client:
            logger.warning("Provider not registered: %s", provider_name)
            return False
        self.active_provider = key
        self.api_client = client
        return True

    def get_active_client(self) -> Optional[DomainAPIClient]:
        """Return currently active provider client."""
        if self.api_client:
            return self.api_client
        if self.active_provider:
            return self.api_clients.get(self.active_provider)
        return None

    def set_test_mode(self, enabled: bool):
        """Enable dry-run purchase mode."""
        self.test_mode = bool(enabled)

    def configure(
        self,
        api_key: str = "",
        secret_key: str = "",
        monthly_budget: float = 10.0,
        provider: str = "porkbun",
    ):
        """
        Configure domain manager from UI/API inputs.
        """
        provider_key = provider.lower()
        self.monthly_budget = float(monthly_budget)
        self._config.update(
            {
                "provider": provider_key,
                "monthly_budget": self.monthly_budget,
                "api_key": api_key,
                "secret_key": secret_key,
            }
        )

        if provider_key == "porkbun":
            if not api_key or not secret_key:
                raise ValueError("Porkbun provider requires api_key and secret_key")
            self.add_api_client(provider_key, PorkbunAPIClient(api_key, secret_key), set_active=True)
        elif provider_key == "mock":
            self.add_api_client(provider_key, MockRegistrarAPIClient(), set_active=True)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def get_config(self) -> Dict[str, Any]:
        """Get redacted configuration for rendering in UI."""
        api_key = self._config.get("api_key", "")
        secret_key = self._config.get("secret_key", "")
        return {
            "provider": self._config.get("provider"),
            "monthly_budget": self.monthly_budget,
            "api_key_configured": bool(api_key),
            "secret_key_configured": bool(secret_key),
            "api_key": f"{'*' * 8}{api_key[-4:]}" if api_key else "",
            "secret_key": f"{'*' * 8}{secret_key[-4:]}" if secret_key else "",
            "active_provider": self.active_provider,
            "test_mode": self.test_mode,
            "providers": sorted(self.api_clients.keys()),
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
        """Backward-compatible alias."""
        return self.generate_random_domain(tld=tld, length=length)

    def generate_domain_from_pattern(self, pattern: str, tld: str = "xyz") -> str:
        """
        Generate domain from a simple pattern template.
        Supported placeholders: {timestamp}, {random}, {date}
        """
        name = pattern
        name = name.replace("{timestamp}", str(int(_now().timestamp())))
        name = name.replace("{date}", _now().strftime("%Y%m%d"))
        name = name.replace("{random}", ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4)))
        # Keep registrar-safe chars.
        safe = ''.join(ch if ch.isalnum() or ch == "-" else "-" for ch in name.lower()).strip("-")
        safe = safe[:40] or self.generate_random_domain_name(8, tld).split(".", 1)[0]
        return f"{safe}.{tld}"

    def find_cheap_available_domain(self, max_price: float = 5.0, max_attempts: int = 10) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        client = self.get_active_client()
        if not client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = client.search_domain(domain)
            
            if result.get("available"):
                price = _to_float_price(result.get("price", 999))
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
        client = self.get_active_client()
        if not client:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        if self.test_mode:
            result = {
                "success": True,
                "message": "Test mode simulated purchase",
                "order_id": "test-mode",
            }
        else:
            # Attempt purchase
            result = client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "purchased_at": _now(),
                "expires_at": _now() + timedelta(days=365),
                "provider": self.active_provider or getattr(client, "provider_name", "unknown"),
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

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 5,
        max_attempts_per_tld: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search and return multiple cheap available domains.
        """
        tlds = tlds or ["xyz", "club", "online", "site", "website"]
        found: List[Dict[str, Any]] = []
        seen = set()

        for tld in tlds:
            for _ in range(max_attempts_per_tld):
                client = self.get_active_client()
                if not client:
                    return found
                candidate = self.generate_random_domain(tld=tld)
                raw = client.search_domain(candidate)
                if not raw.get("available"):
                    continue
                price = _to_float_price(raw.get("price", 999))
                if price > max_price:
                    continue
                info = {"domain": candidate, "price": price, "tld": tld}
                if info["domain"] in seen:
                    continue
                seen.add(info["domain"])
                found.append(info)
                if len(found) >= limit:
                    return found
        return found

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict[str, Any]:
        """
        Structured rotation helper for API/CLI consumers.
        """
        info = self.find_cheap_available_domain(max_price=max_price)
        if not info:
            return {"success": False, "error": "No cheap available domain found"}

        ok = self.purchase_domain_if_budget_allows(info["domain"], info["price"])
        if not ok:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded",
                "domain": info["domain"],
                "price": info["price"],
            }

        self.active_domain = info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "cost": info["price"],
            "provider": self.active_provider,
        }

    def configure_domain_dns(
        self,
        domain: str,
        mx_records: Optional[List[Dict[str, Any]]] = None,
        a_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Placeholder DNS configuration API.
        Returns explicit unsupported response until provider DNS APIs are wired.
        """
        return {
            "success": False,
            "domain": domain,
            "message": "DNS configuration not implemented for current provider",
            "mx_records": mx_records or [],
            "a_records": a_records or [],
        }

    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain

    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return self.owned_domains

    def list_provider_domains(self) -> List[str]:
        """List domains known by active provider."""
        client = self.get_active_client()
        if not client:
            return []
        return client.list_domains()

    def get_budget_status(self) -> Dict:
        """Get budget information"""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }

    @staticmethod
    def _serialize_datetime(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    @staticmethod
    def _deserialize_datetime(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value
        return value

    def export_state(self) -> Dict[str, Any]:
        """Export manager state for persistence."""
        owned_domains = []
        for entry in self.owned_domains:
            owned_domains.append({k: self._serialize_datetime(v) for k, v in entry.items()})

        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "owned_domains": owned_domains,
            "active_provider": self.active_provider,
            "test_mode": self.test_mode,
        }

    def import_state(self, state: Dict[str, Any]):
        """Import manager state from persistent storage."""
        self.monthly_budget = float(state.get("monthly_budget", self.monthly_budget))
        self.current_spending = float(state.get("current_spending", self.current_spending))
        self.active_domain = state.get("active_domain", self.active_domain)
        self.test_mode = bool(state.get("test_mode", self.test_mode))

        raw_owned = state.get("owned_domains", [])
        loaded = []
        for entry in raw_owned:
            loaded.append({k: self._deserialize_datetime(v) for k, v in entry.items()})
        self.owned_domains = loaded

        provider = state.get("active_provider")
        if provider:
            self.set_active_provider(provider)


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Domain rotation manager CLI")
    parser.add_argument("--provider", choices=["porkbun", "mock"], default="porkbun")
    parser.add_argument("--api-key", default=os.getenv("PORKBUN_API_KEY", ""))
    parser.add_argument("--secret-key", default=os.getenv("PORKBUN_SECRET_KEY", ""))
    parser.add_argument("--monthly-budget", type=float, default=float(os.getenv("DOMAIN_BUDGET", "50")))
    parser.add_argument(
        "--state-file",
        default=str(Path.home() / ".opsechat" / "domain_manager_state.json"),
        help="State file for budget/domain history persistence",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search cheap available domains")
    search.add_argument("--tld", action="append", default=[])
    search.add_argument("--max-price", type=float, default=5.0)
    search.add_argument("--limit", type=int, default=5)

    purchase = subparsers.add_parser("purchase", help="Purchase a specific domain")
    purchase.add_argument("--domain", required=True)
    purchase.add_argument("--price", type=float, default=None)

    dns = subparsers.add_parser("dns", help="Configure DNS records (provider-dependent)")
    dns.add_argument("--domain", required=True)
    dns.add_argument("--mx", action="append", default=[], help="MX host value, repeatable")
    dns.add_argument("--a", action="append", default=[], help="A record IP, repeatable")

    rotate = subparsers.add_parser("rotate", help="Find and rotate to new domain")
    rotate.add_argument("--max-price", type=float, default=5.0)

    budget = subparsers.add_parser("budget", help="Budget operations")
    budget_sub = budget.add_subparsers(dest="budget_cmd", required=True)
    budget_sub.add_parser("status", help="Show budget status")
    bset = budget_sub.add_parser("set", help="Set monthly budget")
    bset.add_argument("--amount", type=float, required=True)

    subparsers.add_parser("list", help="List domains in local state")
    subparsers.add_parser("provider-list", help="List domains from active provider API")

    return parser


def _load_manager_state_file(path: str) -> Dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load state file: %s", path)
        return {}


def _save_manager_state_file(path: str, data: Dict[str, Any]):
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(state_path, 0o600)


def _print_json(data: Dict[str, Any]):
    print(json.dumps(data, indent=2, default=str))


def main():
    parser = _build_cli_parser()
    args = parser.parse_args()

    manager = DomainRotationManager(monthly_budget=args.monthly_budget)

    # Configure provider
    if args.provider == "mock":
        manager.configure(provider="mock", monthly_budget=args.monthly_budget)
    else:
        if not args.api_key or not args.secret_key:
            parser.error("Porkbun provider requires --api-key/--secret-key or env vars")
        manager.configure(
            provider="porkbun",
            api_key=args.api_key,
            secret_key=args.secret_key,
            monthly_budget=args.monthly_budget,
        )

    persisted = _load_manager_state_file(args.state_file)
    if persisted:
        manager.import_state(persisted)

    if args.command == "search":
        tlds = args.tld if args.tld else None
        result = {"domains": manager.search_cheap_domains(tlds=tlds, max_price=args.max_price, limit=args.limit)}
        _print_json(result)
    elif args.command == "purchase":
        price = args.price
        if price is None:
            availability = manager.get_active_client().search_domain(args.domain)
            if not availability.get("available"):
                _print_json({"success": False, "error": "Domain is unavailable", "domain": args.domain})
                return
            price = _to_float_price(availability.get("price"))
        success = manager.purchase_domain_if_budget_allows(args.domain, float(price))
        _print_json({"success": success, "domain": args.domain, "price": price})
    elif args.command == "dns":
        mx_records = [{"priority": 10, "host": host} for host in args.mx]
        a_records = [{"host": "@", "ip": ip} for ip in args.a]
        _print_json(
            manager.configure_domain_dns(
                domain=args.domain,
                mx_records=mx_records,
                a_records=a_records,
            )
        )
    elif args.command == "rotate":
        _print_json(manager.rotate_to_new_domain(max_price=args.max_price))
    elif args.command == "budget":
        if args.budget_cmd == "status":
            _print_json(manager.get_budget_status())
        elif args.budget_cmd == "set":
            manager.budget_manager.set_monthly_budget(args.amount)
            _print_json({"success": True, "monthly_budget": manager.monthly_budget})
    elif args.command == "list":
        _print_json({"domains": manager.get_owned_domains()})
    elif args.command == "provider-list":
        _print_json({"domains": manager.list_provider_domains()})

    _save_manager_state_file(args.state_file, manager.export_state())


if __name__ == "__main__":
    main()


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
