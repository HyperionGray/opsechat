#!/usr/bin/env python3
"""
Domain rotation CLI for burner email domains.

Supported registrars:
- Porkbun
- Namecheap
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


def _parse_datetime(value):
    """Parse datetime values loaded from JSON config."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _restore_owned_domains(raw_domains):
    """Restore owned domains from persisted JSON-safe representation."""
    restored = []
    for item in raw_domains or []:
        domain = dict(item)
        purchased_at = _parse_datetime(domain.get("purchased_at"))
        expires_at = _parse_datetime(domain.get("expires_at"))
        if purchased_at is not None:
            domain["purchased_at"] = purchased_at
        if expires_at is not None:
            domain["expires_at"] = expires_at
        restored.append(domain)
    return restored


def _serialize_owned_domains(domains):
    """Serialize owned domains for JSON persistence."""
    serialized = []
    for item in domains:
        domain = dict(item)
        purchased_at = domain.get("purchased_at")
        expires_at = domain.get("expires_at")
        if isinstance(purchased_at, datetime):
            domain["purchased_at"] = purchased_at.isoformat()
        if isinstance(expires_at, datetime):
            domain["expires_at"] = expires_at.isoformat()
        serialized.append(domain)
    return serialized


def _prompt_with_default(prompt, default_value):
    shown_default = default_value if default_value is not None else ""
    value = input(f"{prompt} [{shown_default}]: ").strip()
    if value:
        return value
    return default_value


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars: porkbun, namecheap")
    print("Porkbun API: https://porkbun.com/account/api")
    print("Namecheap API: https://www.namecheap.com/support/api/\n")
    
    config = load_config()
    current_registrar = config.get("registrar", "porkbun")
    
    print("Current configuration:")
    print(f"  Registrar: {current_registrar}")

    if current_registrar == "porkbun":
        current_key = config.get("porkbun_api_key") or config.get("api_key")
        if current_key:
            print(f"  Porkbun API Key: {'*' * 20}{current_key[-4:]}")
        else:
            print("  Porkbun API Key: Not configured")
    elif current_registrar == "namecheap":
        current_user = config.get("namecheap_api_user")
        current_ip = config.get("namecheap_client_ip", "127.0.0.1")
        print(f"  Namecheap API User: {current_user or 'Not configured'}")
        print(f"  Namecheap Client IP: {current_ip}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    registrar = _prompt_with_default("Registrar (porkbun/namecheap)", current_registrar)
    registrar = (registrar or "porkbun").strip().lower()
    if registrar not in ("porkbun", "namecheap"):
        print("Invalid registrar. Keeping previous registrar.")
        registrar = current_registrar
    config["registrar"] = registrar

    if registrar == "porkbun":
        api_key = _prompt_with_default("Porkbun API Key", config.get("porkbun_api_key") or config.get("api_key"))
        if api_key:
            config["porkbun_api_key"] = api_key
        api_secret = getpass("Porkbun API Secret [hidden]: ").strip()
        if api_secret:
            config["porkbun_api_secret"] = api_secret
    else:
        api_user = _prompt_with_default("Namecheap API User", config.get("namecheap_api_user"))
        if api_user:
            config["namecheap_api_user"] = api_user
        api_key = getpass("Namecheap API Key [hidden]: ").strip()
        if api_key:
            config["namecheap_api_key"] = api_key
        username = _prompt_with_default("Namecheap Username", config.get("namecheap_username") or api_user)
        if username:
            config["namecheap_username"] = username
        client_ip = _prompt_with_default("Namecheap Client IP", config.get("namecheap_client_ip", "127.0.0.1"))
        if client_ip:
            config["namecheap_client_ip"] = client_ip
        sandbox_default = "yes" if config.get("namecheap_sandbox") else "no"
        sandbox_input = _prompt_with_default("Use Namecheap sandbox (yes/no)", sandbox_default)
        config["namecheap_sandbox"] = str(sandbox_input).lower() in ("1", "y", "yes", "true", "on")
    
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

    registrar = config.get("registrar", "porkbun").lower().strip()
    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))

    try:
        if registrar == "porkbun":
            api_key = config.get("porkbun_api_key") or config.get("api_key")
            api_secret = config.get("porkbun_api_secret") or config.get("api_secret")
            if not api_key or not api_secret:
                raise ValueError("Porkbun credentials not configured")
            manager.configure(
                registrar="porkbun",
                api_key=api_key,
                secret_key=api_secret,
                monthly_budget=config.get("monthly_budget", 50.0),
            )
        elif registrar == "namecheap":
            api_user = config.get("namecheap_api_user")
            api_key = config.get("namecheap_api_key")
            if not api_user or not api_key:
                raise ValueError("Namecheap credentials not configured")
            manager.configure(
                registrar="namecheap",
                api_key=api_user,
                secret_key=api_key,
                monthly_budget=config.get("monthly_budget", 50.0),
                username=config.get("namecheap_username"),
                client_ip=config.get("namecheap_client_ip", "127.0.0.1"),
                sandbox=bool(config.get("namecheap_sandbox", False)),
                contact_profile=config.get("namecheap_contact_profile"),
            )
        else:
            raise ValueError(f"Unsupported registrar '{registrar}'")
    except ValueError as exc:
        print(f"Error: {exc}")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    # Load saved state
    if "current_spending" in config:
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = _restore_owned_domains(config['owned_domains'])
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    if config.get("active_registrar"):
        manager.set_active_registrar(config["active_registrar"])

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = _serialize_owned_domains(manager.owned_domains)
    config['active_domain'] = manager.active_domain
    config['active_registrar'] = manager.active_registrar
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
        registrar = domain.get("registrar", manager.active_registrar or "unknown")
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Registrar: {registrar}")
        print(f"   Price: ${domain['price']}")
        purchased_at = _parse_datetime(domain.get("purchased_at"))
        expires_at = _parse_datetime(domain.get("expires_at"))
        if purchased_at:
            print(f"   Purchased: {purchased_at.strftime('%Y-%m-%d %H:%M')}")
        if expires_at:
            print(f"   Expires: {expires_at.strftime('%Y-%m-%d')}")
        print()


def search_domains():
    """Search for available cheap domains"""
    manager, _ = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Active registrar: {manager.active_registrar}")
    print("Searching for domains under $5...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
        
        if domain_info:
            print(f"  Found: {domain_info['domain']} - ${domain_info['price']} ({domain_info.get('registrar')})")
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
    print(f"Domains Owned: {budget_status['domains_owned']}")
    print(f"Active Registrar: {budget_status.get('active_registrar')}\n")
    
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
        f"via {domain_info.get('registrar', manager.active_registrar)}"
    )
    
    confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Purchase cancelled.")
        return
    
    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price'],
        registrar=domain_info.get("registrar")
    )
    
    if success:
        print(f"\nSuccessfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\nFailed to purchase domain. Check credentials, registrar profile, and budget.")


def show_status():
    """Show current status"""
    manager, _ = get_manager()
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")
    print(f"Active Registrar: {budget_status.get('active_registrar')}")
    print("Configured Registrars: " + ", ".join(budget_status.get("available_registrars", [])))
    
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
