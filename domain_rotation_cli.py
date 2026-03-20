#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It integrates with Porkbun and Namecheap APIs.

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
from domain_manager import DomainRotationManager, create_domain_api_client


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


def serialize_owned_domains(owned_domains):
    """Convert datetime fields to ISO strings for JSON storage."""
    serialized = []
    for domain in owned_domains:
        item = dict(domain)
        for key in ("purchased_at", "expires_at"):
            if isinstance(item.get(key), datetime):
                item[key] = item[key].isoformat()
        serialized.append(item)
    return serialized


def deserialize_owned_domains(owned_domains):
    """Convert ISO datetime strings back to datetime objects when possible."""
    deserialized = []
    for domain in owned_domains:
        item = dict(domain)
        for key in ("purchased_at", "expires_at"):
            value = item.get(key)
            if isinstance(value, str):
                try:
                    item[key] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep original string if format is unknown.
                    pass
        deserialized.append(item)
    return deserialized


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars: porkbun, namecheap")
    print("Porkbun API docs: https://porkbun.com/account/api")
    print("Namecheap API docs: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    registrar = config.get('registrar', 'porkbun')
    
    print("Current configuration:")
    print(f"  Registrar: {registrar}")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")

    if registrar == "porkbun":
        if config.get('api_secret'):
            print("  API Secret: ********************")
        else:
            print("  API Secret: Not configured")
    elif registrar == "namecheap":
        print(f"  Username: {config.get('username', 'Not configured')}")
        print(f"  Client IP: {config.get('client_ip', 'Not configured')}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    registrar_input = input(f"Registrar [porkbun/namecheap] [{registrar}]: ").strip().lower()
    if registrar_input:
        if registrar_input not in ("porkbun", "namecheap"):
            print("Invalid registrar. Keeping previous setting.")
        else:
            registrar = registrar_input
            config['registrar'] = registrar

    if registrar == "porkbun":
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            config['api_key'] = api_key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
    elif registrar == "namecheap":
        api_key = input("Namecheap API Key: ").strip()
        if api_key:
            config['api_key'] = api_key

        username = input("Namecheap Username: ").strip()
        if username:
            config['username'] = username

        client_ip = input("Namecheap API Whitelisted Client IP: ").strip()
        if client_ip:
            config['client_ip'] = client_ip
    
    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config['monthly_budget'] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif 'monthly_budget' not in config:
        config['monthly_budget'] = 50.0

    config['registrar'] = registrar
    save_config(config)
    print("\n✅ Configuration updated successfully!")


def get_manager():
    """Get configured domain manager"""
    config = load_config()
    registrar = config.get('registrar', 'porkbun')

    try:
        if registrar == "porkbun":
            if not config.get('api_key') or not config.get('api_secret'):
                raise ValueError("Porkbun credentials (api_key/api_secret) are not configured.")
            client = create_domain_api_client(
                "porkbun",
                api_key=config['api_key'],
                api_secret=config['api_secret']
            )
        elif registrar == "namecheap":
            if not config.get('api_key') or not config.get('username') or not config.get('client_ip'):
                raise ValueError("Namecheap credentials (api_key/username/client_ip) are not configured.")
            client = create_domain_api_client(
                "namecheap",
                api_key=config['api_key'],
                username=config['username'],
                client_ip=config['client_ip'],
                contact_profile=config.get('contact_profile')
            )
        else:
            raise ValueError(f"Unsupported registrar in config: {registrar}")
    except ValueError as exc:
        print(f"❌ Error: {exc}")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0),
        registrar=registrar
    )
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = deserialize_owned_domains(config['owned_domains'])
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['registrar'] = manager.registrar or config.get('registrar', 'porkbun')
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = serialize_owned_domains(manager.owned_domains)
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
        purchased_at = domain.get('purchased_at')
        expires_at = domain.get('expires_at')
        if isinstance(purchased_at, datetime):
            purchased_display = purchased_at.strftime('%Y-%m-%d %H:%M')
        else:
            purchased_display = str(purchased_at) if purchased_at else "Unknown"
        if isinstance(expires_at, datetime):
            expires_display = expires_at.strftime('%Y-%m-%d')
        else:
            expires_display = str(expires_at) if expires_at else "Unknown"

        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {purchased_display}")
        print(f"   Expires: {expires_display}")
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, config = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Using registrar: {manager.registrar or 'unknown'}")
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
    print(f"Registrar: {manager.registrar or 'unknown'}")
    
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
    
    print(f"Registrar: {manager.registrar or 'unknown'}")
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
