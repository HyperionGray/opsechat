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
    python domain_rotation_cli.py cleanup       # Remove expired domains from local state
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


def _format_datetime(value):
    """Format datetime-like values safely for display."""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime('%Y-%m-%d %H:%M')
        except ValueError:
            return value
    return "Unknown"


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


def get_manager():
    """Get configured domain manager"""
    config = load_config()
    
    if not config.get('api_key') or not config.get('api_secret'):
        print("Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)
    
    client = PorkbunAPIClient(config['api_key'], config['api_secret'])
    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    
    # Load persisted state in a type-safe way.
    manager.import_state(config)
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config.update(manager.export_state())
    save_config(config)


def list_domains():
    """List owned domains"""
    manager, _ = get_manager()
    
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
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'))}")
        expires_display = _format_datetime(domain.get('expires_at'))
        print(f"   Expires: {expires_display.split(' ')[0] if ' ' in expires_display else expires_display}")
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, _ = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
        
        if domain_info:
            print(f"  Found: {domain_info['domain']} - ${domain_info['price']}")
        else:
            print(f"  No cheap domain found in this attempt")
    
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
        print("Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(max_price=min(5.0, budget_status['remaining']))
    
    if not domain_info:
        print("Could not find an available cheap domain within budget.")
        return
    
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']}")
    
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
    manager, _ = get_manager()
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")
    
    if manager.active_domain:
        print(f"\nCurrent burner email domain: {manager.active_domain}")
        print(f"   Configure your email system to use: user@{manager.active_domain}")


def cleanup_domains():
    """Remove expired domains from locally persisted state."""
    manager, config = get_manager()
    result = manager.cleanup_expired_domains()
    save_manager_state(manager, config)

    print("\n=== Domain Cleanup ===\n")
    print(f"Removed expired domains: {result['removed_count']}")
    if result["removed_domains"]:
        for domain in result["removed_domains"]:
            print(f"  - {domain}")
    print(f"Remaining domains: {result['remaining_count']}")
    print(f"Active domain: {result['active_domain'] or 'None'}")


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
  python domain_rotation_cli.py cleanup    # Remove expired local domains
  python domain_rotation_cli.py list       # List owned domains
        """
    )
    
    parser.add_argument(
        'command',
        choices=['config', 'status', 'search', 'rotate', 'cleanup', 'list'],
        help='Command to execute'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status()
    elif args.command == 'search':
        search_domains()
    elif args.command == 'rotate':
        rotate_domain()
    elif args.command == 'cleanup':
        cleanup_domains()
    elif args.command == 'list':
        list_domains()


if __name__ == '__main__':
    main()
