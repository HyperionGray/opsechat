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
from domain_manager import PorkbunAPIClient, NamecheapAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _serialize_domain_record(record):
    """Convert datetime fields to ISO strings for JSON persistence."""
    serialized = dict(record)
    for key in ("purchased_at", "expires_at"):
        value = serialized.get(key)
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
    return serialized


def _deserialize_domain_record(record):
    """Restore datetime fields from ISO strings when loading state."""
    deserialized = dict(record)
    for key in ("purchased_at", "expires_at"):
        value = deserialized.get(key)
        if isinstance(value, str):
            try:
                deserialized[key] = datetime.fromisoformat(value)
            except ValueError:
                # Keep raw value if format is unknown; caller can still display it.
                pass
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
    print("This tool supports Porkbun and Namecheap API providers for domain management.")
    print("Porkbun API: https://porkbun.com/account/api")
    print("Namecheap API: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    
    print("Current configuration:")
    provider = config.get('provider', 'porkbun')
    print(f"  Provider: {provider}")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    selected_provider = input(f"Provider [porkbun/namecheap] [{provider}]: ").strip().lower()
    if selected_provider:
        if selected_provider not in {"porkbun", "namecheap"}:
            print("Invalid provider. Keeping previous value.")
        else:
            provider = selected_provider
            config['provider'] = provider
    else:
        config['provider'] = provider

    api_key = input("API Key: ").strip()
    if api_key:
        config['api_key'] = api_key

    if provider == "porkbun":
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
        config.pop('api_user', None)
        config.pop('username', None)
        config.pop('client_ip', None)
    else:
        api_user = input("Namecheap API User: ").strip()
        if api_user:
            config['api_user'] = api_user
        username = input("Namecheap Username [optional, defaults to api_user]: ").strip()
        if username:
            config['username'] = username
        client_ip = input("Namecheap Client IP [127.0.0.1]: ").strip()
        if client_ip:
            config['client_ip'] = client_ip
        elif 'client_ip' not in config:
            config['client_ip'] = "127.0.0.1"
        use_sandbox = input("Use Namecheap sandbox? [yes/no, default no]: ").strip().lower()
        if use_sandbox in {"yes", "y"}:
            config['use_sandbox'] = True
        elif use_sandbox in {"no", "n"}:
            config['use_sandbox'] = False
    
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

    provider = config.get('provider', 'porkbun').lower()

    if provider == 'porkbun':
        if not config.get('api_key') or not config.get('api_secret'):
            print("Error: Porkbun API credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = PorkbunAPIClient(config['api_key'], config['api_secret'])
    elif provider == 'namecheap':
        if not config.get('api_key') or not config.get('api_user'):
            print("Error: Namecheap credentials not configured (api_key/api_user required).")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = NamecheapAPIClient(
            api_key=config['api_key'],
            api_user=config['api_user'],
            username=config.get('username'),
            client_ip=config.get('client_ip', '127.0.0.1'),
            use_sandbox=bool(config.get('use_sandbox', False))
        )
    else:
        print(f"Error: Unsupported provider '{provider}'.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    manager.add_api_client(provider, client, make_default=True)
    
    # Load saved state
    if config.get('current_spending') is not None:
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = [_deserialize_domain_record(r) for r in config['owned_domains']]
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = [_serialize_domain_record(r) for r in manager.owned_domains]
    config['active_domain'] = manager.active_domain
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
        purchased_at = domain.get('purchased_at')
        expires_at = domain.get('expires_at')

        if isinstance(purchased_at, str):
            purchased_display = purchased_at
        elif isinstance(purchased_at, datetime):
            purchased_display = purchased_at.strftime('%Y-%m-%d %H:%M')
        else:
            purchased_display = "unknown"

        if isinstance(expires_at, str):
            expires_display = expires_at
        elif isinstance(expires_at, datetime):
            expires_display = expires_at.strftime('%Y-%m-%d')
        else:
            expires_display = "unknown"

        print(f"{i}. {domain['domain']}{active}")
        print(f"   Provider: {domain.get('provider', manager.default_provider or 'unknown')}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {purchased_display}")
        print(f"   Expires: {expires_display}")
        print()


def search_domains(provider=None):
    """Search for available cheap domains"""
    manager, _ = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")
    if provider:
        print(f"Provider filter: {provider}\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        providers = [provider] if provider else None
        domain_info = manager.find_cheap_available_domain(
            max_price=5.0,
            max_attempts=1,
            providers=providers
        )
        
        if domain_info:
            print(
                f"  Found: {domain_info['domain']} - ${domain_info['price']} "
                f"(provider: {domain_info.get('provider', 'unknown')})"
            )
        else:
            print("  No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(provider=None):
    """Rotate to a new domain"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation ===\n")
    
    budget_status = manager.get_budget_status()
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")
    print(f"Default Provider: {budget_status.get('default_provider')}\n")
    
    if budget_status['remaining'] < 1:
        print("Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")

    providers = [provider] if provider else None
    domain_info = manager.find_cheap_available_domain(
        max_price=min(5.0, budget_status['remaining']),
        providers=providers
    )
    
    if not domain_info:
        print("Could not find an available cheap domain within budget.")
        return
    
    print(
        f"\nFound: {domain_info['domain']} for ${domain_info['price']} "
        f"(provider: {domain_info.get('provider', 'unknown')})"
    )
    
    confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Purchase cancelled.")
        return
    
    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price'],
        provider=domain_info.get('provider')
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
    print(f"Default Provider: {budget_status.get('default_provider') or 'None'}")
    print(f"Configured Providers: {', '.join(budget_status.get('providers', [])) or 'None'}")
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")
    
    if manager.active_domain:
        print(f"\nCurrent burner email domain: {manager.active_domain}")
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
        help='Optional provider override for search/rotate commands'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status()
    elif args.command == 'search':
        search_domains(provider=args.provider)
    elif args.command == 'rotate':
        rotate_domain(provider=args.provider)
    elif args.command == 'list':
        list_domains()


if __name__ == '__main__':
    main()
