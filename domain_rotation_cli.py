#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails.

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
from datetime import datetime
from getpass import getpass
from domain_manager import PorkbunAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def save_config(config):
    """Save configuration to file"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        os.chmod(CONFIG_FILE, 0o600)  # Secure permissions
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")


def _parse_datetime(value):
    """Parse datetime from ISO string, tolerate invalid values."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _serialize_owned_domain(domain):
    """Serialize owned domain entry for JSON storage."""
    serialized = dict(domain)
    for key in ("purchased_at", "expires_at"):
        dt_value = _parse_datetime(serialized.get(key))
        if dt_value is not None:
            serialized[key] = dt_value.isoformat()
    return serialized


def _deserialize_owned_domain(domain):
    """Deserialize owned domain entry from JSON storage."""
    deserialized = dict(domain)
    for key in ("purchased_at", "expires_at"):
        parsed = _parse_datetime(deserialized.get(key))
        if parsed is not None:
            deserialized[key] = parsed
    return deserialized


def _format_datetime(value, fmt):
    """Format datetime values safely for display."""
    parsed = _parse_datetime(value)
    if parsed is None:
        return "unknown"
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
    print("\n[OK] Configuration updated successfully.")


def get_manager():
    """Get configured domain manager"""
    config = load_config()
    
    if not config.get('api_key') or not config.get('api_secret'):
        print("[ERROR] API credentials not configured.")
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
        manager.owned_domains = [
            _deserialize_owned_domain(domain)
            for domain in config['owned_domains']
            if isinstance(domain, dict)
        ]
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = [
        _serialize_owned_domain(domain)
        for domain in manager.owned_domains
        if isinstance(domain, dict)
    ]
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
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'), '%Y-%m-%d')}")
        print()


def search_domains(max_price=5.0, attempts=5):
    """Search for available cheap domains"""
    manager, _ = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Searching for domains under ${max_price}...\n")
    
    for i in range(max(1, attempts)):
        print(f"Attempt {i+1}/{max(1, attempts)}...")
        domain_info = manager.find_cheap_available_domain(max_price=max_price, max_attempts=1)
        
        if domain_info:
            print(f"  [OK] Found: {domain_info['domain']} - ${domain_info['price']}")
        else:
            print("  [NOPE] No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(auto_confirm=False, max_price=5.0):
    """Rotate to a new domain"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation ===\n")
    
    budget_status = manager.get_budget_status()
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")
    
    if budget_status['remaining'] < 1:
        print("[ERROR] Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(max_price=min(max_price, budget_status['remaining']))
    
    if not domain_info:
        print("[ERROR] Could not find an available cheap domain within budget.")
        return
    
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']}")
    
    if auto_confirm:
        confirm = 'yes'
    else:
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
        print(f"\n[OK] Successfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\n[ERROR] Failed to purchase domain. Check API credentials and budget.")


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
        print(f"\n[OK] Current burner email domain: {manager.active_domain}")
        print(f"   Configure your email system to use: user@{manager.active_domain}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='OpSecChat Domain Rotation CLI',
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
        choices=['config', 'status', 'search', 'rotate', 'list'],
        help='Command to execute'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Auto-confirm domain purchase (for rotate command)'
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
        help='Number of search attempts for search command (default: 5)'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status()
    elif args.command == 'search':
        search_domains(max_price=args.max_price, attempts=args.attempts)
    elif args.command == 'rotate':
        rotate_domain(auto_confirm=args.yes, max_price=args.max_price)
    elif args.command == 'list':
        list_domains()


if __name__ == '__main__':
    main()
