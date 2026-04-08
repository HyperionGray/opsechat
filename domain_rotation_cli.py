#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It integrates with Porkbun API (and can be extended for other registrars).

Usage:
    python domain_rotation_cli.py list          # List owned domains
    python domain_rotation_cli.py search        # Search for available cheap domains
    python domain_rotation_cli.py rotate        # Rotate to a new domain
    python domain_rotation_cli.py rotate-auto   # Non-interactive rotation for automation
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


def _parse_tlds(raw_value):
    """Parse comma-separated TLD list from CLI input."""
    if not raw_value:
        return None
    parsed = []
    for item in raw_value.split(","):
        cleaned = item.strip().lower().lstrip(".")
        if cleaned:
            parsed.append(cleaned)
    return parsed or None


def _emit_json(payload):
    """Emit JSON output for automation use-cases."""
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


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


def get_manager(exit_on_error=True, json_output=False):
    """Get configured domain manager"""
    config = load_config()
    
    if not config.get('api_key') or not config.get('api_secret'):
        if exit_on_error:
            if json_output:
                _emit_json({
                    "success": False,
                    "error": "API credentials not configured",
                    "hint": "Run: python domain_rotation_cli.py config",
                })
            else:
                print("❌ Error: API credentials not configured.")
                print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        return None, config
    
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


def search_domains():
    """Search for available cheap domains"""
    manager, config = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")
    
    matches = manager.search_cheap_domains(max_price=5.0, limit=5, max_attempts=25)
    if not matches:
        print("  No cheap domains found in this search window")
        return
    for domain_info in matches:
        print(f"  Found: {domain_info['domain']} - ${domain_info['price']}")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain():
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
    
    domain_info = manager.find_cheap_available_domain(max_price=min(5.0, budget_status['remaining']))
    
    if not domain_info:
        print("❌ Could not find an available cheap domain within budget.")
        return
    
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']}")
    
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


def rotate_domain_auto(max_price=5.0, max_attempts=10, tlds=None, length=8, json_output=False):
    """
    Non-interactive domain rotation.

    This mode is intended for cron jobs and CI automation where no prompt/confirmation
    can be provided.
    """
    manager, config = get_manager(exit_on_error=True, json_output=json_output)

    if max_attempts <= 0:
        payload = {
            "success": False,
            "message": "max_attempts must be greater than 0",
            "max_attempts": max_attempts,
        }
        if json_output:
            _emit_json(payload)
        else:
            print(payload["message"])
        return 1

    if length <= 0:
        payload = {
            "success": False,
            "message": "length must be greater than 0",
            "length": length,
        }
        if json_output:
            _emit_json(payload)
        else:
            print(payload["message"])
        return 1

    budget_before = manager.get_budget_status()
    remaining_budget = budget_before["remaining"]
    effective_max_price = min(max_price, remaining_budget)
    parsed_tlds = _parse_tlds(tlds)

    if effective_max_price <= 0:
        payload = {
            "success": False,
            "message": "No budget remaining for domain rotation",
            "budget_status": budget_before,
            "requested_max_price": max_price,
            "effective_max_price": effective_max_price,
            "tlds": parsed_tlds,
            "max_attempts": max_attempts,
            "length": length,
        }
        if json_output:
            _emit_json(payload)
        else:
            print("Domain rotation failed: no budget remaining")
            print(f"Budget status: {budget_before}")
        return 1

    result = manager.rotate_to_new_domain(
        max_price=effective_max_price,
        max_attempts=max_attempts,
        tlds=parsed_tlds,
        length=length,
    )
    budget_after = manager.get_budget_status()

    payload = {
        "success": bool(result.get("success")),
        "requested_max_price": max_price,
        "effective_max_price": effective_max_price,
        "max_attempts": max_attempts,
        "tlds": parsed_tlds,
        "length": length,
        "budget_before": budget_before,
        "budget_after": budget_after,
        "result": result,
    }

    if result.get("success"):
        save_manager_state(manager, config, quiet=json_output)

    if json_output:
        _emit_json(payload)
    else:
        if payload["success"]:
            print(f"Successfully rotated to: {result.get('active_domain', result.get('domain'))}")
        else:
            print(f"Domain rotation failed: {result.get('message', 'unknown error')}")
        print(f"Budget before: {budget_before}")
        print(f"Budget after: {budget_after}")

    return 0 if payload["success"] else 1


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
        help='Maximum purchase price for rotate-auto (USD)'
    )
    parser.add_argument(
        '--max-attempts',
        type=int,
        default=10,
        help='Maximum search attempts for rotate-auto'
    )
    parser.add_argument(
        '--tlds',
        default=None,
        help='Comma-separated TLDs for rotate-auto (example: xyz,club,online)'
    )
    parser.add_argument(
        '--length',
        type=int,
        default=8,
        help='Domain label length for rotate-auto'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Emit machine-readable JSON output (rotate-auto)'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
        return 0
    elif args.command == 'status':
        show_status()
        return 0
    elif args.command == 'search':
        search_domains()
        return 0
    elif args.command == 'rotate':
        rotate_domain()
        return 0
    elif args.command == 'rotate-auto':
        return rotate_domain_auto(
            max_price=args.max_price,
            max_attempts=args.max_attempts,
            tlds=args.tlds,
            length=args.length,
            json_output=args.json,
        )
    elif args.command == 'list':
        list_domains()
        return 0


if __name__ == '__main__':
    sys.exit(main())
