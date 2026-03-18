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
from domain_manager import NamecheapAPIClient, PorkbunAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _serialize_owned_domains(domains):
    """Convert datetime fields to ISO strings for JSON storage."""
    serialized = []
    for domain in domains:
        item = dict(domain)
        for field in ("purchased_at", "expires_at"):
            value = item.get(field)
            if isinstance(value, datetime):
                item[field] = value.isoformat()
        serialized.append(item)
    return serialized


def _deserialize_owned_domains(domains):
    """Convert ISO strings back to datetime objects when possible."""
    deserialized = []
    for domain in domains:
        item = dict(domain)
        for field in ("purchased_at", "expires_at"):
            value = item.get(field)
            if isinstance(value, str):
                try:
                    item[field] = datetime.fromisoformat(value)
                except ValueError:
                    pass
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
    print("Supported providers: porkbun, namecheap")
    print("Porkbun API: https://porkbun.com/account/api")
    print("Namecheap API: https://ap.www.namecheap.com/settings/tools/apiaccess/\n")
    
    config = load_config()
    
    current_provider = config.get('active_provider', 'porkbun')
    print("Current configuration:")
    print(f"  Active Provider: {current_provider}")
    if config.get('api_key'):
        print(f"  Porkbun API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  Porkbun API Key: Not configured")
    if config.get('namecheap_api_key'):
        print(f"  Namecheap API Key: {'*' * 20}{config['namecheap_api_key'][-4:]}")
    else:
        print("  Namecheap API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")
    
    provider = input(f"Active provider [porkbun/namecheap] [{current_provider}]: ").strip().lower()
    if not provider:
        provider = current_provider
    if provider not in ('porkbun', 'namecheap'):
        print("Invalid provider selected, keeping previous value")
        provider = current_provider
    config['active_provider'] = provider

    if provider == 'namecheap':
        namecheap_api_key = getpass("Namecheap API Key: ").strip()
        if namecheap_api_key:
            config['namecheap_api_key'] = namecheap_api_key

        username = input("Namecheap Username: ").strip()
        if username:
            config['namecheap_username'] = username

        api_user = input("Namecheap API User [default: username]: ").strip()
        if api_user:
            config['namecheap_api_user'] = api_user
        elif username and 'namecheap_api_user' not in config:
            config['namecheap_api_user'] = username

        client_ip = input("Namecheap Whitelisted Client IP: ").strip()
        if client_ip:
            config['namecheap_client_ip'] = client_ip

        sandbox = input("Use Namecheap sandbox? (yes/no) [no]: ").strip().lower()
        if sandbox in ('yes', 'no'):
            config['namecheap_sandbox'] = sandbox == 'yes'
    else:
        api_key = getpass("Porkbun API Key: ").strip()
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
    
    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))

    if config.get('api_key') and config.get('api_secret'):
        manager.add_api_client('porkbun', PorkbunAPIClient(config['api_key'], config['api_secret']))

    if (
        config.get('namecheap_api_key')
        and config.get('namecheap_username')
        and (config.get('namecheap_api_user') or config.get('namecheap_username'))
        and config.get('namecheap_client_ip')
    ):
        manager.add_api_client(
            'namecheap',
            NamecheapAPIClient(
                api_user=config.get('namecheap_api_user', config['namecheap_username']),
                api_key=config['namecheap_api_key'],
                username=config['namecheap_username'],
                client_ip=config['namecheap_client_ip'],
                use_sandbox=bool(config.get('namecheap_sandbox', False)),
                contact_profile=config.get('namecheap_contact_profile'),
            )
        )

    if not manager.api_clients:
        print("❌ Error: No API credentials configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    active_provider = config.get('active_provider')
    if active_provider:
        manager.set_active_provider(active_provider)
    
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
    config['active_provider'] = manager.active_provider
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
        provider = f" ({domain['provider']})" if domain.get('provider') else ""
        print(f"{i}. {domain['domain']}{active}")
        if provider:
            print(f"   Provider:{provider}")
        print(f"   Price: ${domain['price']}")
        purchased_at = domain.get('purchased_at')
        expires_at = domain.get('expires_at')
        purchased_str = purchased_at.strftime('%Y-%m-%d %H:%M') if isinstance(purchased_at, datetime) else str(purchased_at)
        expires_str = expires_at.strftime('%Y-%m-%d') if isinstance(expires_at, datetime) else str(expires_at)
        print(f"   Purchased: {purchased_str}")
        print(f"   Expires: {expires_str}")
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
            provider = domain_info.get('provider', manager.active_provider)
            print(f"  ✅ Found: {domain_info['domain']} - ${domain_info['price']} via {provider}")
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
    print(f"Active Provider: {budget_status.get('active_provider')}\n")
    
    if budget_status['remaining'] < 1:
        print("❌ Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(max_price=min(5.0, budget_status['remaining']))
    
    if not domain_info:
        print("❌ Could not find an available cheap domain within budget.")
        return
    
    provider_name = domain_info.get('provider', manager.active_provider)
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']} via {provider_name}")
    
    confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Purchase cancelled.")
        return
    
    print("\nPurchasing domain...")
    if provider_name:
        success = manager.purchase_domain_with_provider(
            domain_info['domain'],
            domain_info['price'],
            provider_name=provider_name
        )
    else:
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
    print(f"Active Provider: {manager.active_provider or 'None'}")
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
