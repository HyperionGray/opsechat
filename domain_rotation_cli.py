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
from typing import Any, Dict, List, Optional

from domain_manager import (
    DomainRotationManager,
    NamecheapAPIClient,
    PorkbunAPIClient,
)


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _to_datetime(value: Any) -> Optional[datetime]:
    """Parse datetime values stored as ISO strings or datetime objects."""
    if isinstance(value, datetime):
        return value
    if not value or not isinstance(value, str):
        return None

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _format_datetime(value: Any, fmt: str) -> str:
    dt_value = _to_datetime(value)
    if dt_value is None:
        return "Unknown"
    return dt_value.strftime(fmt)


def _normalize_owned_domains(owned_domains: Any) -> List[Dict[str, Any]]:
    """Normalize persisted domain records for reliable JSON storage."""
    normalized_domains: List[Dict[str, Any]] = []
    if not isinstance(owned_domains, list):
        return normalized_domains

    for domain_info in owned_domains:
        if not isinstance(domain_info, dict):
            continue

        normalized = dict(domain_info)
        purchased_at = normalized.get("purchased_at")
        expires_at = normalized.get("expires_at")

        if isinstance(purchased_at, datetime):
            normalized["purchased_at"] = purchased_at.isoformat() + "Z"
        if isinstance(expires_at, datetime):
            normalized["expires_at"] = expires_at.isoformat() + "Z"

        normalized.setdefault("provider", "unknown")
        normalized_domains.append(normalized)

    return normalized_domains


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
    print("This tool supports Porkbun and Namecheap for domain management.")
    print("Porkbun API docs: https://porkbun.com/account/api")
    print("Namecheap API docs: https://www.namecheap.com/support/api/\n")
    
    config = load_config()
    
    print("Current configuration:")
    registrar = config.get("registrar", "porkbun")
    print(f"  Registrar: {registrar}")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")
    
    registrar_input = input("Registrar (porkbun/namecheap): ").strip().lower()
    if registrar_input:
        if registrar_input not in {"porkbun", "namecheap"}:
            print("Invalid registrar. Use 'porkbun' or 'namecheap'.")
            return
        config["registrar"] = registrar_input

    selected_registrar = config.get("registrar", "porkbun")

    if selected_registrar == "namecheap":
        username = input("Namecheap Username: ").strip()
        if username:
            config["username"] = username

        api_user = input("Namecheap ApiUser [default: username]: ").strip()
        if api_user:
            config["api_user"] = api_user
        elif username and not config.get("api_user"):
            config["api_user"] = username

        client_ip = input("Namecheap Client IP [default: 127.0.0.1]: ").strip()
        if client_ip:
            config["client_ip"] = client_ip
        elif "client_ip" not in config:
            config["client_ip"] = "127.0.0.1"

        api_key = getpass("Namecheap API Key: ").strip()
        if api_key:
            config["api_key"] = api_key
    else:
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            config['api_key'] = api_key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
    
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
    
    registrar = config.get("registrar", "porkbun").strip().lower()

    client: Any
    provider: str
    if registrar == "namecheap":
        if not config.get("api_key") or not config.get("username"):
            print("❌ Error: Namecheap credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = NamecheapAPIClient(
            api_key=config["api_key"],
            username=config["username"],
            api_user=config.get("api_user"),
            client_ip=config.get("client_ip", "127.0.0.1"),
            sandbox=bool(config.get("sandbox", False)),
        )
        provider = "namecheap"
    else:
        api_key = config.get("api_key") or config.get("porkbun_api_key")
        api_secret = config.get("api_secret") or config.get("porkbun_secret_key")
        if not api_key or not api_secret:
            print("❌ Error: Porkbun API credentials not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = PorkbunAPIClient(api_key, api_secret)
        provider = "porkbun"

    manager = DomainRotationManager(monthly_budget=float(config.get('monthly_budget', 50.0)))
    manager.add_api_client(provider, client, make_active=True)

    manager.load_state(
        owned_domains=_normalize_owned_domains(config.get("owned_domains", [])),
        current_spending=float(config.get("current_spending", 0.0) or 0.0),
        active_domain=config.get("active_domain"),
    )
    active_provider = config.get("active_provider")
    if active_provider and active_provider in manager.api_clients:
        manager.active_provider = active_provider
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _normalize_owned_domains(manager.owned_domains)
    config['active_domain'] = manager.active_domain
    config['active_provider'] = manager.active_provider
    save_config(config)


def list_domains():
    """List owned domains"""
    manager, _ = get_manager()
    
    print("\n=== Owned Domains ===\n")
    
    domains = manager.get_owned_domains()
    
    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return
    
    for i, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain['domain'] == manager.active_domain else ""
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Provider: {domain.get('provider', 'unknown')}")
        print(f"   Price: ${domain.get('price', 'unknown')}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'), '%Y-%m-%d')}")
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, _ = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
        
        if domain_info:
            print(
                f"  ✅ Found: {domain_info['domain']} - "
                f"${domain_info['price']} ({domain_info.get('provider', 'unknown')})"
            )
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
        domain_info['price'],
        provider=domain_info.get("provider"),
    )
    
    if success:
        print(f"\n✅ Successfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\n❌ Failed to purchase domain. Check API credentials and budget.")


def show_status():
    """Show current status"""
    manager, _ = get_manager()
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    current_config = manager.get_config()
    print(f"Registrar: {current_config.get('active_provider') or 'unknown'}")
    print(f"Configured Providers: {', '.join(current_config.get('providers', [])) or 'None'}")
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
