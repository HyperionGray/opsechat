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
from datetime import datetime
from pathlib import Path
from getpass import getpass
from domain_manager import DomainRotationManager, NamecheapAPIClient, PorkbunAPIClient


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


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("This tool supports Porkbun and Namecheap APIs for domain management.\n")
    
    config = load_config()
    provider = config.get('provider', 'porkbun').lower()
    
    print("Current configuration:")
    print(f"  Provider: {provider}")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")
    if provider == 'namecheap':
        print(f"  API User: {config.get('api_user', 'Not configured')}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")
    
    provider_input = input(f"Provider (porkbun/namecheap) [{provider}]: ").strip().lower()
    if provider_input:
        if provider_input not in {'porkbun', 'namecheap'}:
            print("Invalid provider. Keeping previous value.")
        else:
            provider = provider_input
    config['provider'] = provider

    api_key = input("API Key: ").strip()
    if api_key:
        config['api_key'] = api_key
    
    if provider == 'porkbun':
        print("Get Porkbun API credentials from: https://porkbun.com/account/api")
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
        config.pop('api_user', None)
        config.pop('username', None)
        config.pop('client_ip', None)
    else:
        print("Namecheap API requires your approved client IP.")
        api_user = input(f"Namecheap API User [{config.get('api_user', '')}]: ").strip()
        if api_user:
            config['api_user'] = api_user

        username = input(f"Namecheap Username [{config.get('username', config.get('api_user', ''))}]: ").strip()
        if username:
            config['username'] = username

        client_ip = input(f"Namecheap Client IP [{config.get('client_ip', '127.0.0.1')}]: ").strip()
        if client_ip:
            config['client_ip'] = client_ip
        elif 'client_ip' not in config:
            config['client_ip'] = '127.0.0.1'

        config.pop('api_secret', None)
    
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
    provider = config.get('provider', 'porkbun').lower()
    
    if not config.get('api_key'):
        print("❌ Error: API key not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(monthly_budget=float(config.get('monthly_budget', 50.0)))
    if provider == 'porkbun':
        if not config.get('api_secret'):
            print("❌ Error: Porkbun API secret not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = PorkbunAPIClient(config['api_key'], config['api_secret'])
    elif provider == 'namecheap':
        if not config.get('api_user'):
            print("❌ Error: Namecheap API user not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = NamecheapAPIClient(
            api_key=config['api_key'],
            api_user=config['api_user'],
            username=config.get('username'),
            client_ip=config.get('client_ip', '127.0.0.1'),
        )
    else:
        print(f"❌ Error: Unsupported provider '{provider}'.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)
    manager.add_api_client(provider, client, set_active=True)
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = float(config['current_spending'])
    if config.get('owned_domains'):
        manager.load_owned_domains(config['owned_domains'])
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['provider'] = manager.get_active_provider() or config.get('provider', 'porkbun')
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = manager.get_owned_domains_serializable()
    config['active_domain'] = manager.active_domain
    save_config(config)


def _format_datetime(value, date_only=False):
    """Format datetime values loaded from either objects or ISO strings."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d' if date_only else '%Y-%m-%d %H:%M')
    return "Unknown"


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
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'))}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'), date_only=True)}")
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, config = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
        
        if domain_info:
            print(f"  ✅ Found: {domain_info['domain']} - ${domain_info['price']}")
        else:
            print(f"  ❌ No cheap domain found in this attempt")
    
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
    success = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price']
    )
    
    if success:
        print(f"\n✅ Successfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\n❌ Failed to purchase domain. Check API credentials and budget.")


def show_status():
    """Show current status"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"Provider: {budget_status.get('provider') or 'not configured'}")
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
        choices=['config', 'status', 'search', 'rotate', 'list'],
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
    elif args.command == 'list':
        list_domains()


if __name__ == '__main__':
    main()
