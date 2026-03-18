"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import argparse
import json
import os
import requests
import random
import string
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional
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
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    @staticmethod
    def _normalize_price(price: object) -> Optional[float]:
        """Normalize API price values into floats."""
        if price is None:
            return None

        if isinstance(price, (int, float)):
            return float(price)

        if isinstance(price, str):
            cleaned = (
                price.strip()
                .replace("$", "")
                .replace("€", "")
                .replace(",", "")
            )
            try:
                return float(cleaned)
            except ValueError:
                logger.warning("Could not parse price value '%s'", price)
                return None

        logger.warning("Unsupported price type: %s", type(price).__name__)
        return None

    @staticmethod
    def _parse_datetime(value: object) -> Optional[datetime]:
        """Parse datetime values from persisted state."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                logger.warning("Could not parse datetime value '%s'", value)
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
        tlds: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs by default unless callers provide a custom set.
        cheap_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        if not cheap_tlds:
            logger.error("No TLDs configured for domain search")
            return None
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = self._normalize_price(result.get("price"))
                if price is None:
                    continue

                if price <= max_price:
                    return {
                        "domain": result.get("domain", domain),
                        "price": price,
                        "tld": tld
                    }
        
        return None

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search for multiple cheap domains.
        Returns up to `limit` unique domain results.
        """
        results: List[Dict] = []
        seen_domains = set()

        for _ in range(max(limit, 0)):
            domain_info = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
                tlds=tlds,
            )
            if not domain_info:
                continue

            domain_name = domain_info.get("domain")
            if not domain_name or domain_name in seen_domains:
                continue

            seen_domains.add(domain_name)
            results.append(domain_info)

        return results
    
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
    
    def rotate_domain(
        self,
        max_price: float = 5.0,
        max_attempts: int = 10,
        tlds: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=max_attempts,
            tlds=tlds,
        )
        
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

    def rotate_to_new_domain(self) -> Optional[str]:
        """
        Backward-compatible alias used by older docs/scripts.
        """
        return self.rotate_domain()

    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        """
        Backward-compatible alias used by older docs/scripts.
        """
        return self.generate_random_domain(tld=tld, length=length)
    
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

    def set_monthly_budget(self, amount: float):
        """Set monthly budget for purchases."""
        if amount < 0:
            raise ValueError("Monthly budget cannot be negative")
        self.monthly_budget = float(amount)

    def export_state(self) -> Dict:
        """Export manager state in JSON-serializable format."""
        serialized_domains: List[Dict] = []
        for domain in self.owned_domains:
            entry = dict(domain)

            purchased_at = self._parse_datetime(entry.get("purchased_at"))
            expires_at = self._parse_datetime(entry.get("expires_at"))

            entry["purchased_at"] = purchased_at.isoformat() if purchased_at else None
            entry["expires_at"] = expires_at.isoformat() if expires_at else None
            serialized_domains.append(entry)

        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain,
        }

    def load_state(self, state: Dict):
        """Load manager state from persisted JSON-style dictionary."""
        if not isinstance(state, dict):
            logger.warning("Invalid manager state type: %s", type(state).__name__)
            return

        monthly_budget = state.get("monthly_budget")
        if monthly_budget is not None:
            normalized_budget = self._normalize_price(monthly_budget)
            if normalized_budget is not None:
                self.monthly_budget = normalized_budget

        current_spending = state.get("current_spending")
        if current_spending is not None:
            normalized_spending = self._normalize_price(current_spending)
            if normalized_spending is not None:
                self.current_spending = normalized_spending

        loaded_domains: List[Dict] = []
        for domain in state.get("owned_domains", []):
            if not isinstance(domain, dict):
                continue

            entry = dict(domain)
            entry["purchased_at"] = self._parse_datetime(entry.get("purchased_at"))
            entry["expires_at"] = self._parse_datetime(entry.get("expires_at"))
            loaded_domains.append(entry)

        self.owned_domains = loaded_domains

        active_domain = state.get("active_domain")
        self.active_domain = active_domain if isinstance(active_domain, str) else None


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()


def _build_cli_parser() -> argparse.ArgumentParser:
    """Build CLI parser for `python -m domain_manager` usage."""
    parser = argparse.ArgumentParser(
        description="Domain management CLI for OpSecChat",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("PORKBUN_API_KEY"),
        help="Porkbun API key (defaults to PORKBUN_API_KEY env var)",
    )
    parser.add_argument(
        "--api-secret",
        default=os.getenv("PORKBUN_SECRET_KEY"),
        help="Porkbun API secret (defaults to PORKBUN_SECRET_KEY env var)",
    )
    parser.add_argument(
        "--state-file",
        default=os.getenv("DOMAIN_MANAGER_STATE_FILE", ".domain-manager-state.json"),
        help="Path to state file for persisted budget/domain history",
    )
    parser.add_argument(
        "--monthly-budget",
        type=float,
        default=None,
        help="Override monthly budget for this run",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Find a cheap available domain")
    search_parser.add_argument("--max-price", type=float, default=5.0)
    search_parser.add_argument("--max-attempts", type=int, default=10)
    search_parser.add_argument(
        "--tld",
        dest="tlds",
        action="append",
        default=None,
        help="Optional TLD filter (repeatable, e.g. --tld xyz --tld club)",
    )

    rotate_parser = subparsers.add_parser("rotate", help="Find and purchase a new domain")
    rotate_parser.add_argument("--max-price", type=float, default=5.0)
    rotate_parser.add_argument("--max-attempts", type=int, default=10)
    rotate_parser.add_argument(
        "--tld",
        dest="tlds",
        action="append",
        default=None,
        help="Optional TLD filter (repeatable, e.g. --tld xyz --tld club)",
    )

    purchase_parser = subparsers.add_parser("purchase", help="Purchase a specific domain")
    purchase_parser.add_argument("--domain", required=True)
    purchase_parser.add_argument(
        "--price",
        type=float,
        default=None,
        help="Known domain price; auto-queried when omitted",
    )

    budget_parser = subparsers.add_parser("budget", help="Show or update budget settings")
    budget_subparsers = budget_parser.add_subparsers(dest="budget_command", required=True)
    budget_subparsers.add_parser("status", help="Show budget status")
    budget_set_parser = budget_subparsers.add_parser("set", help="Set monthly budget")
    budget_set_parser.add_argument("--amount", type=float, required=True)

    subparsers.add_parser("list", help="List purchased domains from local state")
    return parser


def _load_state_file(path: Path) -> Dict:
    """Load persisted manager state from file."""
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Could not load state file '%s': %s", path, exc)
        return {}


def _save_state_file(path: Path, state: Dict):
    """Persist manager state to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _format_domain_timestamp(value: object, fmt: str) -> str:
    """Format possibly-missing datetimes for CLI output."""
    parsed = DomainRotationManager._parse_datetime(value)
    return parsed.strftime(fmt) if parsed else "unknown"


def run_cli(argv: Optional[List[str]] = None) -> int:
    """Run CLI for module execution."""
    parser = _build_cli_parser()
    args = parser.parse_args(argv)

    state_path = Path(args.state_file).expanduser()
    state = _load_state_file(state_path)

    budget_default = float(os.getenv("DOMAIN_BUDGET", "50"))
    manager = DomainRotationManager(monthly_budget=budget_default)
    manager.load_state(state)

    if args.monthly_budget is not None:
        manager.set_monthly_budget(args.monthly_budget)

    requires_api = args.command in {"search", "rotate", "purchase"}
    if requires_api:
        if not args.api_key or not args.api_secret:
            parser.error(
                "search/rotate/purchase require --api-key and --api-secret "
                "(or PORKBUN_API_KEY/PORKBUN_SECRET_KEY env vars)"
            )
        manager.set_api_client(PorkbunAPIClient(args.api_key, args.api_secret))

    if args.command == "search":
        result = manager.find_cheap_available_domain(
            max_price=args.max_price,
            max_attempts=args.max_attempts,
            tlds=args.tlds,
        )
        if not result:
            print("No cheap available domain found")
            return 1
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "rotate":
        result = manager.rotate_domain(
            max_price=args.max_price,
            max_attempts=args.max_attempts,
            tlds=args.tlds,
        )
        if not result:
            print("Domain rotation failed")
            return 1
        print(f"Activated domain: {result}")
        _save_state_file(state_path, manager.export_state())
        return 0

    if args.command == "purchase":
        price = args.price
        if price is None:
            search_result = manager.api_client.search_domain(args.domain)
            if not search_result.get("available"):
                print(f"Domain is unavailable: {args.domain}")
                return 1
            price = manager._normalize_price(search_result.get("price"))
            if price is None:
                print(f"Could not determine price for domain: {args.domain}")
                return 1

        success = manager.purchase_domain_if_budget_allows(args.domain, price)
        if not success:
            print(f"Purchase failed: {args.domain}")
            return 1

        print(f"Purchased domain: {args.domain} (${price})")
        _save_state_file(state_path, manager.export_state())
        return 0

    if args.command == "budget":
        if args.budget_command == "status":
            payload = manager.get_budget_status()
            payload["active_domain"] = manager.active_domain
            print(json.dumps(payload, indent=2))
            return 0

        if args.budget_command == "set":
            manager.set_monthly_budget(args.amount)
            _save_state_file(state_path, manager.export_state())
            print(f"Monthly budget set to ${manager.monthly_budget:.2f}")
            return 0

    if args.command == "list":
        domains = manager.get_owned_domains()
        if not domains:
            print("No domains recorded in state file")
            return 0

        for idx, domain in enumerate(domains, 1):
            domain_name = domain.get("domain", "unknown")
            active_marker = " [ACTIVE]" if domain_name == manager.active_domain else ""
            price = domain.get("price", "unknown")
            purchased = _format_domain_timestamp(domain.get("purchased_at"), "%Y-%m-%d %H:%M")
            expires = _format_domain_timestamp(domain.get("expires_at"), "%Y-%m-%d")
            print(f"{idx}. {domain_name}{active_marker}")
            print(f"   Price: ${price}")
            print(f"   Purchased: {purchased}")
            print(f"   Expires: {expires}")
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(run_cli())
