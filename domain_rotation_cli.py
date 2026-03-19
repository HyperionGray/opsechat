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


def _normalize_config(config):
    """
    Normalize legacy config shape into registrar-aware structure.
    """
    normalized = dict(config or {})
    registrars = dict(normalized.get("registrars", {}))

    # Backwards compatibility with legacy single-provider fields.
    if normalized.get("api_key") and normalized.get("api_secret") and "porkbun" not in registrars:
        registrars["porkbun"] = {
            "api_key": normalized["api_key"],
            "api_secret": normalized["api_secret"],
        }

    normalized["registrars"] = registrars

    if "active_provider" not in normalized:
        normalized["active_provider"] = "porkbun" if "porkbun" in registrars else None

    return normalized


def _serialize_owned_domains(owned_domains):
    """Convert datetimes to ISO strings for JSON persistence."""
    serialized = []
    for domain_info in owned_domains:
        item = dict(domain_info)
        for key in ("purchased_at", "expires_at"):
            value = item.get(key)
            if isinstance(value, datetime):
                item[key] = value.isoformat()
        serialized.append(item)
    return serialized


def _deserialize_owned_domains(owned_domains):
    """Convert persisted ISO timestamps back to datetime objects."""
    restored = []
    for domain_info in owned_domains or []:
        item = dict(domain_info)
        for key in ("purchased_at", "expires_at"):
            value = item.get(key)
            if isinstance(value, str):
                try:
                    item[key] = datetime.fromisoformat(value)
                except ValueError:
                    item[key] = value
        restored.append(item)
    return restored


def _format_datetime(value, fmt):
    if isinstance(value, datetime):
        return value.strftime(fmt)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime(fmt)
        except ValueError:
            return value
    return "unknown"


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return _normalize_config({})
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return _normalize_config(json.load(f))
    except Exception as e:
        print(f"Error loading config: {e}")
        return _normalize_config({})


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
    print("This tool supports Porkbun and Namecheap for domain management.")
    print("Porkbun docs:   https://porkbun.com/account/api")
    print("Namecheap docs: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    registrars = dict(config.get("registrars", {}))
    
    print("Current configuration:")
    porkbun = registrars.get("porkbun", {})
    if porkbun.get('api_key'):
        print(f"  Porkbun API Key: {'*' * 20}{porkbun['api_key'][-4:]}")
    else:
        print("  Porkbun API Key: Not configured")

    namecheap = registrars.get("namecheap", {})
    if namecheap.get('api_key'):
        print(f"  Namecheap API Key: {'*' * 20}{namecheap['api_key'][-4:]}")
    else:
        print("  Namecheap API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")

    print(f"  Active Provider: {config.get('active_provider') or 'Not set'}")
    
    print("\nEnter new values (or press Enter to keep current):\n")
    
    porkbun_api_key = input("Porkbun API Key: ").strip()
    if porkbun_api_key:
        porkbun["api_key"] = porkbun_api_key
    
    porkbun_api_secret = getpass("Porkbun API Secret: ").strip()
    if porkbun_api_secret:
        porkbun["api_secret"] = porkbun_api_secret

    enable_namecheap = input("Configure Namecheap as backup provider? (yes/no) [no]: ").strip().lower()
    if enable_namecheap == "yes":
        namecheap_api_key = input("Namecheap API Key: ").strip()
        if namecheap_api_key:
            namecheap["api_key"] = namecheap_api_key

        namecheap_username = input("Namecheap Username: ").strip()
        if namecheap_username:
            namecheap["username"] = namecheap_username

        client_ip = input("Namecheap API Client IP (must be allowlisted): ").strip()
        if client_ip:
            namecheap["client_ip"] = client_ip

        use_sandbox = input("Use Namecheap sandbox? (yes/no) [no]: ").strip().lower()
        if use_sandbox in ("yes", "no"):
            namecheap["use_sandbox"] = use_sandbox == "yes"

    if porkbun:
        registrars["porkbun"] = porkbun
    if namecheap:
        registrars["namecheap"] = namecheap

    config["registrars"] = registrars
    
    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config['monthly_budget'] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif 'monthly_budget' not in config:
        config['monthly_budget'] = 50.0

    active_provider = input("Active provider [porkbun/namecheap] (blank keeps current): ").strip().lower()
    if active_provider in ("porkbun", "namecheap"):
        if active_provider in registrars:
            config["active_provider"] = active_provider
        else:
            print(f"Provider '{active_provider}' is not configured; keeping existing active provider.")
    
    save_config(config)
    print("\n✅ Configuration updated successfully!")


def get_manager():
    """Get configured domain manager"""
    config = load_config()

    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))
    registrars = config.get("registrars", {})

    porkbun = registrars.get("porkbun", {})
    if porkbun.get("api_key") and porkbun.get("api_secret"):
        manager.add_api_client(
            "porkbun",
            PorkbunAPIClient(porkbun["api_key"], porkbun["api_secret"]),
            set_active=False,
        )

    namecheap = registrars.get("namecheap", {})
    if namecheap.get("api_key") and namecheap.get("username"):
        manager.add_api_client(
            "namecheap",
            NamecheapAPIClient(
                api_key=namecheap["api_key"],
                username=namecheap["username"],
                api_user=namecheap.get("api_user") or namecheap.get("username"),
                client_ip=namecheap.get("client_ip", "127.0.0.1"),
                use_sandbox=bool(namecheap.get("use_sandbox", False)),
            ),
            set_active=False,
        )

    if not manager.list_providers():
        print("❌ Error: No API credentials configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    if config.get("active_provider"):
        manager.set_active_provider(config["active_provider"])
    elif "porkbun" in manager.list_providers():
        manager.set_active_provider("porkbun")
    
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
    config['active_provider'] = manager.get_active_provider()
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
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Provider: {provider}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'), '%Y-%m-%d')}")
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
    print(f"Active Provider: {manager.get_active_provider() or 'none'}")
    print(f"Configured Providers: {', '.join(manager.list_providers())}\n")
    
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
    print(f"Active Provider: {manager.get_active_provider() or 'none'}")
    print(f"Configured Providers: {', '.join(manager.list_providers()) or 'none'}")
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
