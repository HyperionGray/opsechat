#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It integrates with Porkbun API (and can be extended for other registrars).

Usage:
    python domain_rotation_cli.py list          # List owned domains
    python domain_rotation_cli.py search        # Search for available cheap domains
    python domain_rotation_cli.py rotate        # Rotate to a new domain
    python domain_rotation_cli.py rotate-auto   # Non-interactive rotate for automation
    python domain_rotation_cli.py status        # Show budget status
    python domain_rotation_cli.py config        # Configure API credentials
"""

import argparse
import json
import os
import sys
from pathlib import Path
from getpass import getpass
from datetime import datetime
from domain_manager import PorkbunAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'
ENV_API_KEY = "OPSECHAT_DOMAIN_API_KEY"
ENV_API_SECRET = "OPSECHAT_DOMAIN_API_SECRET"
ENV_MONTHLY_BUDGET = "OPSECHAT_DOMAIN_MONTHLY_BUDGET"


def _parse_datetime(value):
    """Parse an ISO timestamp when possible."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _serialize_owned_domains(domains):
    """Convert in-memory domain records to JSON-safe form."""
    serialized = []
    for entry in domains or []:
        item = dict(entry)
        for field in ("purchased_at", "expires_at"):
            dt_value = item.get(field)
            if isinstance(dt_value, datetime):
                item[field] = dt_value.isoformat()
        serialized.append(item)
    return serialized


def _deserialize_owned_domains(domains):
    """Convert JSON-loaded domain records back to runtime-safe form."""
    deserialized = []
    for entry in domains or []:
        item = dict(entry)
        for field in ("purchased_at", "expires_at"):
            parsed = _parse_datetime(item.get(field))
            if parsed is not None:
                item[field] = parsed
        deserialized.append(item)
    return deserialized


def _parse_env_float(value):
    """Parse optional numeric values from environment strings."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def apply_env_overrides(config):
    """Overlay config with environment variables for automation use."""
    merged = dict(config or {})

    env_api_key = os.getenv(ENV_API_KEY, "").strip()
    if env_api_key:
        merged["api_key"] = env_api_key

    env_api_secret = os.getenv(ENV_API_SECRET, "").strip()
    if env_api_secret:
        merged["api_secret"] = env_api_secret

    env_budget = _parse_env_float(os.getenv(ENV_MONTHLY_BUDGET))
    if env_budget is not None:
        merged["monthly_budget"] = env_budget

    return merged


def _json_default(value):
    """JSON serializer for datetime values in command output."""
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _emit_result(result, output_json=False):
    """Emit command results as text or JSON."""
    if output_json:
        print(json.dumps(result, indent=2, default=_json_default))
        return

    if result.get("success"):
        print(result.get("message", "Operation completed successfully"))
    else:
        print(result.get("message", "Operation failed"))


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def save_config(config):
    """Save configuration to file"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        os.chmod(CONFIG_FILE, 0o600)  # Secure permissions
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("This tool supports Porkbun API for domain management.")
    print("You can get API credentials from: https://porkbun.com/account/api\n")
    
    config = load_config()
    
    print("Current configuration:")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")
    
    api_key = input("Porkbun API Key: ").strip()
    if api_key:
        config['api_key'] = api_key
    
    api_secret = getpass("Porkbun API Secret: ").strip()
    if api_secret:
        config['api_secret'] = api_secret
    
    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config['monthly_budget'] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif 'monthly_budget' not in config:
        config['monthly_budget'] = 50.0
    
    save_config(config)
    print("\n✅ Configuration updated successfully!")


def get_manager():
    """Get configured domain manager"""
    config = apply_env_overrides(load_config())
    
    if not config.get('api_key') or not config.get('api_secret'):
        print("❌ Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)
    
    client = PorkbunAPIClient(config['api_key'], config['api_secret'])
    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = _deserialize_owned_domains(config['owned_domains'])
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _serialize_owned_domains(manager.owned_domains)
    config['active_domain'] = manager.active_domain
    save_config(config)


def list_domains():
    """List owned domains"""
    manager, config = get_manager()
    
    print("\n=== Owned Domains ===\n")
    
    domains = manager.get_owned_domains()
    
    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return
    
    for i, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain['domain'] == manager.active_domain else ""
        purchased_at = _parse_datetime(domain.get('purchased_at'))
        expires_at = _parse_datetime(domain.get('expires_at'))
        purchased_text = purchased_at.strftime('%Y-%m-%d %H:%M') if purchased_at else str(domain.get('purchased_at', 'unknown'))
        expires_text = expires_at.strftime('%Y-%m-%d') if expires_at else str(domain.get('expires_at', 'unknown'))
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {purchased_text}")
        print(f"   Expires: {expires_text}")
        print()


def search_domains(max_price=5.0, limit=5, max_attempts=25):
    """Search for available cheap domains"""
    manager, _config = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Searching for domains under ${max_price}...\n")
    
    matches = manager.search_cheap_domains(
        max_price=max_price,
        limit=limit,
        max_attempts=max_attempts,
    )
    if not matches:
        print("  No cheap domains found in this search window")
        return
    for domain_info in matches:
        print(f"  Found: {domain_info['domain']} - ${domain_info['price']}")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(auto_approve=False, max_price=5.0, max_attempts=10):
    """Rotate to a new domain"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation ===\n")
    
    budget_status = manager.get_budget_status()
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")
    
    if budget_status['remaining'] < 1:
        print("❌ Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(
        max_price=min(max_price, budget_status['remaining']),
        max_attempts=max_attempts,
    )
    
    if not domain_info:
        print("❌ Could not find an available cheap domain within budget.")
        return
    
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']}")
    
    if not auto_approve:
        confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Purchase cancelled.")
            return
    
    print("\nPurchasing domain...")
    result = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price']
    )
    
    if result.get("success"):
        print(f"\nSuccessfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print(f"\nFailed to purchase domain: {result.get('message', 'unknown error')}")


def rotate_domain_auto(max_price=5.0, max_attempts=25, dry_run=False, output_json=False):
    """
    Non-interactive domain rotation for schedulers and automation tools.

    Returns an integer process exit code.
    """
    manager, config = get_manager()
    budget_status = manager.get_budget_status()

    effective_max_price = min(max_price, budget_status['remaining'])
    if effective_max_price <= 0:
        result = {
            "success": False,
            "message": "Insufficient budget remaining this month.",
            "budget_status": budget_status,
        }
        _emit_result(result, output_json=output_json)
        return 2

    domain_info = manager.find_cheap_available_domain(
        max_price=effective_max_price,
        max_attempts=max_attempts,
    )

    if not domain_info:
        result = {
            "success": False,
            "message": "Could not find an available cheap domain within budget.",
            "budget_status": manager.get_budget_status(),
        }
        _emit_result(result, output_json=output_json)
        return 3

    if dry_run:
        result = {
            "success": True,
            "message": "Dry run complete - domain candidate found.",
            "dry_run": True,
            "candidate": domain_info,
            "budget_status": manager.get_budget_status(),
        }
        _emit_result(result, output_json=output_json)
        return 0

    result = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price'],
    )

    if result.get("success"):
        save_manager_state(manager, config)

    _emit_result(result, output_json=output_json)
    return 0 if result.get("success") else 4


def show_status():
    """Show current status"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")
    
    if manager.active_domain:
        print(f"\n✅ Current burner email domain: {manager.active_domain}")
        print(f"   Configure your email system to use: user@{manager.active_domain}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='OpSecHat Domain Rotation CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python domain_rotation_cli.py config     # Configure API credentials
  python domain_rotation_cli.py status     # Show current status
  python domain_rotation_cli.py search     # Search for available domains
  python domain_rotation_cli.py rotate     # Rotate to a new domain
  python domain_rotation_cli.py rotate --yes
  python domain_rotation_cli.py rotate-auto --json
  python domain_rotation_cli.py list       # List owned domains
        """
    )
    
    parser.add_argument(
        'command',
        choices=['config', 'status', 'search', 'rotate', 'rotate-auto', 'list'],
        help='Command to execute'
    )
    parser.add_argument(
        '--max-price',
        type=float,
        default=5.0,
        help='Maximum domain price in USD (search/rotate commands)',
    )
    parser.add_argument(
        '--max-attempts',
        type=int,
        default=25,
        help='Maximum random-domain attempts for search/rotate commands',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=5,
        help='Maximum number of domains to return for search',
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip purchase confirmation for rotate',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Find candidate without purchasing (rotate-auto)',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Emit machine-readable JSON output (rotate-auto)',
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status()
    elif args.command == 'search':
        search_domains(
            max_price=args.max_price,
            limit=args.limit,
            max_attempts=args.max_attempts,
        )
    elif args.command == 'rotate':
        rotate_domain(
            auto_approve=args.yes,
            max_price=args.max_price,
            max_attempts=args.max_attempts,
        )
    elif args.command == 'rotate-auto':
        exit_code = rotate_domain_auto(
            max_price=args.max_price,
            max_attempts=args.max_attempts,
            dry_run=args.dry_run,
            output_json=args.json,
        )
        sys.exit(exit_code)
    elif args.command == 'list':
        list_domains()


if __name__ == '__main__':
    main()
