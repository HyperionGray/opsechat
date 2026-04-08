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

from domain_manager import DomainRotationManager, NamecheapAPIClient, PorkbunAPIClient


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'
NAMECHEAP_CONTACT_FIELDS = [
    "FirstName",
    "LastName",
    "Address1",
    "City",
    "StateProvince",
    "PostalCode",
    "Country",
    "Phone",
    "EmailAddress",
]


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


def _prompt_namecheap_contact(config):
    """Prompt for Namecheap contact profile required for purchases."""
    existing = config.get("namecheap_default_contact", {})
    prompt_now = input(
        "Configure Namecheap contact profile now? [yes/no] "
        "(required for purchases): "
    ).strip().lower()
    if prompt_now not in {"yes", "y"}:
        return

    contact = {}
    print("\nEnter Namecheap contact profile values:")
    for field in NAMECHEAP_CONTACT_FIELDS:
        default_value = existing.get(field, "")
        value = input(f"  {field} [{default_value}]: ").strip()
        contact[field] = value or default_value

    missing = [field for field in NAMECHEAP_CONTACT_FIELDS if not contact.get(field)]
    if missing:
        print(
            f"Contact profile not saved. Missing required fields: {', '.join(missing)}"
        )
        return

    config["namecheap_default_contact"] = contact
    print("Namecheap contact profile saved.")


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars:")
    print("  - Porkbun (simple API, recommended)")
    print("  - Namecheap (requires account whitelist/client IP)\n")
    
    config = load_config()
    
    print("Current configuration:")
    print(f"  Registrar: {config.get('registrar', 'porkbun')}")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    registrar_default = config.get("registrar", "porkbun")
    registrar = input(f"Registrar [porkbun/namecheap] (default: {registrar_default}): ").strip().lower()
    if registrar in {"porkbun", "namecheap"}:
        config["registrar"] = registrar
    elif registrar:
        print("Invalid registrar; keeping previous value")
    else:
        config["registrar"] = registrar_default
    
    api_key = input("API Key: ").strip()
    if api_key:
        config['api_key'] = api_key
    
    if config["registrar"] == "porkbun":
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config["api_secret"] = api_secret

    if config["registrar"] == "namecheap":
        username = input(
            f"Namecheap Username (default: {config.get('namecheap_username', '')}): "
        ).strip()
        if username:
            config["namecheap_username"] = username

        api_user = input(
            f"Namecheap API User (optional, default: {config.get('namecheap_api_user', '')}): "
        ).strip()
        if api_user:
            config["namecheap_api_user"] = api_user

        client_ip = input(
            f"Namecheap Client IP (default: {config.get('namecheap_client_ip', '127.0.0.1')}): "
        ).strip()
        if client_ip:
            config["namecheap_client_ip"] = client_ip
        elif "namecheap_client_ip" not in config:
            config["namecheap_client_ip"] = "127.0.0.1"

        use_sandbox = input(
            f"Use Namecheap sandbox? [yes/no] (default: {'yes' if config.get('namecheap_use_sandbox') else 'no'}): "
        ).strip().lower()
        if use_sandbox in {"yes", "y"}:
            config["namecheap_use_sandbox"] = True
        elif use_sandbox in {"no", "n"}:
            config["namecheap_use_sandbox"] = False
        _prompt_namecheap_contact(config)
    
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
    registrar = config.get("registrar", "porkbun")

    if registrar == "namecheap":
        username = config.get("namecheap_username")
        if not username:
            print("❌ Error: Namecheap username not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = NamecheapAPIClient(
            api_key=config["api_key"],
            username=username,
            api_user=config.get("namecheap_api_user"),
            client_ip=config.get("namecheap_client_ip", "127.0.0.1"),
            use_sandbox=bool(config.get("namecheap_use_sandbox", False)),
            default_contact=config.get("namecheap_default_contact"),
        )
    else:
        if not config.get("api_secret"):
            print("❌ Error: Porkbun API secret not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = PorkbunAPIClient(config['api_key'], config['api_secret'])

    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0),
        registrar=registrar,
    )
    
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
        serialized = dict(domain)
        purchased_at = serialized.get("purchased_at")
        if isinstance(purchased_at, datetime):
            serialized["purchased_at"] = purchased_at.isoformat()
        expires_at = serialized.get("expires_at")
        if isinstance(expires_at, datetime):
            serialized["expires_at"] = expires_at.isoformat()
        serialized_domains.append(serialized)
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
        purchased_at = domain.get('purchased_at')
        if isinstance(purchased_at, str):
            try:
                purchased_at = datetime.fromisoformat(purchased_at)
            except ValueError:
                purchased_at = None

        expires_at = domain.get('expires_at')
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except ValueError:
                expires_at = None

        active = " [ACTIVE]" if domain['domain'] == manager.active_domain else ""
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {purchased_at.strftime('%Y-%m-%d %H:%M') if purchased_at else 'unknown'}")
        print(f"   Expires: {expires_at.strftime('%Y-%m-%d') if expires_at else 'unknown'}")
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
