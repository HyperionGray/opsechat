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
from pathlib import Path
from getpass import getpass
from datetime import datetime
from domain_manager import PorkbunAPIClient, NamecheapAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _parse_datetime(value):
    """Parse ISO datetime from persisted config state."""
    if isinstance(value, datetime):
        return value
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _serialize_domains(domains):
    """Convert runtime domain state to JSON-safe dictionaries."""
    serialized = []
    for domain in domains:
        entry = dict(domain)
        if isinstance(entry.get("purchased_at"), datetime):
            entry["purchased_at"] = entry["purchased_at"].isoformat()
        if isinstance(entry.get("expires_at"), datetime):
            entry["expires_at"] = entry["expires_at"].isoformat()
        serialized.append(entry)
    return serialized


def _deserialize_domains(domains):
    """Convert persisted domain dictionaries back to runtime types."""
    deserialized = []
    for domain in domains or []:
        entry = dict(domain)
        purchased_at = _parse_datetime(entry.get("purchased_at"))
        expires_at = _parse_datetime(entry.get("expires_at"))
        if purchased_at:
            entry["purchased_at"] = purchased_at
        else:
            entry["purchased_at"] = datetime.now()
        if expires_at:
            entry["expires_at"] = expires_at
        else:
            entry["expires_at"] = datetime.now()
        deserialized.append(entry)
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


def _configure_porkbun(config):
    """Configure Porkbun API credentials."""
    print("\n--- Porkbun Configuration ---\n")
    porkbun = config.get('providers', {}).get('porkbun', {})

    if porkbun.get('api_key'):
        print(f"Current API Key: {'*' * 20}{porkbun['api_key'][-4:]}")
    else:
        print("Current API Key: Not configured")

    api_key = input("Porkbun API Key: ").strip()
    if api_key:
        porkbun['api_key'] = api_key

    api_secret = getpass("Porkbun API Secret: ").strip()
    if api_secret:
        porkbun['api_secret'] = api_secret

    config.setdefault('providers', {})['porkbun'] = porkbun
    config['registrar'] = 'porkbun'


def _configure_namecheap(config):
    """Configure Namecheap API credentials."""
    print("\n--- Namecheap Configuration ---\n")
    namecheap = config.get('providers', {}).get('namecheap', {})

    if namecheap.get('api_key'):
        print(f"Current API Key: {'*' * 20}{namecheap['api_key'][-4:]}")
    else:
        print("Current API Key: Not configured")

    api_user = input("Namecheap ApiUser: ").strip()
    if api_user:
        namecheap['api_user'] = api_user

    username = input("Namecheap UserName (account username): ").strip()
    if username:
        namecheap['username'] = username

    api_key = getpass("Namecheap API Key: ").strip()
    if api_key:
        namecheap['api_key'] = api_key

    client_ip = input("Namecheap API Client IP (whitelisted IP): ").strip()
    if client_ip:
        namecheap['client_ip'] = client_ip

    sandbox_raw = input("Use Namecheap sandbox? (yes/no) [default: no]: ").strip().lower()
    if sandbox_raw in ('yes', 'no'):
        namecheap['sandbox'] = sandbox_raw == 'yes'
    elif 'sandbox' not in namecheap:
        namecheap['sandbox'] = False

    print("\nNamecheap requires contact details for domain purchases.")
    existing_contact = namecheap.get('contact_details', {})
    contact_fields = [
        "FirstName",
        "LastName",
        "Address1",
        "City",
        "StateProvince",
        "PostalCode",
        "Country",
        "Phone",
        "EmailAddress",
        "OrganizationName",
        "PhoneExt",
    ]
    contact = dict(existing_contact)
    for field in contact_fields:
        current_value = contact.get(field, "")
        prompt_suffix = f" [current: {current_value}]" if current_value else ""
        new_value = input(f"{field}{prompt_suffix}: ").strip()
        if new_value:
            contact[field] = new_value

    namecheap['contact_details'] = contact
    config.setdefault('providers', {})['namecheap'] = namecheap
    config['registrar'] = 'namecheap'


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("This tool supports Porkbun and Namecheap API for domain management.")
    print("Porkbun API docs: https://porkbun.com/account/api")
    print("Namecheap API docs: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    providers = config.get('providers', {})
    
    print("Current configuration:")
    print(f"  Default Registrar: {config.get('registrar', 'porkbun')}")
    print(f"  Porkbun Configured: {'yes' if providers.get('porkbun', {}).get('api_key') else 'no'}")
    print(f"  Namecheap Configured: {'yes' if providers.get('namecheap', {}).get('api_key') else 'no'}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nSelect registrar to configure:")
    print("  1) Porkbun")
    print("  2) Namecheap")
    choice = input("Choose 1 or 2 [default: 1]: ").strip() or "1"

    if choice == "2":
        _configure_namecheap(config)
    else:
        _configure_porkbun(config)
    
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

    # Backward compatibility for legacy flat config keys
    if config.get('api_key') and config.get('api_secret'):
        config.setdefault('providers', {}).setdefault('porkbun', {
            'api_key': config['api_key'],
            'api_secret': config['api_secret'],
        })
        config.setdefault('registrar', 'porkbun')

    providers = config.get('providers', {})
    registrar = config.get('registrar', 'porkbun')

    if registrar == 'namecheap':
        provider_cfg = providers.get('namecheap', {})
        required = ['api_user', 'username', 'api_key', 'client_ip']
        if any(not provider_cfg.get(field) for field in required):
            print("❌ Error: Namecheap API credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        primary_client = NamecheapAPIClient(
            api_user=provider_cfg['api_user'],
            api_key=provider_cfg['api_key'],
            username=provider_cfg['username'],
            client_ip=provider_cfg['client_ip'],
            sandbox=provider_cfg.get('sandbox', False),
            contact_details=provider_cfg.get('contact_details'),
        )
        primary_provider = 'namecheap'
    else:
        provider_cfg = providers.get('porkbun', {})
        if not provider_cfg.get('api_key') or not provider_cfg.get('api_secret'):
            print("❌ Error: Porkbun API credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        primary_client = PorkbunAPIClient(provider_cfg['api_key'], provider_cfg['api_secret'])
        primary_provider = 'porkbun'

    manager = DomainRotationManager(
        api_client=primary_client,
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    manager.api_clients = {primary_provider: primary_client}
    manager.api_client = primary_client

    # Optional secondary provider for fallback
    if primary_provider != 'porkbun':
        porkbun_cfg = providers.get('porkbun', {})
        if porkbun_cfg.get('api_key') and porkbun_cfg.get('api_secret'):
            manager.add_api_client(
                'porkbun',
                PorkbunAPIClient(porkbun_cfg['api_key'], porkbun_cfg['api_secret'])
            )
    if primary_provider != 'namecheap':
        namecheap_cfg = providers.get('namecheap', {})
        required = ['api_user', 'username', 'api_key', 'client_ip']
        if all(namecheap_cfg.get(field) for field in required):
            manager.add_api_client(
                'namecheap',
                NamecheapAPIClient(
                    api_user=namecheap_cfg['api_user'],
                    api_key=namecheap_cfg['api_key'],
                    username=namecheap_cfg['username'],
                    client_ip=namecheap_cfg['client_ip'],
                    sandbox=namecheap_cfg.get('sandbox', False),
                    contact_details=namecheap_cfg.get('contact_details'),
                )
            )

    if not manager.api_clients:
        print("❌ Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = _deserialize_domains(config['owned_domains'])
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    if config.get('active_provider'):
        manager.active_provider = config['active_provider']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _serialize_domains(manager.owned_domains)
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
        provider = domain.get('provider', 'unknown')
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Provider: {provider}")
        print(f"   Price: ${domain['price']}")
        purchased_at = domain.get('purchased_at')
        expires_at = domain.get('expires_at')
        if isinstance(purchased_at, datetime):
            purchased_txt = purchased_at.strftime('%Y-%m-%d %H:%M')
        else:
            purchased_txt = str(purchased_at)
        if isinstance(expires_at, datetime):
            expires_txt = expires_at.strftime('%Y-%m-%d')
        else:
            expires_txt = str(expires_at)
        print(f"   Purchased: {purchased_txt}")
        print(f"   Expires: {expires_txt}")
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
    print(f"Active Provider: {manager.active_provider or 'None'}")
    print(f"Configured Providers: {', '.join(budget_status.get('providers_configured', [])) or 'None'}")
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
