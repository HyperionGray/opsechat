#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It supports multiple registrars and registrar fallback.

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
from domain_manager import (
    DomainRotationManager,
    NamecheapAPIClient,
    PorkbunAPIClient,
)


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _normalize_config(config):
    """Migrate legacy config schema to multi-registrar schema."""
    if not isinstance(config, dict):
        return {}

    registrars = config.get('registrars')
    if not isinstance(registrars, dict):
        registrars = {}

    # Backward compatibility: move legacy Porkbun keys into registrars map.
    legacy_api_key = config.pop('api_key', None)
    legacy_api_secret = config.pop('api_secret', None)
    if legacy_api_key or legacy_api_secret:
        porkbun_cfg = registrars.get('porkbun', {})
        if legacy_api_key:
            porkbun_cfg['api_key'] = legacy_api_key
        if legacy_api_secret:
            porkbun_cfg['api_secret'] = legacy_api_secret
        registrars['porkbun'] = porkbun_cfg

    config['registrars'] = registrars

    # Ensure preferred registrar defaults to porkbun if available.
    if not config.get('preferred_registrar') and 'porkbun' in registrars:
        config['preferred_registrar'] = 'porkbun'

    return config


def _parse_datetime(value):
    """Parse datetime from JSON-serialized value."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _serialize_owned_domains(domains):
    """Serialize manager-owned domains for JSON storage."""
    serialized = []
    for domain in domains:
        entry = dict(domain)
        for field in ('purchased_at', 'expires_at'):
            value = entry.get(field)
            if isinstance(value, datetime):
                entry[field] = value.isoformat()
        serialized.append(entry)
    return serialized


def _deserialize_owned_domains(domains):
    """Deserialize JSON-owned domains to runtime values."""
    deserialized = []
    for domain in domains or []:
        entry = dict(domain)
        for field in ('purchased_at', 'expires_at'):
            parsed = _parse_datetime(entry.get(field))
            if parsed:
                entry[field] = parsed
        deserialized.append(entry)
    return deserialized


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return _normalize_config(config)
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
    """Configure registrar API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars:")
    print("  - porkbun")
    print("  - namecheap")
    print("\nPorkbun API: https://porkbun.com/account/api")
    print("Namecheap API: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    
    preferred = config.get('preferred_registrar', 'porkbun')
    print(f"Current preferred registrar: {preferred}")
    print("Configured registrars:")
    for registrar, registrar_cfg in sorted(config.get('registrars', {}).items()):
        has_key = bool(registrar_cfg.get('api_key'))
        state = "configured" if has_key else "incomplete"
        print(f"  - {registrar}: {state}")
    if not config.get('registrars'):
        print("  None configured yet")

    monthly_budget = config.get('monthly_budget')
    if monthly_budget is not None:
        print(f"Monthly Budget: ${monthly_budget}")
    else:
        print("Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")
    
    registrars = config.setdefault('registrars', {})
    registrar = input("Registrar [porkbun/namecheap] (default: porkbun): ").strip().lower() or "porkbun"
    if registrar not in {"porkbun", "namecheap"}:
        print("Invalid registrar. Choose 'porkbun' or 'namecheap'.")
        return

    registrar_cfg = dict(registrars.get(registrar, {}))

    api_key = input(f"{registrar.title()} API Key: ").strip()
    if api_key:
        registrar_cfg['api_key'] = api_key

    if registrar == "porkbun":
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            registrar_cfg['api_secret'] = api_secret
    else:
        username = input("Namecheap Username: ").strip()
        if username:
            registrar_cfg['username'] = username

        api_user = input("Namecheap ApiUser (blank = username): ").strip()
        if api_user:
            registrar_cfg['api_user'] = api_user

        client_ip = input("Namecheap Client IP (whitelisted public IP): ").strip()
        if client_ip:
            registrar_cfg['client_ip'] = client_ip

        sandbox_choice = input("Use Namecheap sandbox? [yes/no] (default: no): ").strip().lower()
        if sandbox_choice in {"yes", "y"}:
            registrar_cfg['sandbox'] = True
        elif sandbox_choice in {"no", "n"}:
            registrar_cfg['sandbox'] = False
    
    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config['monthly_budget'] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif 'monthly_budget' not in config:
        config['monthly_budget'] = 50.0
    
    registrars[registrar] = registrar_cfg
    set_preferred = input(f"Set '{registrar}' as preferred registrar? [yes/no] (default: yes): ").strip().lower()
    if set_preferred in {"", "yes", "y"}:
        config['preferred_registrar'] = registrar

    save_config(_normalize_config(config))
    print("\n✅ Configuration updated successfully!")


def _build_client(registrar, registrar_cfg):
    """Build registrar client from config."""
    if registrar == "porkbun":
        api_key = registrar_cfg.get('api_key')
        api_secret = registrar_cfg.get('api_secret')
        if api_key and api_secret:
            return PorkbunAPIClient(api_key, api_secret)
        return None

    if registrar == "namecheap":
        api_key = registrar_cfg.get('api_key')
        username = registrar_cfg.get('username')
        client_ip = registrar_cfg.get('client_ip')
        if not (api_key and username and client_ip):
            return None
        return NamecheapAPIClient(
            api_key=api_key,
            username=username,
            api_user=registrar_cfg.get('api_user') or username,
            client_ip=client_ip,
            sandbox=bool(registrar_cfg.get('sandbox', False)),
        )

    return None


def get_manager():
    """Get configured domain manager"""
    config = load_config()

    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))

    for registrar, registrar_cfg in sorted(config.get('registrars', {}).items()):
        client = _build_client(registrar, registrar_cfg)
        if client:
            manager.add_api_client(registrar, client)

    preferred = config.get('preferred_registrar')
    if preferred and preferred in manager.get_available_registrars():
        manager.set_preferred_registrar(preferred)

    if not manager.get_available_registrars():
        print("❌ Error: No valid registrar credentials configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
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
    config['preferred_registrar'] = manager.preferred_registrar
    save_config(config)


def list_domains(registrar=None):
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
        if domain.get("registrar"):
            print(f"   Registrar: {domain['registrar']}")
        print(f"   Price: ${domain['price']}")
        purchased_at = domain.get('purchased_at')
        expires_at = domain.get('expires_at')
        if isinstance(purchased_at, datetime):
            print(f"   Purchased: {purchased_at.strftime('%Y-%m-%d %H:%M')}")
        if isinstance(expires_at, datetime):
            print(f"   Expires: {expires_at.strftime('%Y-%m-%d')}")
        print()


def search_domains(registrar=None):
    """Search for available cheap domains"""
    manager, config = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")
    
    if registrar:
        print(f"Using registrar: {registrar}")

    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(
            max_price=5.0,
            max_attempts=1,
            registrar=registrar,
        )
        
        if domain_info:
            print(
                "  ✅ Found: "
                f"{domain_info['domain']} - ${domain_info['price']} "
                f"({domain_info.get('registrar', 'unknown')})"
            )
        else:
            print(f"  ❌ No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(registrar=None):
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
    
    if registrar:
        print(f"Registrar override: {registrar}")

    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(
        max_price=min(5.0, budget_status['remaining']),
        registrar=registrar,
    )
    
    if not domain_info:
        print("❌ Could not find an available cheap domain within budget.")
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
        domain_info['price'],
        registrar=domain_info.get('registrar') or registrar,
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
    print(f"Preferred Registrar: {budget_status.get('preferred_registrar') or 'None'}")
    print(
        "Configured Registrars: "
        + (", ".join(budget_status.get('available_registrars', [])) or "None")
    )
    
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
    parser.add_argument(
        '--registrar',
        choices=['porkbun', 'namecheap'],
        help='Optional registrar override for search/rotate/list'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status()
    elif args.command == 'search':
        search_domains(registrar=args.registrar)
    elif args.command == 'rotate':
        rotate_domain(registrar=args.registrar)
    elif args.command == 'list':
        list_domains(registrar=args.registrar)


if __name__ == '__main__':
    main()
