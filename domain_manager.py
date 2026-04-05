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
        self._configured_provider: Optional[str] = "porkbun" if api_client else None
        self._api_key: Optional[str] = None
        self._secret_key: Optional[str] = None
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client
        self._configured_provider = "custom"
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"

    def generate_random_domain_name(self, length: int = 8, tld: str = "xyz") -> str:
        """Compatibility alias used by docs/integrations."""
        return self.generate_random_domain(tld=tld, length=length)

    @staticmethod
    def _parse_price(value) -> Optional[float]:
        """Normalize registrar pricing into a float value."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = value.strip().replace("$", "").replace("€", "").replace(",", "")
            if not normalized:
                return None
            try:
                return float(normalized)
            except ValueError:
                return None
        return None
    
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
                price = self._parse_price(result.get("price"))
                if price is None:
                    logger.warning("Price missing/invalid for domain %s", domain)
                    continue
                
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None

    def search_cheap_domains(self, tlds: Optional[List[str]] = None,
                             max_price: float = 5.0,
                             limit: int = 5) -> List[Dict]:
        """
        Search for several cheap domains, returning available candidates.
        """
        if limit <= 0:
            return []
        if not self.api_client:
            logger.error("No API client configured")
            return []

        tlds = tlds or ["xyz", "club", "online", "site", "website"]
        results: List[Dict] = []
        attempts = 0
        max_attempts = max(limit * 4, 10)

        while len(results) < limit and attempts < max_attempts:
            tld = random.choice(tlds)
            domain = self.generate_random_domain(tld=tld)
            attempts += 1
            search_result = self.api_client.search_domain(domain)
            if not search_result.get("available"):
                continue

            price = self._parse_price(search_result.get("price"))
            if price is None or price > max_price:
                continue

            results.append({
                "domain": domain,
                "price": price,
                "tld": tld
            })

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

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict:
        """
        Rotate to a new domain and return structured status information.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)
        if not domain_info:
            return {
                "success": False,
                "error": "Could not find available cheap domain",
                "domain": None,
                "cost": None
            }

        purchased = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"]
        )
        if not purchased:
            return {
                "success": False,
                "error": "Purchase failed or budget exceeded",
                "domain": domain_info["domain"],
                "cost": domain_info["price"]
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "error": None,
            "domain": domain_info["domain"],
            "cost": domain_info["price"]
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

    def get_month_spending(self) -> float:
        """Compatibility helper for docs/integrations."""
        return self.current_spending

    def get_remaining_budget(self) -> float:
        """Compatibility helper for docs/integrations."""
        return self.monthly_budget - self.current_spending

    def set_monthly_budget(self, amount: float):
        """Update monthly budget."""
        if amount <= 0:
            raise ValueError("Budget must be greater than 0")
        self.monthly_budget = float(amount)

    def configure(self, api_key: str, secret_key: str,
                  monthly_budget: float = 50.0) -> Dict:
        """
        Configure manager with Porkbun credentials.
        """
        if not api_key or not secret_key:
            raise ValueError("Both API key and secret key are required")
        if monthly_budget <= 0:
            raise ValueError("Monthly budget must be greater than 0")

        self._api_key = api_key
        self._secret_key = secret_key
        self._configured_provider = "porkbun"
        self.monthly_budget = float(monthly_budget)
        self.api_client = PorkbunAPIClient(api_key, secret_key)
        return self.get_config()

    def get_config(self, include_secrets: bool = False) -> Dict:
        """
        Return current configuration, masking secrets by default.
        """
        api_key = self._api_key or ""
        secret_key = self._secret_key or ""
        key_suffix = api_key[-4:] if len(api_key) >= 4 else api_key

        config = {
            "configured": self.api_client is not None,
            "provider": self._configured_provider,
            "monthly_budget": self.monthly_budget,
            "has_api_key": bool(api_key),
            "has_secret_key": bool(secret_key),
            "api_key_suffix": key_suffix
        }
        if include_secrets:
            config["api_key"] = api_key
            config["secret_key"] = secret_key
        return config

    def add_api_client(self, provider_name: str, api_client: DomainAPIClient):
        """
        Register and activate an API client implementation.
        """
        if not provider_name:
            raise ValueError("provider_name is required")
        self.api_client = api_client
        self._configured_provider = provider_name

    @staticmethod
    def _serialize_datetime(value) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return ""

    @staticmethod
    def _deserialize_datetime(value):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value
        return value

    def export_state(self) -> Dict:
        """
        Export runtime state to a JSON-serializable dictionary.
        """
        serialized_domains = []
        for item in self.owned_domains:
            serialized_domains.append({
                "domain": item.get("domain"),
                "price": item.get("price"),
                "purchased_at": self._serialize_datetime(item.get("purchased_at")),
                "expires_at": self._serialize_datetime(item.get("expires_at"))
            })

        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "owned_domains": serialized_domains,
            "active_domain": self.active_domain
        }

    def load_state(self, state: Dict):
        """
        Load runtime state from a dictionary produced by export_state().
        """
        if not isinstance(state, dict):
            return

        if "monthly_budget" in state and state["monthly_budget"] is not None:
            self.monthly_budget = float(state["monthly_budget"])
        if "current_spending" in state and state["current_spending"] is not None:
            self.current_spending = float(state["current_spending"])
        self.active_domain = state.get("active_domain")

        loaded_domains = []
        for item in state.get("owned_domains", []):
            if not isinstance(item, dict):
                continue
            loaded_domains.append({
                "domain": item.get("domain"),
                "price": item.get("price"),
                "purchased_at": self._deserialize_datetime(item.get("purchased_at")),
                "expires_at": self._deserialize_datetime(item.get("expires_at"))
            })
        self.owned_domains = loaded_domains


def _build_manager_from_env() -> DomainRotationManager:
    """
    Build a manager from environment variables.
    """
    monthly_budget = float(os.getenv("DOMAIN_BUDGET", "50.0"))
    manager = DomainRotationManager(monthly_budget=monthly_budget)

    api_key = os.getenv("PORKBUN_API_KEY", "").strip()
    secret_key = os.getenv("PORKBUN_SECRET_KEY", "").strip()
    if api_key and secret_key:
        manager.configure(api_key=api_key, secret_key=secret_key, monthly_budget=monthly_budget)
    return manager


def _require_api_client(manager: DomainRotationManager) -> bool:
    if manager.api_client is None:
        print("Error: missing API credentials.")
        print("Set PORKBUN_API_KEY and PORKBUN_SECRET_KEY environment variables.")
        return False
    return True


def _cmd_search(args) -> int:
    manager = _build_manager_from_env()
    if not _require_api_client(manager):
        return 1

    results = manager.search_cheap_domains(
        tlds=args.tld or None,
        max_price=args.max_price,
        limit=args.limit
    )
    print(json.dumps(results, indent=2))
    return 0


def _cmd_purchase(args) -> int:
    manager = _build_manager_from_env()
    if not _require_api_client(manager):
        return 1

    search_result = manager.api_client.search_domain(args.domain)
    if not search_result.get("available"):
        print(json.dumps({
            "success": False,
            "error": "Domain is not available",
            "domain": args.domain
        }, indent=2))
        return 2

    price = manager._parse_price(search_result.get("price"))
    if price is None:
        print(json.dumps({
            "success": False,
            "error": "Could not determine domain price",
            "domain": args.domain
        }, indent=2))
        return 2

    if args.max_price is not None and price > args.max_price:
        print(json.dumps({
            "success": False,
            "error": f"Price {price:.2f} exceeds max-price {args.max_price:.2f}",
            "domain": args.domain
        }, indent=2))
        return 2

    success = manager.purchase_domain_if_budget_allows(args.domain, price)
    print(json.dumps({
        "success": success,
        "domain": args.domain,
        "price": price,
        "active_domain": manager.get_active_domain(),
        "budget_status": manager.get_budget_status()
    }, indent=2))
    return 0 if success else 2


def _cmd_rotate(args) -> int:
    manager = _build_manager_from_env()
    if not _require_api_client(manager):
        return 1

    result = manager.rotate_to_new_domain(max_price=args.max_price)
    result["budget_status"] = manager.get_budget_status()
    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 2


def _cmd_list(args) -> int:
    manager = _build_manager_from_env()
    if not _require_api_client(manager):
        return 1

    domains = []
    if hasattr(manager.api_client, "list_domains"):
        domains = manager.api_client.list_domains()
    print(json.dumps({"domains": domains, "count": len(domains)}, indent=2))
    return 0


def _cmd_budget_status(args) -> int:
    manager = _build_manager_from_env()
    print(json.dumps(manager.get_budget_status(), indent=2))
    return 0


def _cmd_budget_set(args) -> int:
    manager = _build_manager_from_env()
    manager.set_monthly_budget(args.amount)
    print(json.dumps({
        "monthly_budget": manager.monthly_budget,
        "remaining": manager.get_remaining_budget()
    }, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Domain manager CLI (Porkbun)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search available cheap domains")
    search_parser.add_argument("--tld", action="append", default=[],
                               help="TLD to consider (repeatable)")
    search_parser.add_argument("--max-price", type=float, default=5.0,
                               help="Maximum acceptable price in USD")
    search_parser.add_argument("--limit", type=int, default=5,
                               help="Maximum number of candidate domains")

    purchase_parser = subparsers.add_parser("purchase", help="Purchase a specific domain")
    purchase_parser.add_argument("--domain", required=True, help="Domain name to purchase")
    purchase_parser.add_argument("--max-price", type=float, default=None,
                                 help="Optional max purchase price in USD")

    rotate_parser = subparsers.add_parser("rotate", help="Find and purchase a new domain")
    rotate_parser.add_argument("--max-price", type=float, default=5.0,
                               help="Maximum acceptable domain price")

    subparsers.add_parser("list", help="List owned domains from registrar account")

    budget_parser = subparsers.add_parser("budget", help="Budget operations")
    budget_subparsers = budget_parser.add_subparsers(dest="budget_command", required=True)
    budget_subparsers.add_parser("status", help="Show current budget")
    budget_set_parser = budget_subparsers.add_parser("set", help="Set monthly budget")
    budget_set_parser.add_argument("--amount", type=float, required=True,
                                   help="Monthly budget in USD")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "search":
        return _cmd_search(args)
    if args.command == "purchase":
        return _cmd_purchase(args)
    if args.command == "rotate":
        return _cmd_rotate(args)
    if args.command == "list":
        return _cmd_list(args)
    if args.command == "budget":
        if args.budget_command == "status":
            return _cmd_budget_status(args)
        if args.budget_command == "set":
            return _cmd_budget_set(args)

    parser.print_help()
    return 2


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()


if __name__ == "__main__":
    raise SystemExit(main())
