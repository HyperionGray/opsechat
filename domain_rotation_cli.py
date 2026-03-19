#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It supports Porkbun and Namecheap registrar APIs.

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
from domain_manager import DomainRotationManager, create_domain_api_client


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'
SUPPORTED_REGISTRARS = ("porkbun", "namecheap")


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


def _parse_bool(value, default=False):
    """Parse truthy/falsey values from config and user input."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _serialize_domains(domains):
    """Serialize owned domain records so they can be stored as JSON."""
    serialized = []
    for domain in domains:
        item = dict(domain)
        for key in ("purchased_at", "expires_at"):
            if isinstance(item.get(key), datetime):
                item[key] = item[key].isoformat()
        serialized.append(item)
    return serialized


def _deserialize_domains(domains):
    """Deserialize owned domain records from config JSON."""
    deserialized = []
    for domain in domains:
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


def _format_datetime(value, fallback="Unknown"):
    """Render datetime fields from mixed runtime/config types."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return fallback
    return fallback


def configure_api(registrar_override=None, sandbox_override=None):
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars: Porkbun, Namecheap")
    print("Porkbun docs: https://porkbun.com/account/api")
    print("Namecheap docs: https://www.namecheap.com/support/api/\n")
    
    config = load_config()
    current_registrar = (config.get('registrar') or 'porkbun').strip().lower()
    if current_registrar not in SUPPORTED_REGISTRARS:
        current_registrar = 'porkbun'
    
    print("Current configuration:")
    print(f"  Registrar: {current_registrar}")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")

    if current_registrar == 'namecheap':
        if config.get('username'):
            print(f"  Username: {config['username']}")
        else:
            print("  Username: Not configured")
        print(f"  Client IP: {config.get('client_ip', '127.0.0.1')}")
        print(f"  Sandbox Mode: {'enabled' if _parse_bool(config.get('sandbox')) else 'disabled'}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    if registrar_override:
        selected_registrar = registrar_override
    else:
        selected_registrar = input(
            f"Registrar [porkbun/namecheap] (current: {current_registrar}): "
        ).strip().lower() or current_registrar
    if selected_registrar not in SUPPORTED_REGISTRARS:
        print(f"Unknown registrar '{selected_registrar}', defaulting to porkbun.")
        selected_registrar = "porkbun"
    config['registrar'] = selected_registrar
    
    api_key = input("API Key: ").strip()
    if api_key:
        config['api_key'] = api_key
    
    if selected_registrar == 'porkbun':
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
    else:
        username = input(f"Namecheap Username [{config.get('username', '')}]: ").strip()
        if username:
            config['username'] = username

        current_client_ip = config.get('client_ip', '127.0.0.1')
        client_ip = input(f"Namecheap Client IP [{current_client_ip}]: ").strip()
        if client_ip:
            config['client_ip'] = client_ip
        elif 'client_ip' not in config:
            config['client_ip'] = current_client_ip

        api_user = input(f"Namecheap ApiUser [{config.get('api_user', config.get('username', ''))}]: ").strip()
        if api_user:
            config['api_user'] = api_user

        if sandbox_override is not None:
            config['sandbox'] = bool(sandbox_override)
        else:
            current_sandbox = "yes" if _parse_bool(config.get('sandbox')) else "no"
            sandbox_input = input(f"Use Namecheap sandbox? [yes/no] (current: {current_sandbox}): ").strip()
            if sandbox_input:
                config['sandbox'] = _parse_bool(sandbox_input)
    
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

    registrar = (config.get('registrar') or 'porkbun').strip().lower()
    if registrar not in SUPPORTED_REGISTRARS:
        print(f"❌ Error: Unsupported registrar in config: {registrar}")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    if not config.get('api_key'):
        print("❌ Error: API key is not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    client_kwargs = {"api_key": config['api_key']}
    if registrar == 'porkbun':
        if not config.get('api_secret'):
            print("❌ Error: Porkbun API secret is not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client_kwargs["api_secret"] = config['api_secret']
    else:
        if not config.get('username'):
            print("❌ Error: Namecheap username is not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client_kwargs["username"] = config['username']
        client_kwargs["client_ip"] = config.get('client_ip', '127.0.0.1')
        client_kwargs["api_user"] = config.get('api_user') or config.get('username')
        client_kwargs["sandbox"] = _parse_bool(config.get('sandbox'))

    client = create_domain_api_client(registrar, **client_kwargs)
    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = _deserialize_domains(config['owned_domains'])
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['registrar'] = manager.registrar or config.get('registrar', 'porkbun')
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _serialize_domains(manager.owned_domains)
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
        purchased_at = _format_datetime(domain.get('purchased_at'))
        if isinstance(purchased_at, datetime):
            purchased_text = purchased_at.strftime('%Y-%m-%d %H:%M')
        else:
            purchased_text = str(purchased_at)
        expires_at = _format_datetime(domain.get('expires_at'))
        if isinstance(expires_at, datetime):
            expires_text = expires_at.strftime('%Y-%m-%d')
        else:
            expires_text = str(expires_at)
        print(f"   Purchased: {purchased_text}")
        print(f"   Expires: {expires_text}")
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
    print(f"Registrar: {manager.registrar or 'unconfigured'}")
    
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
        '--registrar',
        choices=SUPPORTED_REGISTRARS,
        help='Registrar to configure (used with config command)'
    )
    parser.add_argument(
        '--sandbox',
        action='store_true',
        help='Enable Namecheap sandbox mode (used with config command)'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api(registrar_override=args.registrar, sandbox_override=args.sandbox)
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
