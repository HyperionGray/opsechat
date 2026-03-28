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
from domain_manager import DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _parse_datetime(value):
    """Parse datetime values from persisted config."""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _serialize_owned_domains(domains):
    """Serialize domain state to JSON-friendly values."""
    serialized = []
    for domain in domains or []:
        entry = dict(domain)
        purchased_at = entry.get("purchased_at")
        expires_at = entry.get("expires_at")

        if isinstance(purchased_at, datetime):
            entry["purchased_at"] = purchased_at.isoformat()
        if isinstance(expires_at, datetime):
            entry["expires_at"] = expires_at.isoformat()
        serialized.append(entry)
    return serialized


def _deserialize_owned_domains(domains):
    """Deserialize persisted domain state."""
    restored = []
    for domain in domains or []:
        entry = dict(domain)
        purchased_at = _parse_datetime(entry.get("purchased_at"))
        expires_at = _parse_datetime(entry.get("expires_at"))
        if purchased_at:
            entry["purchased_at"] = purchased_at
        if expires_at:
            entry["expires_at"] = expires_at
        restored.append(entry)
    return restored


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
    print("This tool supports Porkbun and Namecheap for domain management.\n")
    
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
    
    print("\nEnter new values (or press Enter to keep current):")
    print("Supported registrars: porkbun, namecheap\n")
    
    registrar = input(f"Registrar [{current_registrar}]: ").strip().lower()
    if not registrar:
        registrar = current_registrar
    if registrar not in {"porkbun", "namecheap"}:
        print(f"Unsupported registrar '{registrar}', using {current_registrar}")
        registrar = current_registrar
    config['registrar'] = registrar

    api_key = input(f"{registrar.title()} API Key: ").strip()
    if api_key:
        config['api_key'] = api_key

    if registrar == "porkbun":
        print("Get Porkbun API credentials from https://porkbun.com/account/api")
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret

        # Clear Namecheap-only options if switching away
        config.pop('api_username', None)
        config.pop('client_ip', None)
        config.pop('use_sandbox', None)
    else:
        print("Get Namecheap API credentials from https://www.namecheap.com/support/api/intro/")
        api_username = input(
            f"Namecheap API Username [{config.get('api_username', '')}]: "
        ).strip()
        if api_username:
            config['api_username'] = api_username

        client_ip_default = config.get('client_ip', '127.0.0.1')
        client_ip = input(f"Namecheap Client IP [{client_ip_default}]: ").strip()
        config['client_ip'] = client_ip or client_ip_default

        sandbox_default = bool(config.get('use_sandbox', False))
        sandbox_input = input(
            f"Use Namecheap sandbox? [{'yes' if sandbox_default else 'no'}]: "
        ).strip().lower()
        if sandbox_input:
            config['use_sandbox'] = sandbox_input in {"yes", "y", "true", "1"}
        elif 'use_sandbox' not in config:
            config['use_sandbox'] = False

        # Keep backward compatibility, but Namecheap uses api_username.
        if not config.get('api_username') and config.get('api_secret'):
            config['api_username'] = config['api_secret']
    
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

    registrar = config.get('registrar', 'porkbun').strip().lower()

    if not config.get('api_key'):
        print("Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))

    if registrar == "porkbun":
        if not config.get('api_secret'):
            print("Error: Porkbun API secret is missing.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        manager.configure(
            api_key=config['api_key'],
            secret_key=config['api_secret'],
            monthly_budget=config.get('monthly_budget', 50.0),
            registrar='porkbun',
        )
    elif registrar == "namecheap":
        api_username = config.get('api_username') or config.get('api_secret')
        if not api_username:
            print("Error: Namecheap API username is missing.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
        manager.configure(
            api_key=config['api_key'],
            secret_key=api_username,
            monthly_budget=config.get('monthly_budget', 50.0),
            registrar='namecheap',
            api_username=api_username,
            client_ip=config.get('client_ip', '127.0.0.1'),
            use_sandbox=bool(config.get('use_sandbox', False)),
        )
    else:
        print(f"Error: Unsupported registrar '{registrar}'.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)
    
    # Load saved state
    if config.get('current_spending') is not None:
        manager.current_spending = float(config['current_spending'])
    if config.get('owned_domains'):
        manager.owned_domains = _deserialize_owned_domains(config['owned_domains'])
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    if config.get('active_registrar'):
        manager.active_registrar = config['active_registrar']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _serialize_owned_domains(manager.owned_domains)
    config['active_domain'] = manager.active_domain
    config['active_registrar'] = manager.active_registrar
    if manager.active_registrar:
        config['registrar'] = manager.active_registrar
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
        active = " [ACTIVE]" if domain.get('domain') == manager.active_domain else ""
        registrar = domain.get('registrar', manager.active_registrar or 'unknown')
        purchased_at = _parse_datetime(domain.get('purchased_at'))
        expires_at = _parse_datetime(domain.get('expires_at'))
        purchased_str = purchased_at.strftime('%Y-%m-%d %H:%M') if purchased_at else "unknown"
        expires_str = expires_at.strftime('%Y-%m-%d') if expires_at else "unknown"

        print(f"{i}. {domain.get('domain', 'unknown')}{active}")
        print(f"   Registrar: {registrar}")
        print(f"   Price: ${domain.get('price', 'unknown')}")
        print(f"   Purchased: {purchased_str}")
        print(f"   Expires: {expires_str}")
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
            print(
                f"  Found: {domain_info['domain']} - ${domain_info['price']} "
                f"({domain_info.get('registrar', 'unknown')})"
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
        print("Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(max_price=min(5.0, budget_status['remaining']))
    
    if not domain_info:
        print("Could not find an available cheap domain within budget.")
        return
    
    print(
        f"\nFound: {domain_info['domain']} for ${domain_info['price']} "
        f"via {domain_info.get('registrar', 'unknown')}"
    )
    
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
        print("\nFailed to purchase domain. Check API credentials, registrar support, and budget.")


def show_status():
    """Show current status"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"Active Registrar: {budget_status.get('active_registrar') or 'None'}")
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
