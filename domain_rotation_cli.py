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
from domain_manager import (
    DomainRotationManager,
    NamecheapAPIClient,
    PorkbunAPIClient,
)


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _mask_value(value: str) -> str:
    """Mask sensitive values for terminal display."""
    if not value:
        return "Not configured"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * 20}{value[-4:]}"


def _prompt_bool(prompt: str, default: bool = False) -> bool:
    """Prompt for a yes/no value."""
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "true", "1"}


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
    print("Supported registrars: porkbun, namecheap")
    print("Porkbun API credentials: https://porkbun.com/account/api")
    print("Namecheap API access: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    current_registrar = config.get('registrar', 'porkbun')
    
    print("Current configuration:")
    print(f"  Registrar: {current_registrar}")
    print(f"  API Key: {_mask_value(config.get('api_key', ''))}")
    if current_registrar == "porkbun":
        print(f"  API Secret: {_mask_value(config.get('api_secret', ''))}")
    else:
        print(f"  API User: {config.get('namecheap_api_user', 'Not configured')}")
        print(f"  Username: {config.get('namecheap_username', 'Not configured')}")
        print(f"  Client IP: {config.get('namecheap_client_ip', 'Not configured')}")
        print(f"  Use Sandbox: {bool(config.get('namecheap_use_sandbox', False))}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    registrar = input(f"Registrar [porkbun/namecheap] [{current_registrar}]: ").strip().lower()
    if registrar:
        if registrar not in {"porkbun", "namecheap"}:
            print("Invalid registrar selected. Keeping existing value.")
            registrar = current_registrar
    else:
        registrar = current_registrar
    config['registrar'] = registrar

    api_key = input("API Key: ").strip()
    if api_key:
        config['api_key'] = api_key

    if registrar == "porkbun":
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
        # Remove stale Namecheap-specific fields.
        config.pop('namecheap_api_user', None)
        config.pop('namecheap_username', None)
        config.pop('namecheap_client_ip', None)
        config.pop('namecheap_use_sandbox', None)
    else:
        api_user = input(f"Namecheap API User [{config.get('namecheap_api_user', '')}]: ").strip()
        if api_user:
            config['namecheap_api_user'] = api_user

        username = input(
            f"Namecheap Username [{config.get('namecheap_username', config.get('namecheap_api_user', ''))}]: "
        ).strip()
        if username:
            config['namecheap_username'] = username

        client_ip = input(f"Namecheap Client IP [{config.get('namecheap_client_ip', '127.0.0.1')}]: ").strip()
        if client_ip:
            config['namecheap_client_ip'] = client_ip
        elif 'namecheap_client_ip' not in config:
            config['namecheap_client_ip'] = "127.0.0.1"

        use_sandbox = _prompt_bool(
            "Use Namecheap sandbox API",
            bool(config.get('namecheap_use_sandbox', False)),
        )
        config['namecheap_use_sandbox'] = use_sandbox
        # Remove stale Porkbun-specific secret if switching registrars.
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


def get_manager():
    """Get configured domain manager"""
    config = load_config()

    registrar = config.get("registrar", "porkbun")
    if not config.get("api_key"):
        print("❌ Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(monthly_budget=config.get("monthly_budget", 50.0))
    if registrar == "namecheap":
        if not config.get("namecheap_api_user"):
            print("❌ Error: Namecheap api_user is not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = NamecheapAPIClient(
            api_key=config["api_key"],
            api_user=config["namecheap_api_user"],
            username=config.get("namecheap_username"),
            client_ip=config.get("namecheap_client_ip"),
            use_sandbox=bool(config.get("namecheap_use_sandbox", False)),
        )
        manager.set_api_client(client)
        manager.registrar = "namecheap"
        manager.registrar_settings = {
            "registrar": "namecheap",
            "api_user": config.get("namecheap_api_user"),
            "username": config.get("namecheap_username") or config.get("namecheap_api_user"),
            "client_ip": config.get("namecheap_client_ip", "127.0.0.1"),
            "use_sandbox": bool(config.get("namecheap_use_sandbox", False)),
        }
    else:
        if not config.get("api_secret"):
            print("❌ Error: Porkbun api_secret is not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = PorkbunAPIClient(config["api_key"], config["api_secret"])
        manager.set_api_client(client)
        manager.registrar = "porkbun"
        manager.registrar_settings = {"registrar": "porkbun"}

    # Load saved state. Prefer manager_state, fallback to legacy keys.
    if config.get("manager_state"):
        manager.import_state(config["manager_state"])
    else:
        manager.import_state(
            {
                "monthly_budget": config.get("monthly_budget", 50.0),
                "current_spending": config.get("current_spending", 0.0),
                "owned_domains": config.get("owned_domains", []),
                "active_domain": config.get("active_domain"),
                "registrar": manager.registrar,
                "registrar_settings": manager.registrar_settings,
            }
        )

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    state = manager.export_state()
    config['manager_state'] = state
    # Keep legacy keys for backward compatibility with older configs.
    config['current_spending'] = state["current_spending"]
    config['owned_domains'] = state["owned_domains"]
    config['active_domain'] = state["active_domain"]
    config['monthly_budget'] = state["monthly_budget"]
    save_config(config)


def list_domains():
    """List owned domains"""
    manager, config = get_manager()
    
    print("\n=== Owned Domains ===\n")
    print(f"Registrar: {manager.registrar}\n")
    
    domains = manager.get_owned_domains()
    
    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return
    
    for i, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain['domain'] == manager.active_domain else ""
        purchased_at = domain.get("purchased_at")
        expires_at = domain.get("expires_at")
        if not hasattr(purchased_at, "strftime"):
            purchased_at = str(purchased_at)
        else:
            purchased_at = purchased_at.strftime('%Y-%m-%d %H:%M')
        if not hasattr(expires_at, "strftime"):
            expires_at = str(expires_at)
        else:
            expires_at = expires_at.strftime('%Y-%m-%d')

        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {purchased_at}")
        print(f"   Expires: {expires_at}")
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, config = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Registrar: {manager.registrar}")
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
    print(f"Registrar: {manager.registrar}\n")
    
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
    print(f"Registrar: {manager.registrar}")
    
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
