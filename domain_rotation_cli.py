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


def _mask_key(value: str) -> str:
    """Mask API keys for display."""
    if not value:
        return "Not configured"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


def _serialize_owned_domains(domains):
    """Serialize domain state to JSON-safe objects."""
    serialized = []
    for domain in domains or []:
        item = dict(domain)
        for key in ("purchased_at", "expires_at"):
            value = item.get(key)
            if isinstance(value, datetime):
                item[key] = value.isoformat()
        serialized.append(item)
    return serialized


def _deserialize_owned_domains(domains):
    """Deserialize domain state from JSON-safe objects."""
    deserialized = []
    for domain in domains or []:
        item = dict(domain)
        for key in ("purchased_at", "expires_at"):
            value = item.get(key)
            if isinstance(value, str):
                try:
                    item[key] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep unparseable values as-is for backward compatibility
                    pass
        deserialized.append(item)
    return deserialized


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported providers: porkbun, namecheap\n")
    
    config = load_config()
    provider = config.get('provider', 'porkbun')
    
    print("Current configuration:")
    print(f"  Provider: {provider}")
    print(f"  API Key: {_mask_key(config.get('api_key', ''))}")
    if provider == "namecheap":
        print(f"  Username: {config.get('username', 'Not configured')}")
        print(f"  Client IP: {config.get('client_ip', '127.0.0.1')}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    provider_input = input(f"Provider [porkbun/namecheap] (current: {provider}): ").strip().lower()
    if provider_input in {"porkbun", "namecheap"}:
        provider = provider_input
        config['provider'] = provider

    api_key = input(f"{provider.capitalize()} API Key: ").strip()
    if api_key:
        config['api_key'] = api_key

    if provider == "porkbun":
        print("Porkbun credentials: https://porkbun.com/account/api")
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
        # Remove provider-specific fields from previous configs
        config.pop('username', None)
        config.pop('client_ip', None)
    else:
        print("Namecheap API docs: https://www.namecheap.com/support/api/intro/")
        username = input("Namecheap Username: ").strip()
        if username:
            config['username'] = username
        client_ip = input(
            f"Namecheap Whitelisted Client IP [default: {config.get('client_ip', '127.0.0.1')}]: "
        ).strip()
        if client_ip:
            config['client_ip'] = client_ip
        elif 'client_ip' not in config:
            config['client_ip'] = "127.0.0.1"
        # Remove provider-specific fields from previous configs
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


def get_manager(provider_override=None):
    """Get configured domain manager"""
    config = load_config()
    provider = provider_override or config.get('provider', 'porkbun')
    api_key = config.get('api_key')
    if not api_key:
        print("❌ Error: API key not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    if provider == "porkbun" and not config.get('api_secret'):
        print("❌ Error: Porkbun API secret not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    if provider == "namecheap" and not config.get('username'):
        print("❌ Error: Namecheap username not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    try:
        client = create_domain_api_client(
            provider=provider,
            api_key=api_key,
            api_secret=config.get('api_secret'),
            username=config.get('username'),
            client_ip=config.get('client_ip', '127.0.0.1'),
            sandbox=bool(config.get('sandbox', False)),
        )
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

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
    config['provider'] = manager.provider
    config['owned_domains'] = _serialize_owned_domains(manager.owned_domains)
    config['active_domain'] = manager.active_domain
    save_config(config)


def list_domains(provider_override=None):
    """List owned domains"""
    manager, config = get_manager(provider_override)
    
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
        purchased_at = domain.get('purchased_at')
        expires_at = domain.get('expires_at')

        if isinstance(purchased_at, str):
            try:
                purchased_at = datetime.fromisoformat(purchased_at)
            except ValueError:
                pass
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except ValueError:
                pass

        purchased_display = purchased_at.strftime('%Y-%m-%d %H:%M') if hasattr(purchased_at, 'strftime') else str(purchased_at)
        expires_display = expires_at.strftime('%Y-%m-%d') if hasattr(expires_at, 'strftime') else str(expires_at)
        print(f"   Purchased: {purchased_display}")
        print(f"   Expires: {expires_display}")
        print()


def search_domains(provider_override=None):
    """Search for available cheap domains"""
    manager, config = get_manager(provider_override)
    
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


def rotate_domain(provider_override=None):
    """Rotate to a new domain"""
    manager, config = get_manager(provider_override)
    
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


def show_status(provider_override=None):
    """Show current status"""
    manager, config = get_manager(provider_override)
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Provider: {manager.provider}")
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
    parser.add_argument(
        '--provider',
        choices=['porkbun', 'namecheap'],
        default=None,
        help='Override configured provider for this command'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status(args.provider)
    elif args.command == 'search':
        search_domains(args.provider)
    elif args.command == 'rotate':
        rotate_domain(args.provider)
    elif args.command == 'list':
        list_domains(args.provider)


if __name__ == '__main__':
    main()
