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
from typing import Any, Dict, Tuple

from domain_manager import DomainRotationManager


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


def _prompt_optional(prompt_text: str, current_value: Any = None, secret: bool = False) -> str:
    """Prompt for a value while allowing Enter to keep existing."""
    suffix = " (press Enter to keep current)" if current_value else ""
    if secret:
        return getpass(f"{prompt_text}{suffix}: ").strip()
    return input(f"{prompt_text}{suffix}: ").strip()


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _format_date(value: Any, fmt: str) -> str:
    if hasattr(value, "strftime"):
        return value.strftime(fmt)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime(fmt)
        except Exception:
            return value
    return "Unknown"


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars:")
    print("  - porkbun   (https://porkbun.com/account/api)")
    print("  - namecheap (https://www.namecheap.com/support/api/intro/)\n")
    
    config = load_config()
    current_registrar = config.get('registrar', 'porkbun')
    
    print("Current configuration:")
    print(f"  Registrar: {current_registrar}")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    if current_registrar == "namecheap":
        print(f"  Username: {config.get('username', 'Not configured')}")
        print(f"  Client IP: {config.get('client_ip', 'Not configured')}")
        print(f"  API User: {config.get('api_user', config.get('username', 'Not configured'))}")
        print(f"  Sandbox: {config.get('sandbox', False)}")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    registrar_input = input(f"Registrar [porkbun/namecheap] [{current_registrar}]: ").strip().lower()
    registrar = registrar_input if registrar_input else current_registrar
    if registrar not in {"porkbun", "namecheap"}:
        print("Invalid registrar. Keeping current registrar.")
        registrar = current_registrar
    config['registrar'] = registrar
    
    api_key = _prompt_optional("API Key", config.get("api_key"))
    if api_key:
        config['api_key'] = api_key

    if registrar == "porkbun":
        api_secret = _prompt_optional("Porkbun API Secret", config.get("api_secret"), secret=True)
        if api_secret:
            config['api_secret'] = api_secret
        for key in ("username", "client_ip", "api_user", "sandbox"):
            config.pop(key, None)
    else:
        username = _prompt_optional("Namecheap username", config.get("username"))
        if username:
            config["username"] = username

        client_ip = _prompt_optional("Namecheap client IP", config.get("client_ip"))
        if client_ip:
            config["client_ip"] = client_ip

        api_user = _prompt_optional(
            "Namecheap API user (blank = same as username)",
            config.get("api_user", config.get("username", "")),
        )
        if api_user:
            config["api_user"] = api_user

        sandbox_input = _prompt_optional(
            "Use Namecheap sandbox? [yes/no]",
            "yes" if config.get("sandbox") else "no",
        )
        if sandbox_input:
            config["sandbox"] = _to_bool(sandbox_input)
        config.pop("api_secret", None)
    
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


def get_manager() -> Tuple[DomainRotationManager, Dict[str, Any]]:
    """Get configured domain manager"""
    config = load_config()
    registrar = config.get("registrar", "porkbun").strip().lower()
    
    if not config.get('api_key'):
        print("Error: API key not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))

    try:
        if registrar == "namecheap":
            if not config.get("username") or not config.get("client_ip"):
                print("Error: Namecheap requires username and client_ip.")
                print("Run: python domain_rotation_cli.py config")
                sys.exit(1)

            manager.configure(
                registrar="namecheap",
                api_key=config["api_key"],
                monthly_budget=config.get("monthly_budget", 50.0),
                username=config["username"],
                client_ip=config["client_ip"],
                api_user=config.get("api_user"),
                sandbox=config.get("sandbox", False),
            )
        else:
            if not config.get("api_secret"):
                print("Error: Porkbun requires api_secret.")
                print("Run: python domain_rotation_cli.py config")
                sys.exit(1)
            manager.configure(
                registrar="porkbun",
                api_key=config["api_key"],
                secret_key=config["api_secret"],
                monthly_budget=config.get("monthly_budget", 50.0),
            )
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = DomainRotationManager.deserialize_owned_domains(
            config['owned_domains']
        )
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['registrar'] = manager.registrar
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = DomainRotationManager.serialize_owned_domains(manager.owned_domains)
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
        print(f"   Purchased: {_format_date(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_date(domain.get('expires_at'), '%Y-%m-%d')}")
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
    
    print(f"Registrar: {manager.registrar}")
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
        description='OpSecChat Domain Rotation CLI',
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
