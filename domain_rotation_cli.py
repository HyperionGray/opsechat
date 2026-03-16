#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It supports Porkbun and Namecheap registrars.

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
SUPPORTED_REGISTRARS = ("porkbun", "namecheap")


def _serialize_datetime(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _deserialize_datetime(value):
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _serialize_owned_domains(domains):
    serialized = []
    for domain in domains:
        serialized.append({
            **domain,
            "purchased_at": _serialize_datetime(domain.get("purchased_at")),
            "expires_at": _serialize_datetime(domain.get("expires_at")),
        })
    return serialized


def _deserialize_owned_domains(domains):
    deserialized = []
    for domain in domains:
        deserialized.append({
            **domain,
            "purchased_at": _deserialize_datetime(domain.get("purchased_at")),
            "expires_at": _deserialize_datetime(domain.get("expires_at")),
        })
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
    config = load_config()

    current_registrar = config.get("registrar", "porkbun").lower()
    if current_registrar not in SUPPORTED_REGISTRARS:
        current_registrar = "porkbun"

    print("Supported registrars:")
    for registrar in SUPPORTED_REGISTRARS:
        selected = " (current)" if registrar == current_registrar else ""
        print(f"  - {registrar}{selected}")
    print()

    registrar = input(f"Registrar [{current_registrar}]: ").strip().lower() or current_registrar
    if registrar not in SUPPORTED_REGISTRARS:
        print(f"Invalid registrar '{registrar}', keeping {current_registrar}")
        registrar = current_registrar

    config["registrar"] = registrar

    if registrar == "porkbun":
        print("\nPorkbun credentials")
        print("Get API credentials from: https://porkbun.com/account/api\n")

        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            config["api_key"] = api_key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config["api_secret"] = api_secret
    else:
        print("\nNamecheap credentials")
        print("Enable API access from: https://www.namecheap.com/support/api/intro/\n")

        api_key = input("Namecheap API Key: ").strip()
        if api_key:
            config["namecheap_api_key"] = api_key

        username = input("Namecheap Username: ").strip()
        if username:
            config["namecheap_username"] = username

        client_ip = input("Namecheap Client IP [127.0.0.1]: ").strip()
        if client_ip:
            config["namecheap_client_ip"] = client_ip
        elif "namecheap_client_ip" not in config:
            config["namecheap_client_ip"] = "127.0.0.1"

        api_user = input("Namecheap ApiUser (optional, defaults to Username): ").strip()
        if api_user:
            config["namecheap_api_user"] = api_user

    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config["monthly_budget"] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif "monthly_budget" not in config:
        config["monthly_budget"] = 50.0

    save_config(config)
    print("\nConfiguration updated successfully.")


def _build_client_from_config(config):
    registrar = config.get("registrar", "porkbun").lower()
    if registrar == "namecheap":
        api_key = config.get("namecheap_api_key")
        username = config.get("namecheap_username")
        client_ip = config.get("namecheap_client_ip", "127.0.0.1")
        api_user = config.get("namecheap_api_user")
        if not api_key or not username:
            raise ValueError("Namecheap credentials missing (namecheap_api_key/namecheap_username)")
        return (
            NamecheapAPIClient(
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                api_user=api_user,
            ),
            "namecheap",
        )

    api_key = config.get("api_key")
    api_secret = config.get("api_secret")
    if not api_key or not api_secret:
        raise ValueError("Porkbun credentials missing (api_key/api_secret)")
    return (PorkbunAPIClient(api_key, api_secret), "porkbun")


def get_manager():
    """Get configured domain manager"""
    config = load_config()

    try:
        client, registrar = _build_client_from_config(config)
    except ValueError as exc:
        print(f"Error: {exc}")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(
        monthly_budget=config.get("monthly_budget", 50.0)
    )
    manager.add_api_client(registrar, client, make_active=True)

    # Load saved state
    if config.get("current_spending") is not None:
        manager.current_spending = float(config["current_spending"])
    if config.get("owned_domains"):
        manager.owned_domains = _deserialize_owned_domains(config["owned_domains"])
    if config.get("active_domain"):
        manager.active_domain = config["active_domain"]
    if config.get("active_provider"):
        manager.active_provider = config["active_provider"]

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config["current_spending"] = manager.current_spending
    config["owned_domains"] = _serialize_owned_domains(manager.owned_domains)
    config["active_domain"] = manager.active_domain
    config["active_provider"] = manager.active_provider
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
        active = " [ACTIVE]" if domain["domain"] == manager.active_domain else ""
        provider = domain.get("provider", "unknown")
        purchased_at = _deserialize_datetime(domain.get("purchased_at"))
        expires_at = _deserialize_datetime(domain.get("expires_at"))

        if isinstance(purchased_at, datetime):
            purchased_display = purchased_at.strftime("%Y-%m-%d %H:%M")
        else:
            purchased_display = str(purchased_at or "unknown")

        if isinstance(expires_at, datetime):
            expires_display = expires_at.strftime("%Y-%m-%d")
        else:
            expires_display = str(expires_at or "unknown")

        print(f"{i}. {domain['domain']}{active}")
        print(f"   Provider: {provider}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {purchased_display}")
        print(f"   Expires: {expires_display}")
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
            provider = domain_info.get("provider", "unknown")
            print(
                f"  Found: {domain_info['domain']} - ${domain_info['price']} "
                f"(provider: {provider})"
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
        print("❌ Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(max_price=min(5.0, budget_status['remaining']))
    
    if not domain_info:
        print("❌ Could not find an available cheap domain within budget.")
        return
    
    provider = domain_info.get("provider", "unknown")
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']} (provider: {provider})")
    
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
    print(f"Active Provider: {manager.active_provider or 'None'}")
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
