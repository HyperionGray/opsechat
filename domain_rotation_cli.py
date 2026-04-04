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
from domain_manager import PorkbunAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'

DEFAULT_SEARCH_TLDS = ["xyz", "club", "online", "site", "website"]
DEFAULT_MAX_SEARCH_PRICE = 5.0


def _safe_float(value, default):
    """Convert value to float with fallback default."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_tld_list(raw_value):
    """Parse comma-separated TLDs into normalized list."""
    if not raw_value:
        return []

    if isinstance(raw_value, list):
        values = raw_value
    else:
        values = str(raw_value).split(",")

    normalized = []
    seen = set()
    for value in values:
        tld = str(value).strip().lower().lstrip(".")
        if tld and tld not in seen:
            normalized.append(tld)
            seen.add(tld)

    return normalized


def _iso_datetime(value):
    """Convert datetime to ISO-8601 string."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _parse_datetime(value):
    """Parse ISO-8601 datetime values; leave unknown values unchanged."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _serialize_owned_domains(domains):
    """Serialize owned domain records for JSON persistence."""
    serialized = []
    for domain in domains or []:
        if not isinstance(domain, dict):
            continue
        entry = dict(domain)
        entry["purchased_at"] = _iso_datetime(entry.get("purchased_at"))
        entry["expires_at"] = _iso_datetime(entry.get("expires_at"))
        serialized.append(entry)
    return serialized


def _deserialize_owned_domains(domains):
    """Deserialize owned domain records from JSON persistence."""
    deserialized = []
    for domain in domains or []:
        if not isinstance(domain, dict):
            continue
        entry = dict(domain)
        entry["purchased_at"] = _parse_datetime(entry.get("purchased_at"))
        entry["expires_at"] = _parse_datetime(entry.get("expires_at"))
        entry["price"] = _safe_float(entry.get("price"), entry.get("price"))
        deserialized.append(entry)
    return deserialized


def _format_timestamp(value, fmt):
    """Format timestamps safely for CLI output."""
    parsed = _parse_datetime(value)
    if isinstance(parsed, datetime):
        return parsed.strftime(fmt)
    if parsed in (None, ""):
        return "N/A"
    return str(parsed)


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
    print("This tool supports Porkbun API for domain management.")
    print("You can get API credentials from: https://porkbun.com/account/api\n")
    
    config = load_config()
    
    print("Current configuration:")
    if config.get('api_key'):
        print(f"  API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    if config.get('search_tlds'):
        print(f"  Search TLDs: {', '.join(config['search_tlds'])}")
    else:
        print(f"  Search TLDs: {', '.join(DEFAULT_SEARCH_TLDS)} (default)")
    if 'max_search_price' in config:
        print(f"  Max Search Price: ${config['max_search_price']}")
    else:
        print(f"  Max Search Price: ${DEFAULT_MAX_SEARCH_PRICE} (default)")
    
    print("\nEnter new values (or press Enter to keep current):\n")
    
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

    tlds = input(
        f"Preferred TLDs (comma-separated) [default: {','.join(DEFAULT_SEARCH_TLDS)}]: "
    ).strip()
    if tlds:
        parsed_tlds = _parse_tld_list(tlds)
        if parsed_tlds:
            config['search_tlds'] = parsed_tlds
        else:
            print("Invalid TLD list, keeping previous/default value")
    elif 'search_tlds' not in config:
        config['search_tlds'] = DEFAULT_SEARCH_TLDS

    max_price = input(f"Max domain search price [default: {DEFAULT_MAX_SEARCH_PRICE}]: ").strip()
    if max_price:
        parsed_price = _safe_float(max_price, None)
        if parsed_price is None or parsed_price <= 0:
            print("Invalid max search price, keeping previous/default value")
        else:
            config['max_search_price'] = parsed_price
    elif 'max_search_price' not in config:
        config['max_search_price'] = DEFAULT_MAX_SEARCH_PRICE
    
    save_config(config)
    print("\n✅ Configuration updated successfully!")


def get_manager():
    """Get configured domain manager"""
    config = load_config()
    
    if not config.get('api_key') or not config.get('api_secret'):
        print("❌ Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)
    
    client = PorkbunAPIClient(config['api_key'], config['api_secret'])
    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=_safe_float(config.get('monthly_budget', 50.0), 50.0)
    )
    
    # Load saved state
    if 'current_spending' in config:
        manager.current_spending = _safe_float(config['current_spending'], 0.0)
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
    config['monthly_budget'] = manager.monthly_budget
    if 'search_tlds' not in config:
        config['search_tlds'] = DEFAULT_SEARCH_TLDS
    if 'max_search_price' not in config:
        config['max_search_price'] = DEFAULT_MAX_SEARCH_PRICE
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
        print(f"   Price: ${domain.get('price', 'N/A')}")
        print(f"   Purchased: {_format_timestamp(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_timestamp(domain.get('expires_at'), '%Y-%m-%d')}")
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, config = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    configured_tlds = _parse_tld_list(config.get('search_tlds')) or DEFAULT_SEARCH_TLDS
    max_price = _safe_float(config.get('max_search_price', DEFAULT_MAX_SEARCH_PRICE), DEFAULT_MAX_SEARCH_PRICE)
    print(f"Searching for domains under ${max_price} in TLDs: {', '.join(configured_tlds)}\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=1,
            tld_candidates=configured_tlds
        )
        
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
    configured_tlds = _parse_tld_list(config.get('search_tlds')) or DEFAULT_SEARCH_TLDS
    max_price = _safe_float(config.get('max_search_price', DEFAULT_MAX_SEARCH_PRICE), DEFAULT_MAX_SEARCH_PRICE)
    
    domain_info = manager.find_cheap_available_domain(
        max_price=min(max_price, budget_status['remaining']),
        tld_candidates=configured_tlds
    )
    
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
