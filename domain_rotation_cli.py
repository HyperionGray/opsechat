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


def _current_month_key(now=None):
    """Return YYYY-MM for budget tracking."""
    if now is None:
        now = datetime.utcnow()
    return now.strftime('%Y-%m')


def _parse_datetime(value):
    """Parse ISO datetime strings safely."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    if candidate.endswith('Z'):
        candidate = candidate[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _serialize_datetime(value):
    """Convert datetime values to JSON-safe strings."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _deserialize_owned_domains(raw_domains):
    """Normalize loaded domain records from config."""
    if not isinstance(raw_domains, list):
        return []

    normalized_domains = []
    for domain in raw_domains:
        if not isinstance(domain, dict):
            continue
        item = dict(domain)
        item['purchased_at'] = _parse_datetime(item.get('purchased_at'))
        item['expires_at'] = _parse_datetime(item.get('expires_at'))
        normalized_domains.append(item)
    return normalized_domains


def _serialize_owned_domains(domains):
    """Prepare domain records for JSON storage."""
    serialized_domains = []
    for domain in domains:
        if not isinstance(domain, dict):
            continue
        item = dict(domain)
        item['purchased_at'] = _serialize_datetime(item.get('purchased_at'))
        item['expires_at'] = _serialize_datetime(item.get('expires_at'))
        serialized_domains.append(item)
    return serialized_domains


def _reset_monthly_spending_if_needed(config):
    """
    Reset tracked spending when a new month starts.

    Returns:
        bool: True when the config state changed.
    """
    current_month = _current_month_key()
    previous_month = config.get('budget_month')

    if previous_month == current_month:
        return False

    config['budget_month'] = current_month

    # Keep existing spending when initializing first-time config.
    if previous_month is not None:
        config['current_spending'] = 0.0
    else:
        config['current_spending'] = float(config.get('current_spending', 0.0) or 0.0)

    return True


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                return loaded
            return {}
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def save_config(config, quiet=False):
    """Save configuration to file"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2, sort_keys=True)
        os.chmod(CONFIG_FILE, 0o600)  # Secure permissions
        if not quiet:
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
    
    _reset_monthly_spending_if_needed(config)
    save_config(config)
    print("\n✅ Configuration updated successfully!")


def get_manager():
    """Get configured domain manager"""
    config = load_config()
    state_changed = _reset_monthly_spending_if_needed(config)
    
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
    manager.current_spending = float(config.get('current_spending', 0.0) or 0.0)
    manager.owned_domains = _deserialize_owned_domains(config.get('owned_domains', []))
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']

    if state_changed:
        save_config(config, quiet=True)
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _serialize_owned_domains(manager.owned_domains)
    config['active_domain'] = manager.active_domain
    config['budget_month'] = _current_month_key()
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
        purchased_at = domain.get('purchased_at')
        expires_at = domain.get('expires_at')
        purchased_text = (
            purchased_at.strftime('%Y-%m-%d %H:%M')
            if isinstance(purchased_at, datetime) else str(purchased_at or "unknown")
        )
        expires_text = (
            expires_at.strftime('%Y-%m-%d')
            if isinstance(expires_at, datetime) else str(expires_at or "unknown")
        )
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain.get('price', 'unknown')}")
        print(f"   Purchased: {purchased_text}")
        print(f"   Expires: {expires_text}")
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
    print(f"  Period: {config.get('budget_month', _current_month_key())}")
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
