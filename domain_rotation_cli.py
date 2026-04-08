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
    python domain_rotation_cli.py report        # Show operational report
    python domain_rotation_cli.py prune         # Remove expired domains from local state
    python domain_rotation_cli.py config        # Configure API credentials
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from getpass import getpass
from typing import Any, Dict, Tuple
from domain_manager import PorkbunAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


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


def _parse_datetime(value: Any):
    """Parse datetime from datetime object or ISO-8601 string."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _format_datetime(value: Any, fmt: str, fallback: str = "unknown"):
    """Format datetime values safely for CLI output."""
    parsed = _parse_datetime(value)
    if not parsed:
        return fallback
    return parsed.strftime(fmt)


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
    print("\nConfiguration updated successfully.")


def get_manager(require_api: bool = True) -> Tuple[DomainRotationManager, Dict]:
    """Get domain manager with optional API requirement."""
    config = load_config()

    try:
        monthly_budget = float(config.get('monthly_budget', 50.0))
    except (TypeError, ValueError):
        monthly_budget = 50.0

    manager = DomainRotationManager(monthly_budget=monthly_budget)

    state = config.get('manager_state')
    if not isinstance(state, dict):
        # Backward-compatible migration for pre-state_version config format.
        state = {
            "current_spending": config.get('current_spending', 0.0),
            "owned_domains": config.get('owned_domains', []),
            "active_domain": config.get('active_domain')
        }
    manager.import_state(state)

    api_key = config.get('api_key')
    api_secret = config.get('api_secret')

    if api_key and api_secret:
        manager.set_api_client(PorkbunAPIClient(api_key, api_secret))
    elif require_api:
        print("Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    state = manager.export_state()
    config['manager_state'] = state

    # Keep legacy keys for compatibility with older versions/tools.
    config['current_spending'] = state['current_spending']
    config['owned_domains'] = state['owned_domains']
    config['active_domain'] = state['active_domain']

    save_config(config)


def list_domains():
    """List owned domains"""
    manager, _ = get_manager(require_api=False)
    
    print("\n=== Owned Domains ===\n")
    
    domains = manager.get_owned_domains()
    
    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return
    
    for i, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain['domain'] == manager.active_domain else ""
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'), '%Y-%m-%d')}")
        print()


def search_domains(max_price: float = 5.0, attempts: int = 5):
    """Search for available cheap domains"""
    manager, _ = get_manager(require_api=True)
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Searching for domains under ${max_price}...\n")
    
    for i in range(attempts):
        print(f"Attempt {i+1}/{attempts}...")
        domain_info = manager.find_cheap_available_domain(max_price=max_price, max_attempts=1)
        
        if domain_info:
            print(f"  Found: {domain_info['domain']} - ${domain_info['price']}")
        else:
            print("  No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(max_price: float = 5.0, auto_confirm: bool = False):
    """Rotate to a new domain"""
    manager, config = get_manager(require_api=True)
    
    print("\n=== Domain Rotation ===\n")
    
    budget_status = manager.get_budget_status()
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")
    
    if budget_status['remaining'] < 1:
        print("Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    effective_max_price = min(max_price, budget_status['remaining'])
    domain_info = manager.find_cheap_available_domain(max_price=effective_max_price)
    
    if not domain_info:
        print("Could not find an available cheap domain within budget.")
        return
    
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']}")

    if not auto_confirm:
        confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Purchase cancelled.")
            return
    
    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price']
    )
    
    if success:
        print(f"\nSuccessfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\nFailed to purchase domain. Check API credentials and budget.")


def show_status():
    """Show current status"""
    manager, _ = get_manager(require_api=False)
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")
    print(f"Expired Domains (tracked): {manager.get_domain_report()['expired_domains']}")
    
    if manager.active_domain:
        print(f"\nCurrent burner email domain: {manager.active_domain}")
        print(f"   Configure your email system to use: user@{manager.active_domain}")


def prune_domains():
    """Remove expired domains from local saved state."""
    manager, config = get_manager(require_api=False)
    removed = manager.prune_expired_domains()
    save_manager_state(manager, config)

    print("\n=== Domain State Cleanup ===\n")
    print(f"Expired domains removed: {removed}")
    print(f"Domains remaining: {len(manager.get_owned_domains())}")
    if manager.active_domain:
        print(f"Active domain: {manager.active_domain}")
    else:
        print("Active domain: None")


def report_domains():
    """Show operational report for domain state and budget."""
    manager, _ = get_manager(require_api=False)
    report = manager.get_domain_report()
    budget = report['budget']

    print("\n=== Domain Rotation Report ===\n")
    print(f"Active Domain: {report['active_domain'] or 'None'}")
    print(f"Domains Owned: {report['domains_owned']}")
    print(f"Expired Domains: {report['expired_domains']}")
    print(f"Next Expiry: {report['next_expiry'] or 'None'}")
    print("\nBudget:")
    print(f"  Monthly: ${budget['monthly_budget']}")
    print(f"  Spent: ${budget['current_spending']}")
    print(f"  Remaining: ${budget['remaining']}")
    print(f"  Utilization: {report['budget_spent_percent']}%")


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
        choices=['config', 'status', 'search', 'rotate', 'list', 'prune', 'report'],
        help='Command to execute'
    )

    parser.add_argument(
        '--max-price',
        type=float,
        default=5.0,
        help='Maximum domain price in USD for search/rotate (default: 5.0)'
    )

    parser.add_argument(
        '--attempts',
        type=int,
        default=5,
        help='Search attempts for the search command (default: 5)'
    )

    parser.add_argument(
        '--yes',
        action='store_true',
        help='Automatically confirm prompts for rotate'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status()
    elif args.command == 'search':
        search_domains(max_price=args.max_price, attempts=max(1, args.attempts))
    elif args.command == 'rotate':
        rotate_domain(max_price=args.max_price, auto_confirm=args.yes)
    elif args.command == 'list':
        list_domains()
    elif args.command == 'prune':
        prune_domains()
    elif args.command == 'report':
        report_domains()


if __name__ == '__main__':
    main()
