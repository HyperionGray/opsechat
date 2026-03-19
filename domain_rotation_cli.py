#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It supports multiple registrar APIs through the domain manager abstraction.

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
from domain_manager import PorkbunAPIClient, NamecheapAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'
SUPPORTED_PROVIDERS = ("porkbun", "namecheap")


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


def _serialize_domain_record(record):
    """Convert datetime fields in domain records to JSON-safe strings."""
    serialized = dict(record)
    for key in ("purchased_at", "expires_at"):
        value = serialized.get(key)
        if hasattr(value, "isoformat"):
            serialized[key] = value.isoformat()
    return serialized


def _deserialize_domain_record(record):
    """Convert ISO datetime strings back into datetime objects."""
    deserialized = dict(record)
    for key in ("purchased_at", "expires_at"):
        value = deserialized.get(key)
        if isinstance(value, str):
            try:
                deserialized[key] = datetime.fromisoformat(value)
            except ValueError:
                pass
    return deserialized


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported providers: porkbun, namecheap\n")
    
    config = load_config()
    current_provider = config.get("provider", "porkbun")
    if current_provider not in SUPPORTED_PROVIDERS:
        current_provider = "porkbun"
    
    print("Current configuration:")
    print(f"  Provider: {current_provider}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    provider = input(f"Provider [porkbun/namecheap] [{current_provider}]: ").strip().lower()
    if provider:
        if provider not in SUPPORTED_PROVIDERS:
            print(f"Invalid provider '{provider}', keeping {current_provider}")
            provider = current_provider
    else:
        provider = current_provider
    config["provider"] = provider

    print("\nEnter new values (or press Enter to keep current):\n")

    if provider == "porkbun":
        print("Get API credentials from: https://porkbun.com/account/api\n")
        current_key = config.get("porkbun_api_key") or config.get("api_key", "")
        current_secret = config.get("porkbun_api_secret") or config.get("api_secret", "")

        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            config["porkbun_api_key"] = api_key
            config["api_key"] = api_key  # Backward compatibility for old config shape.
        elif current_key:
            config["porkbun_api_key"] = current_key
            config["api_key"] = current_key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config["porkbun_api_secret"] = api_secret
            config["api_secret"] = api_secret
        elif current_secret:
            config["porkbun_api_secret"] = current_secret
            config["api_secret"] = current_secret
    else:
        print("Namecheap API intro: https://www.namecheap.com/support/api/intro/\n")
        print("Note: Namecheap requires your allowed Client IP in API settings.\n")

        current_api_user = config.get("namecheap_api_user", "")
        current_api_key = config.get("namecheap_api_key", "")
        current_username = config.get("namecheap_username", current_api_user)
        current_client_ip = config.get("namecheap_client_ip", "127.0.0.1")
        current_sandbox = bool(config.get("namecheap_sandbox", False))

        api_user = input(f"Namecheap API User [{current_api_user}]: ").strip()
        if api_user:
            config["namecheap_api_user"] = api_user
        elif current_api_user:
            config["namecheap_api_user"] = current_api_user

        api_key = getpass("Namecheap API Key: ").strip()
        if api_key:
            config["namecheap_api_key"] = api_key
        elif current_api_key:
            config["namecheap_api_key"] = current_api_key

        username = input(f"Namecheap API Username [{current_username or config.get('namecheap_api_user', '')}]: ").strip()
        if username:
            config["namecheap_username"] = username
        elif current_username:
            config["namecheap_username"] = current_username
        elif config.get("namecheap_api_user"):
            config["namecheap_username"] = config["namecheap_api_user"]

        client_ip = input(f"Namecheap Client IP [{current_client_ip}]: ").strip()
        if client_ip:
            config["namecheap_client_ip"] = client_ip
        else:
            config["namecheap_client_ip"] = current_client_ip

        sandbox_in = input(f"Use Namecheap sandbox [yes/no] [{'yes' if current_sandbox else 'no'}]: ").strip().lower()
        if sandbox_in:
            config["namecheap_sandbox"] = sandbox_in in {"y", "yes", "true", "1"}
        else:
            config["namecheap_sandbox"] = current_sandbox
    
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

    provider = config.get("provider", "porkbun")
    if provider not in SUPPORTED_PROVIDERS:
        provider = "porkbun"

    if provider == "porkbun":
        api_key = config.get("porkbun_api_key") or config.get("api_key")
        api_secret = config.get("porkbun_api_secret") or config.get("api_secret")
        if not api_key or not api_secret:
            print("Error: Porkbun API credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = PorkbunAPIClient(api_key, api_secret)
    else:
        api_user = config.get("namecheap_api_user")
        api_key = config.get("namecheap_api_key")
        username = config.get("namecheap_username") or api_user
        client_ip = config.get("namecheap_client_ip", "127.0.0.1")
        sandbox = bool(config.get("namecheap_sandbox", False))
        contact = config.get("namecheap_contact", {})
        if not api_user or not api_key:
            print("Error: Namecheap API credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = NamecheapAPIClient(
            api_user=api_user,
            api_key=api_key,
            username=username,
            client_ip=client_ip,
            sandbox=sandbox,
            contact=contact,
        )

    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    manager.primary_provider = provider
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = [
            _deserialize_domain_record(record) for record in config['owned_domains']
        ]
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = [
        _serialize_domain_record(record) for record in manager.owned_domains
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
        provider = domain.get("provider", "unknown")
        purchased_at = domain.get("purchased_at")
        expires_at = domain.get("expires_at")
        if hasattr(purchased_at, "strftime"):
            purchased_text = purchased_at.strftime("%Y-%m-%d %H:%M")
        else:
            purchased_text = str(purchased_at)
        if hasattr(expires_at, "strftime"):
            expires_text = expires_at.strftime("%Y-%m-%d")
        else:
            expires_text = str(expires_at)
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Provider: {provider}")
        print(f"   Price: ${domain['price']}")
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
    provider = config.get("provider", "porkbun")
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Provider: {provider}")
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
