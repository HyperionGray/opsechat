#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It integrates with multiple registrars (Porkbun and Namecheap).

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


def _upgrade_legacy_config(config):
    """Upgrade legacy single-registrar config in-place."""
    if not config:
        return {}

    registrars = config.get("registrars", {})
    if config.get("api_key") and config.get("api_secret") and "porkbun" not in registrars:
        registrars["porkbun"] = {
            "api_key": config.get("api_key", ""),
            "api_secret": config.get("api_secret", "")
        }
        config["default_registrar"] = config.get("default_registrar", "porkbun")

    config["registrars"] = registrars
    return config


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return _upgrade_legacy_config(json.load(f))
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
    print("Supported registrars:")
    print("  1) Porkbun")
    print("  2) Namecheap")
    print("\nPorkbun API: https://porkbun.com/account/api")
    print("Namecheap API: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    registrars = config.setdefault("registrars", {})
    
    print("Current configuration:")
    print(f"  Default Registrar: {config.get('default_registrar', 'not set')}")
    print(f"  Configured Registrars: {', '.join(sorted(registrars.keys())) or 'none'}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter registrar configuration:\n")
    registrar_choice = input("Registrar [porkbun/namecheap] (default: porkbun): ").strip().lower() or "porkbun"
    if registrar_choice not in {"porkbun", "namecheap"}:
        print("Invalid registrar choice.")
        return

    if registrar_choice == "porkbun":
        api_key = input("Porkbun API Key: ").strip()
        api_secret = getpass("Porkbun API Secret: ").strip()
        if not api_key or not api_secret:
            print("Porkbun requires both API key and API secret.")
            return
        registrars["porkbun"] = {"api_key": api_key, "api_secret": api_secret}
    else:
        api_key = input("Namecheap API Key: ").strip()
        username = input("Namecheap Username: ").strip()
        client_ip = input("Namecheap Client IP (default: 127.0.0.1): ").strip() or "127.0.0.1"
        if not api_key or not username:
            print("Namecheap requires API key and username.")
            return
        registrars["namecheap"] = {
            "api_key": api_key,
            "username": username,
            "client_ip": client_ip
        }

    if input(f"Set '{registrar_choice}' as default registrar? [Y/n]: ").strip().lower() != "n":
        config["default_registrar"] = registrar_choice
    
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

    registrars = config.get("registrars", {})
    if not registrars:
        print("Error: No registrar credentials configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))

    porkbun_cfg = registrars.get("porkbun")
    if porkbun_cfg and porkbun_cfg.get("api_key") and porkbun_cfg.get("api_secret"):
        manager.add_api_client(
            "porkbun",
            PorkbunAPIClient(porkbun_cfg["api_key"], porkbun_cfg["api_secret"])
        )

    namecheap_cfg = registrars.get("namecheap")
    if namecheap_cfg and namecheap_cfg.get("api_key") and namecheap_cfg.get("username"):
        manager.add_api_client(
            "namecheap",
            NamecheapAPIClient(
                api_key=namecheap_cfg["api_key"],
                username=namecheap_cfg["username"],
                client_ip=namecheap_cfg.get("client_ip", "127.0.0.1")
            )
        )

    available = manager.get_available_registrars()
    if not available:
        print("Error: Config exists but no valid registrar credentials were found.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    default_registrar = config.get("default_registrar")
    if default_registrar in available:
        manager.set_default_registrar(default_registrar)
    else:
        manager.set_default_registrar(available[0])
        config["default_registrar"] = available[0]
    
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
    config['owned_domains'] = manager.owned_domains
    config['active_domain'] = manager.active_domain
    config['default_registrar'] = manager.default_registrar
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
        if domain.get("registrar"):
            print(f"   Registrar: {domain['registrar']}")
        purchased_at = _parse_dt(domain.get("purchased_at"))
        expires_at = _parse_dt(domain.get("expires_at"))
        print(f"   Purchased: {purchased_at.strftime('%Y-%m-%d %H:%M') if purchased_at else domain.get('purchased_at', 'n/a')}")
        print(f"   Expires: {expires_at.strftime('%Y-%m-%d') if expires_at else domain.get('expires_at', 'n/a')}")
        print()


def _parse_dt(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def show_registrars():
    """List configured registrars and selected default."""
    manager, config = get_manager()
    print("\n=== Registrar Configuration ===\n")
    print(f"Default registrar: {manager.default_registrar}")
    print("Configured registrars:")
    for registrar in manager.get_available_registrars():
        marker = " (default)" if registrar == manager.default_registrar else ""
        print(f"  - {registrar}{marker}")


def search_domains():
    """Search for available cheap domains"""
    manager, config = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5 across configured registrars...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
        
        if domain_info:
            registrar = domain_info.get("registrar", "unknown")
            print(f"  Found: {domain_info['domain']} - ${domain_info['price']} via {registrar}")
        else:
            print("  No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain():
    """Rotate to a new domain"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation ===\n")
    print(f"Default Registrar: {manager.default_registrar}")
    
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
    
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']} via {domain_info.get('registrar', 'unknown')}")
    
    confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Purchase cancelled.")
        return
    
    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price'],
        registrar=domain_info.get('registrar')
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
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")
    
    print(f"\nRegistrars configured: {', '.join(manager.get_available_registrars())}")
    print(f"Default registrar: {manager.default_registrar}")

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
  python domain_rotation_cli.py config      # Configure a registrar
  python domain_rotation_cli.py status     # Show current status
  python domain_rotation_cli.py search     # Search for available domains
  python domain_rotation_cli.py rotate     # Rotate to a new domain
  python domain_rotation_cli.py list       # List owned domains
  python domain_rotation_cli.py registrars # Show configured registrars
        """
    )
    
    parser.add_argument(
        'command',
        choices=['config', 'status', 'search', 'rotate', 'list', 'registrars'],
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
    elif args.command == 'registrars':
        show_registrars()


if __name__ == '__main__':
    main()
