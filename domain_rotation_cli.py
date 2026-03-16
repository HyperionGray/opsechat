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


def _masked_key(api_key):
    if not api_key:
        return "Not configured"
    return f"{'*' * max(len(api_key) - 4, 0)}{api_key[-4:]}"


def _format_dt(value, fmt):
    if isinstance(value, datetime):
        return value.strftime(fmt)
    return str(value) if value else "Unknown"


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("This tool supports Porkbun API for domain management.")
    print("You can get API credentials from: https://porkbun.com/account/api\n")
    
    config = load_config()
    
    print("Current configuration:")
    print(f"  API Key: {_masked_key(config.get('api_key'))}")
    
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
    print("\n[OK] Configuration updated successfully.")


def get_manager(require_api=True):
    """Get configured domain manager"""
    config = load_config()
    
    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))
    has_api_credentials = bool(config.get('api_key') and config.get('api_secret'))

    if has_api_credentials:
        manager.configure(
            api_key=config['api_key'],
            secret_key=config['api_secret'],
            monthly_budget=config.get('monthly_budget', 50.0),
        )
    elif require_api:
        print("[ERROR] API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    # Load saved state (new format first, then legacy fallback)
    state = config.get("state")
    if isinstance(state, dict):
        manager.import_state(state)
    else:
        manager.import_state({
            "current_spending": config.get("current_spending"),
            "owned_domains": config.get("owned_domains", []),
            "active_domain": config.get("active_domain"),
        })
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    state = manager.export_state()
    config['state'] = state
    config['monthly_budget'] = manager.monthly_budget
    # Keep legacy keys for backwards compatibility with older configs/tools.
    config['current_spending'] = state['current_spending']
    config['owned_domains'] = state['owned_domains']
    config['active_domain'] = state['active_domain']
    save_config(config)


def list_domains():
    """List owned domains"""
    manager, _ = get_manager(require_api=False)
    
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
        print(f"   Purchased: {_format_dt(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_dt(domain.get('expires_at'), '%Y-%m-%d')}")
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, _ = get_manager(require_api=True)
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
        
        if domain_info:
            print(f"  [OK] Found: {domain_info['domain']} - ${domain_info['price']}")
        else:
            print(f"  [NOPE] No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain():
    """Rotate to a new domain"""
    manager, config = get_manager(require_api=True)
    
    print("\n=== Domain Rotation ===\n")
    
    budget_status = manager.get_budget_status()
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Budget Cycle: {budget_status['budget_cycle']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")
    
    if budget_status['remaining'] < 1:
        print("[ERROR] Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(max_price=min(5.0, budget_status['remaining']))
    
    if not domain_info:
        print("[ERROR] Could not find an available cheap domain within budget.")
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
        print(f"\n[OK] Successfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\n[ERROR] Failed to purchase domain. Check API credentials and budget.")


def show_status():
    """Show current status"""
    manager, _ = get_manager(require_api=False)
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"  Cycle: {budget_status['budget_cycle']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")
    
    if manager.active_domain:
        print(f"\n[OK] Current burner email domain: {manager.active_domain}")
        print(f"   Configure your email system to use: user@{manager.active_domain}")


def activate_domain(domain):
    """Set an owned domain as the active domain."""
    manager, config = get_manager(require_api=False)

    if not domain:
        print("[ERROR] Domain is required. Example: python domain_rotation_cli.py activate example.xyz")
        return

    if manager.set_active_domain(domain):
        save_manager_state(manager, config)
        print(f"[OK] Active domain set to: {domain}")
    else:
        print(f"[ERROR] Domain not found in owned domains: {domain}")


def prune_expired_domains():
    """Remove expired domains from local state."""
    manager, config = get_manager(require_api=False)
    removed = manager.remove_expired_domains()
    save_manager_state(manager, config)
    print(f"[OK] Removed {removed} expired domain(s).")


def reset_budget():
    """Manually reset spending for the current budget cycle."""
    manager, config = get_manager(require_api=False)
    manager.reset_budget()
    save_manager_state(manager, config)
    print("[OK] Budget spending reset to $0.00.")


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
  python domain_rotation_cli.py activate example.xyz
  python domain_rotation_cli.py prune-expired
  python domain_rotation_cli.py reset-budget
        """
    )
    
    parser.add_argument(
        'command',
        choices=[
            'config', 'status', 'search', 'rotate', 'list',
            'activate', 'prune-expired', 'reset-budget'
        ],
        help='Command to execute'
    )
    parser.add_argument(
        'domain',
        nargs='?',
        help='Domain value used by the activate command'
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
    elif args.command == 'activate':
        activate_domain(args.domain)
    elif args.command == 'prune-expired':
        prune_expired_domains()
    elif args.command == 'reset-budget':
        reset_budget()


if __name__ == '__main__':
    main()
