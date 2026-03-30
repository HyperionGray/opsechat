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
from domain_manager import (
    DomainRotationManager,
    NamecheapAPIClient,
    PorkbunAPIClient,
)


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
    print("This tool supports Porkbun and Namecheap API for domain management.")
    print("Porkbun keys: https://porkbun.com/account/api")
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

    provider_input = input("Provider [porkbun/namecheap] (default: porkbun): ").strip().lower()
    if provider_input in {"porkbun", "namecheap"}:
        config['provider'] = provider_input
    elif 'provider' not in config:
        config['provider'] = 'porkbun'

    selected_provider = config.get('provider', 'porkbun')

    api_key_prompt = "Namecheap API Key" if selected_provider == "namecheap" else "Porkbun API Key"
    api_key = input(f"{api_key_prompt}: ").strip()
    if api_key:
        config['api_key'] = api_key

    if selected_provider == "namecheap":
        username = input("Namecheap Username: ").strip()
        if username:
            config['username'] = username
        client_ip = input("Namecheap Client IP (whitelisted in Namecheap): ").strip()
        if client_ip:
            config['client_ip'] = client_ip
        api_user = input("Namecheap ApiUser (optional; defaults to username): ").strip()
        if api_user:
            config['api_user'] = api_user
        default_contact_id = input("Namecheap default contact profile ID (optional): ").strip()
        if default_contact_id:
            try:
                config['default_contact_id'] = int(default_contact_id)
            except ValueError:
                print("Invalid contact profile ID, ignoring")
        sandbox = input("Use Namecheap sandbox? [y/N]: ").strip().lower()
        config['sandbox'] = sandbox in {'y', 'yes'}
    else:
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret

    use_fallback = input("Configure fallback provider too? [y/N]: ").strip().lower()
    if use_fallback in {'y', 'yes'}:
        fallback_provider = "namecheap" if selected_provider == "porkbun" else "porkbun"
        print(f"\nConfiguring fallback provider: {fallback_provider}")
        fb_key = input(f"{fallback_provider.capitalize()} API Key: ").strip()
        if fb_key:
            fallback = {"provider": fallback_provider, "api_key": fb_key}
            if fallback_provider == "porkbun":
                fb_secret = getpass("Porkbun API Secret: ").strip()
                if fb_secret:
                    fallback["api_secret"] = fb_secret
            else:
                fb_user = input("Namecheap Username: ").strip()
                fb_ip = input("Namecheap Client IP: ").strip()
                if fb_user:
                    fallback["username"] = fb_user
                if fb_ip:
                    fallback["client_ip"] = fb_ip
                fb_api_user = input("Namecheap ApiUser (optional): ").strip()
                if fb_api_user:
                    fallback["api_user"] = fb_api_user
                fb_contact = input("Namecheap default contact profile ID (optional): ").strip()
                if fb_contact:
                    try:
                        fallback["default_contact_id"] = int(fb_contact)
                    except ValueError:
                        print("Invalid fallback contact profile ID, ignoring")
                fb_sandbox = input("Use Namecheap sandbox? [y/N]: ").strip().lower()
                fallback["sandbox"] = fb_sandbox in {'y', 'yes'}
            config['fallback'] = fallback
    
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
    
    if not config.get('api_key'):
        print("❌ Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    provider = config.get('provider', 'porkbun')
    if provider == 'namecheap':
        if not config.get('username') or not config.get('client_ip'):
            print("❌ Error: Namecheap requires username and client_ip.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = NamecheapAPIClient(
            api_key=config['api_key'],
            username=config['username'],
            client_ip=config['client_ip'],
            api_user=config.get('api_user'),
            sandbox=bool(config.get('sandbox', False)),
            default_contact_id=config.get('default_contact_id'),
        )
    else:
        if not config.get('api_secret'):
            print("❌ Error: Porkbun requires api_secret.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = PorkbunAPIClient(config['api_key'], config['api_secret'])

    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0)
    )

    fallback = config.get('fallback')
    if isinstance(fallback, dict) and fallback.get('api_key'):
        fb_provider = fallback.get('provider', 'porkbun')
        try:
            if fb_provider == 'namecheap':
                if fallback.get('username') and fallback.get('client_ip'):
                    manager.add_api_client(
                        NamecheapAPIClient(
                            api_key=fallback['api_key'],
                            username=fallback['username'],
                            client_ip=fallback['client_ip'],
                            api_user=fallback.get('api_user'),
                            sandbox=bool(fallback.get('sandbox', False)),
                            default_contact_id=fallback.get('default_contact_id'),
                        )
                    )
            else:
                if fallback.get('api_secret'):
                    manager.add_api_client(
                        PorkbunAPIClient(fallback['api_key'], fallback['api_secret'])
                    )
        except Exception as exc:
            print(f"⚠️ Could not load fallback provider: {exc}")
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = config['owned_domains']
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    serialized_domains = []
    for domain in manager.owned_domains:
        d = dict(domain)
        if isinstance(d.get('purchased_at'), datetime):
            d['purchased_at'] = d['purchased_at'].isoformat()
        if isinstance(d.get('expires_at'), datetime):
            d['expires_at'] = d['expires_at'].isoformat()
        serialized_domains.append(d)
    config['owned_domains'] = serialized_domains
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
        purchased_at = domain.get('purchased_at')
        expires_at = domain.get('expires_at')
        if isinstance(purchased_at, str):
            try:
                purchased_at = datetime.fromisoformat(purchased_at)
            except ValueError:
                purchased_at = None
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except ValueError:
                expires_at = None

        registrar = domain.get('registrar')
        if registrar:
            print(f"   Registrar: {registrar}")

        print(f"   Purchased: {purchased_at.strftime('%Y-%m-%d %H:%M') if purchased_at else 'Unknown'}")
        print(f"   Expires: {expires_at.strftime('%Y-%m-%d') if expires_at else 'Unknown'}")
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
        domain_info['price'],
        registrar=domain_info.get('registrar'),
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
