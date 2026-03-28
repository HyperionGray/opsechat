#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails.

This CLI tool allows easy rotation of domains for burner email services.
It supports Porkbun and Namecheap registrar providers.

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
from domain_manager import DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _serialize_domain_entry(entry):
    """Convert datetime values to strings for JSON storage."""
    normalized = dict(entry)
    for key in ("purchased_at", "expires_at"):
        value = normalized.get(key)
        if isinstance(value, datetime):
            normalized[key] = value.isoformat()
    return normalized


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _deserialize_domain_entry(entry):
    """Convert stored datetime strings back to datetime objects."""
    normalized = dict(entry)
    for key in ("purchased_at", "expires_at"):
        parsed = _parse_datetime(normalized.get(key))
        if parsed is not None:
            normalized[key] = parsed
    return normalized


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
    print("Supported providers:")
    print("  - porkbun")
    print("  - namecheap")
    print()
    
    config = load_config()
    
    print("Current configuration:")
    provider = config.get("provider", "porkbun")
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
    
    selected_provider = input("Provider [porkbun/namecheap] (default: current): ").strip().lower()
    if selected_provider:
        if selected_provider not in ("porkbun", "namecheap"):
            print("Invalid provider; keeping current provider")
        else:
            config["provider"] = selected_provider
    provider = config.get("provider", "porkbun")

    if provider == "porkbun":
        print("\nGet API credentials from: https://porkbun.com/account/api\n")
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            config['api_key'] = api_key
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
    else:
        print("\nNamecheap API setup requires an allowed client IP.")
        print("Docs: https://www.namecheap.com/support/api/intro/\n")
        api_key = input("Namecheap API Key: ").strip()
        if api_key:
            config['api_key'] = api_key
        username = input("Namecheap Username: ").strip()
        if username:
            config["username"] = username
        api_user = input("Namecheap API User (blank = username): ").strip()
        if api_user:
            config["api_user"] = api_user
        client_ip = input("Namecheap Client IP (allowed in API settings): ").strip()
        if client_ip:
            config["client_ip"] = client_ip
    
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

    provider = config.get("provider", "porkbun")
    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))

    if provider == "porkbun":
        if not config.get('api_key') or not config.get('api_secret'):
            print("Error: Porkbun credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        configured = manager.configure(
            api_key=config["api_key"],
            secret_key=config["api_secret"],
            monthly_budget=config.get("monthly_budget", 50.0),
            provider="porkbun",
        )
    elif provider == "namecheap":
        required = ("api_key", "username", "client_ip")
        if not all(config.get(k) for k in required):
            print("Error: Namecheap requires api_key, username, and client_ip.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        configured = manager.configure(
            api_key=config["api_key"],
            provider="namecheap",
            username=config["username"],
            client_ip=config["client_ip"],
            api_user=config.get("api_user"),
            monthly_budget=config.get("monthly_budget", 50.0),
        )
    else:
        print(f"Error: Unsupported provider '{provider}'.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    if not configured.get("success"):
        print(f"Error: {configured.get('message', 'failed to configure domain provider')}")
        sys.exit(1)
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = [
            _deserialize_domain_entry(item)
            for item in config['owned_domains']
        ]
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = [
        _serialize_domain_entry(item)
        for item in manager.owned_domains
    ]
    config['active_domain'] = manager.active_domain
    config['provider'] = manager.get_active_provider() or config.get("provider", "porkbun")
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
        purchased_at_display = purchased_at.strftime('%Y-%m-%d %H:%M') if hasattr(purchased_at, "strftime") else str(purchased_at)
        expires_at_display = expires_at.strftime('%Y-%m-%d') if hasattr(expires_at, "strftime") else str(expires_at)
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Provider: {provider}")
        print(f"   Purchased: {purchased_at_display}")
        print(f"   Expires: {expires_at_display}")
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
            print(
                "  Found: "
                f"{domain_info['domain']} - ${domain_info['price']} "
                f"({domain_info.get('provider', 'unknown')})"
            )
        else:
            print("  No cheap domain found in this attempt")
    
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

    print(
        f"\nFound: {domain_info['domain']} for ${domain_info['price']} "
        f"via {domain_info.get('provider', 'unknown')}"
    )
    
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
    manager, config = get_manager()
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"Active Provider: {manager.get_active_provider() or 'None'}")
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
