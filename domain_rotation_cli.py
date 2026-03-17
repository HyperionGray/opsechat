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
    python domain_rotation_cli.py cleanup       # Remove expired local state
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from getpass import getpass
from domain_manager import PorkbunAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'
STATE_VERSION = 1


def _parse_datetime(value):
    """Parse datetime value from config, supporting legacy formats."""
    if isinstance(value, datetime):
        return value

    if not value:
        return None

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (ValueError, OSError):
            return None

    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            pass

    return None


def _serialize_datetime(value):
    """Serialize datetime value for JSON storage."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _normalize_owned_domains(raw_domains):
    """
    Normalize domain state loaded from config.
    Ensures datetime fields are datetime objects and price is numeric.
    """
    normalized_domains = []
    now = datetime.now()

    for raw in raw_domains or []:
        if not isinstance(raw, dict):
            continue

        domain = raw.get("domain")
        if not domain:
            continue

        try:
            price = float(raw.get("price", 0.0))
        except (TypeError, ValueError):
            price = 0.0

        purchased_at = _parse_datetime(raw.get("purchased_at")) or now
        expires_at = _parse_datetime(raw.get("expires_at")) or (purchased_at + timedelta(days=365))

        normalized_domains.append({
            "domain": domain,
            "price": price,
            "purchased_at": purchased_at,
            "expires_at": expires_at
        })

    return normalized_domains


def _serialize_owned_domains(owned_domains):
    """Serialize domain state with datetime-safe values for JSON."""
    serialized = []
    for domain in owned_domains or []:
        if not isinstance(domain, dict):
            continue
        serialized.append({
            "domain": domain.get("domain"),
            "price": domain.get("price"),
            "purchased_at": _serialize_datetime(domain.get("purchased_at")),
            "expires_at": _serialize_datetime(domain.get("expires_at"))
        })
    return serialized


def cleanup_expired_domains(manager):
    """Remove expired domains from local state and repair active pointer."""
    now = datetime.now()
    before_count = len(manager.owned_domains)

    cleaned = []
    for domain in manager.owned_domains:
        expires_at = _parse_datetime(domain.get("expires_at"))
        if not expires_at or expires_at < now:
            continue
        cleaned.append(domain)

    manager.owned_domains = cleaned
    owned_domain_names = {d["domain"] for d in manager.owned_domains}
    if manager.active_domain not in owned_domain_names:
        manager.active_domain = manager.owned_domains[-1]["domain"] if manager.owned_domains else None

    return before_count - len(manager.owned_domains)


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
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    
    # Load saved state
    if "current_spending" in config:
        try:
            manager.current_spending = float(config['current_spending'])
        except (TypeError, ValueError):
            manager.current_spending = 0.0

    manager.owned_domains = _normalize_owned_domains(config.get('owned_domains', []))
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']

    # Repair active domain if state is stale or missing.
    owned_names = {d["domain"] for d in manager.owned_domains}
    if manager.active_domain not in owned_names and manager.owned_domains:
        manager.active_domain = manager.owned_domains[-1]["domain"]
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['state_version'] = STATE_VERSION
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _serialize_owned_domains(manager.owned_domains)
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
        print(f"   Purchased: {domain['purchased_at'].strftime('%Y-%m-%d %H:%M')}")
        print(f"   Expires: {domain['expires_at'].strftime('%Y-%m-%d')}")
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


def cleanup_domains():
    """Prune expired local domains from saved state."""
    manager, config = get_manager()

    print("\n=== Domain State Cleanup ===\n")
    removed_count = cleanup_expired_domains(manager)
    save_manager_state(manager, config)

    print(f"Removed {removed_count} expired domain record(s).")
    print(f"Remaining domain records: {len(manager.owned_domains)}")
    print(f"Active domain: {manager.active_domain or 'None'}")


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
  python domain_rotation_cli.py cleanup    # Remove expired local domains
        """
    )
    
    parser.add_argument(
        'command',
        choices=['config', 'status', 'search', 'rotate', 'list', 'cleanup'],
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
    elif args.command == 'cleanup':
        cleanup_domains()


if __name__ == '__main__':
    main()
