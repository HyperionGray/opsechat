#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It integrates with Porkbun API (and can be extended for other registrars).

Usage:
    python domain_rotation_cli.py list          # List owned domains
    python domain_rotation_cli.py search        # Search for available cheap domains
    python domain_rotation_cli.py rotate        # Rotate to a new domain
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


def save_config(config, quiet=False):
    """Save configuration to file"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        os.chmod(CONFIG_FILE, 0o600)  # Secure permissions
        if not quiet:
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
    config = load_config()
    
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


def save_manager_state(manager, config, quiet=False):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _serialize_owned_domains(manager.owned_domains)
    config['active_domain'] = manager.active_domain
    save_config(config, quiet=quiet)


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


def search_domains(max_price=5.0, limit=5, max_attempts=25, json_output=False):
    """Search for available cheap domains"""
    manager, config = get_manager()
    
    if not json_output:
        print("\n=== Searching for Available Cheap Domains ===\n")
        print(f"Searching for domains under ${max_price}...\n")

    matches = manager.search_cheap_domains(max_price=max_price, limit=limit, max_attempts=max_attempts)
    if not matches:
        if json_output:
            print(json.dumps({"success": False, "matches": [], "message": "No cheap domains found"}))
        else:
            print("  No cheap domains found in this search window")
        return False

    if json_output:
        print(json.dumps({"success": True, "matches": matches, "count": len(matches)}))
        return True

    for domain_info in matches:
        print(f"  Found: {domain_info['domain']} - ${domain_info['price']}")

    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")
    return True


def rotate_domain(
    max_price=5.0,
    max_attempts=10,
    auto_confirm=False,
    dry_run=False,
    json_output=False,
):
    """Rotate to a new domain"""
    manager, config = get_manager()
    
    if not json_output:
        print("\n=== Domain Rotation ===\n")

    budget_status = manager.get_budget_status()
    if not json_output:
        print(f"Monthly Budget: ${budget_status['monthly_budget']}")
        print(f"Current Spending: ${budget_status['current_spending']}")
        print(f"Remaining: ${budget_status['remaining']}")
        print(f"Domains Owned: {budget_status['domains_owned']}\n")

    if budget_status['remaining'] < 1:
        result = {"success": False, "message": "Insufficient budget remaining this month."}
        if json_output:
            print(json.dumps(result))
        else:
            print("Insufficient budget remaining this month.")
        return result

    if not json_output:
        print("Searching for available cheap domain...")

    allowed_price = max(0.01, min(float(max_price), budget_status['remaining']))
    domain_info = manager.find_cheap_available_domain(max_price=allowed_price, max_attempts=max_attempts)

    if not domain_info:
        result = {"success": False, "message": "Could not find an available cheap domain within budget."}
        if json_output:
            print(json.dumps(result))
        else:
            print("Could not find an available cheap domain within budget.")
        return result

    if dry_run:
        result = {
            "success": True,
            "dry_run": True,
            "candidate": domain_info,
            "budget_status": budget_status,
        }
        if json_output:
            print(json.dumps(result))
        else:
            print(f"\nCandidate domain: {domain_info['domain']} for ${domain_info['price']}")
            print("Dry-run enabled. No purchase was made.")
        return result

    if not json_output:
        print(f"\nFound: {domain_info['domain']} for ${domain_info['price']}")

    if not auto_confirm:
        confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
        if confirm != 'yes':
            result = {"success": False, "message": "Purchase cancelled."}
            if json_output:
                print(json.dumps(result))
            else:
                print("Purchase cancelled.")
            return result

    if not json_output:
        print("\nPurchasing domain...")
    result = manager.purchase_domain_if_budget_allows(domain_info['domain'], domain_info['price'])

    if result.get("success"):
        save_manager_state(manager, config, quiet=json_output)
        if json_output:
            print(json.dumps(result))
        else:
            print(f"\nSuccessfully purchased and activated: {domain_info['domain']}")
    else:
        if json_output:
            print(json.dumps(result))
        else:
            print(f"\nFailed to purchase domain: {result.get('message', 'unknown error')}")
    return result


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


def build_parser():
    """Build command-line parser for domain rotation commands."""
    parser = argparse.ArgumentParser(
        description='OpSecHat Domain Rotation CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python domain_rotation_cli.py config                            # Configure API credentials
  python domain_rotation_cli.py status                            # Show current status
  python domain_rotation_cli.py search                            # Search for available domains
  python domain_rotation_cli.py rotate                            # Rotate to a new domain (interactive)
  python domain_rotation_cli.py rotate --yes --max-price 3.50     # Non-interactive purchase
  python domain_rotation_cli.py rotate --dry-run --json           # Machine-readable candidate output
  python domain_rotation_cli.py list                              # List owned domains
        """
    )

    parser.add_argument(
        'command',
        choices=['config', 'status', 'search', 'rotate', 'list'],
        help='Command to execute'
    )
    parser.add_argument(
        '--max-price',
        type=float,
        default=5.0,
        help='Maximum candidate domain price (search/rotate commands)'
    )
    parser.add_argument(
        '--max-attempts',
        type=int,
        default=25,
        help='Maximum random domain attempts when searching'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=5,
        help='Maximum number of results for search'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip purchase confirmation prompt for rotate command'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Find a candidate domain without purchasing it (rotate command)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Emit machine-readable JSON output where supported'
    )
    return parser


def main(argv=None):
    """Main CLI entry point"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.max_price <= 0:
        parser.error("--max-price must be greater than 0")
    if args.max_attempts <= 0:
        parser.error("--max-attempts must be greater than 0")
    if args.limit <= 0:
        parser.error("--limit must be greater than 0")

    if args.command == 'config':
        configure_api()
        return 0
    elif args.command == 'status':
        show_status()
        return 0
    elif args.command == 'search':
        success = search_domains(
            max_price=args.max_price,
            limit=args.limit,
            max_attempts=args.max_attempts,
            json_output=args.json,
        )
        return 0 if success else 1
    elif args.command == 'rotate':
        result = rotate_domain(
            max_price=args.max_price,
            max_attempts=args.max_attempts,
            auto_confirm=args.yes,
            dry_run=args.dry_run,
            json_output=args.json,
        )
        return 0 if result.get("success") else 1
    elif args.command == 'list':
        list_domains()
        return 0


if __name__ == '__main__':
    sys.exit(main())
