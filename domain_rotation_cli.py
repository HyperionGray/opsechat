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
from typing import Any, Dict, Optional

from domain_manager import (
    DomainRotationManager,
    NamecheapAPIClient,
    PorkbunAPIClient,
)


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO datetime string safely."""
    if isinstance(value, datetime):
        return value
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _deserialize_domain_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Convert serialized domain entry values back to runtime types."""
    parsed = dict(entry)
    purchased_at = _parse_datetime(parsed.get("purchased_at"))
    expires_at = _parse_datetime(parsed.get("expires_at"))
    if purchased_at:
        parsed["purchased_at"] = purchased_at
    if expires_at:
        parsed["expires_at"] = expires_at
    return parsed


def _serialize_domain_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize runtime-only values (e.g. datetimes) for JSON storage."""
    serialized = dict(entry)
    for key in ("purchased_at", "expires_at"):
        value = serialized.get(key)
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
    return serialized


def _format_datetime(value: Any, fmt: str) -> str:
    """Format datetime values while tolerating string-based legacy state."""
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed.strftime(fmt)
    if isinstance(value, str) and value:
        return value
    return "unknown"


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
    print("Supported registrars: Porkbun, Namecheap")
    print("Porkbun docs: https://porkbun.com/account/api")
    print("Namecheap docs: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    current_registrar = config.get("registrar", "porkbun")
    
    print("Current configuration:")
    print(f"  Registrar: {current_registrar}")
    if current_registrar == "namecheap":
        if config.get("api_key"):
            print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
        else:
            print("  API Key: Not configured")
        print(f"  API User: {config.get('namecheap_api_user', 'Not configured')}")
        print(f"  Username: {config.get('namecheap_username', 'Not configured')}")
        print(f"  Client IP: {config.get('namecheap_client_ip', 'Not configured')}")
        if config.get("namecheap_contact_profile"):
            print("  Contact Profile: configured")
        else:
            print("  Contact Profile: not configured")
    else:
        if config.get('api_key'):
            print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
        else:
            print("  API Key: Not configured")
        if config.get('api_secret'):
            print("  API Secret: configured")
        else:
            print("  API Secret: not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    registrar = input(f"Registrar [porkbun/namecheap] (current: {current_registrar}): ").strip().lower()
    if registrar not in {"", "porkbun", "namecheap"}:
        print("Invalid registrar. Keeping current value.")
        registrar = current_registrar
    if not registrar:
        registrar = current_registrar
    config["registrar"] = registrar
    
    api_key = input("Registrar API Key: ").strip()
    if api_key:
        config['api_key'] = api_key

    if registrar == "porkbun":
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
        # Clean Namecheap-specific settings when switching back.
        config.pop("namecheap_api_user", None)
        config.pop("namecheap_username", None)
        config.pop("namecheap_client_ip", None)
        config.pop("namecheap_contact_profile", None)
        config.pop("namecheap_sandbox", None)
    else:
        api_user = input("Namecheap API User: ").strip()
        if api_user:
            config["namecheap_api_user"] = api_user

        username = input("Namecheap Username (default: API User): ").strip()
        if username:
            config["namecheap_username"] = username
        elif api_user:
            config["namecheap_username"] = api_user

        client_ip = input("Namecheap Client IP (required by Namecheap): ").strip()
        if client_ip:
            config["namecheap_client_ip"] = client_ip

        contact_profile_path = input(
            "Optional path to Namecheap contact profile JSON (for purchases): "
        ).strip()
        if contact_profile_path:
            try:
                with open(contact_profile_path, "r", encoding="utf-8") as profile_file:
                    config["namecheap_contact_profile"] = json.load(profile_file)
            except Exception as exc:
                print(f"Could not load contact profile ({exc}); keeping previous value.")

        sandbox = input("Use Namecheap sandbox? [y/N]: ").strip().lower()
        if sandbox:
            config["namecheap_sandbox"] = sandbox in {"y", "yes", "true", "1"}
    
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

    if registrar == "namecheap":
        required = ["api_key", "namecheap_api_user", "namecheap_username", "namecheap_client_ip"]
        missing = [key for key in required if not config.get(key)]
        if missing:
            print(f"❌ Error: Missing Namecheap configuration values: {', '.join(missing)}")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        client = NamecheapAPIClient(
            api_user=config["namecheap_api_user"],
            api_key=config["api_key"],
            username=config["namecheap_username"],
            client_ip=config["namecheap_client_ip"],
            contact_profile=config.get("namecheap_contact_profile"),
            sandbox=bool(config.get("namecheap_sandbox", False)),
        )
    else:
        if not config.get('api_key') or not config.get('api_secret'):
            print("❌ Error: Porkbun credentials not configured.")
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
        manager.owned_domains = [
            _deserialize_domain_entry(domain_entry)
            for domain_entry in config['owned_domains']
        ]
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config["registrar"] = manager.registrar
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = [
        _serialize_domain_entry(domain_entry)
        for domain_entry in manager.owned_domains
    ]
    config['active_domain'] = manager.active_domain
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
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'), '%Y-%m-%d')}")
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, _ = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Using registrar: {manager.registrar}")
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
    print(f"Using registrar: {manager.registrar}")
    
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
    manager, _ = get_manager()
    
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
