#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails.

This CLI tool allows easy rotation of domains for burner email services.
It supports multiple registrars and provider fallback.

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


def _prompt_keep_current(prompt: str, current: str = "") -> str:
    suffix = f" [current: {current}]" if current else ""
    return input(f"{prompt}{suffix}: ").strip()


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _migrate_legacy_config(config):
    """
    Upgrade older flat Porkbun config into the registrars map.
    """
    registrars = config.get("registrars")
    if not isinstance(registrars, dict):
        registrars = {}
        config["registrars"] = registrars

    if "api_key" in config and "api_secret" in config:
        if "porkbun" not in registrars:
            registrars["porkbun"] = {
                "api_key": config.get("api_key", ""),
                "api_secret": config.get("api_secret", ""),
            }
        config.pop("api_key", None)
        config.pop("api_secret", None)

    if "default_registrar" not in config:
        if "porkbun" in registrars:
            config["default_registrar"] = "porkbun"
        elif registrars:
            config["default_registrar"] = sorted(registrars.keys())[0]

    if "monthly_budget" not in config:
        config["monthly_budget"] = 50.0

    return config


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return _migrate_legacy_config(json.load(f))
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


def _configure_porkbun(config):
    registrars = config.setdefault("registrars", {})
    current = registrars.get("porkbun", {})
    print("\nPorkbun configuration:")
    print("Get credentials from: https://porkbun.com/account/api\n")

    api_key = _prompt_keep_current("Porkbun API Key", current.get("api_key", ""))
    api_secret = getpass("Porkbun API Secret (leave blank to keep current): ").strip()

    if not current:
        current = {}
    if api_key:
        current["api_key"] = api_key
    if api_secret:
        current["api_secret"] = api_secret

    registrars["porkbun"] = current


def _configure_namecheap(config):
    registrars = config.setdefault("registrars", {})
    current = registrars.get("namecheap", {})
    contact = dict(current.get("contact_profile", {}))

    print("\nNamecheap configuration:")
    print("Get credentials from: https://www.namecheap.com/support/api/intro/\n")

    api_key = _prompt_keep_current("Namecheap API Key", current.get("api_key", ""))
    username = _prompt_keep_current("Namecheap Username", current.get("username", ""))
    client_ip = _prompt_keep_current("Namecheap Client IP", current.get("client_ip", "127.0.0.1"))
    sandbox_prompt = _prompt_keep_current(
        "Use Namecheap sandbox? (yes/no)",
        "yes" if _to_bool(current.get("sandbox", False)) else "no",
    )
    sandbox = _to_bool(sandbox_prompt) if sandbox_prompt else _to_bool(current.get("sandbox", False))

    print("\nNamecheap contact profile (required for purchases, optional for searches):")
    for key, label in (
        ("first_name", "First Name"),
        ("last_name", "Last Name"),
        ("organization_name", "Organization Name"),
        ("address1", "Address Line 1"),
        ("city", "City"),
        ("state_province", "State/Province"),
        ("postal_code", "Postal Code"),
        ("country", "Country (2-letter ISO, e.g. US)"),
        ("phone", "Phone (+1.5555555555)"),
        ("email_address", "Email Address"),
    ):
        value = _prompt_keep_current(label, contact.get(key, ""))
        if value:
            contact[key] = value

    entry = dict(current) if current else {}
    if api_key:
        entry["api_key"] = api_key
    if username:
        entry["username"] = username
    if client_ip:
        entry["client_ip"] = client_ip
    entry["sandbox"] = sandbox
    entry["contact_profile"] = contact
    registrars["namecheap"] = entry


def configure_api(registrar=None):
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars: porkbun, namecheap")
    
    config = load_config()
    _migrate_legacy_config(config)
    
    print("Current configuration:")
    registrars = config.get("registrars", {})
    if registrars:
        for provider in sorted(registrars.keys()):
            entry = registrars.get(provider, {})
            configured = bool(entry.get("api_key"))
            print(f"  {provider}: {'configured' if configured else 'not configured'}")
    else:
        print("  No registrar credentials configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")

    current_default = config.get("default_registrar", "")
    selected = (registrar or "").strip().lower()
    if not selected:
        selected = _prompt_keep_current(
            "Registrar to configure (porkbun/namecheap)",
            current_default or "porkbun",
        ).lower()
    if selected not in {"porkbun", "namecheap"}:
        print(f"Unsupported registrar: {selected}")
        return

    print("\nEnter new values (or press Enter to keep current):\n")

    if selected == "porkbun":
        _configure_porkbun(config)
    else:
        _configure_namecheap(config)

    default_registrar = _prompt_keep_current(
        "Default registrar (porkbun/namecheap)",
        config.get("default_registrar", selected),
    ).lower()
    if default_registrar in {"porkbun", "namecheap"}:
        if default_registrar in config.get("registrars", {}):
            config["default_registrar"] = default_registrar
        else:
            print(f"Warning: {default_registrar} is not configured yet; keeping current default.")
    
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
    _migrate_legacy_config(config)

    manager = DomainRotationManager(
        monthly_budget=config.get('monthly_budget', 50.0)
    )

    registrars = config.get("registrars", {})
    if not isinstance(registrars, dict):
        registrars = {}

    porkbun = registrars.get("porkbun", {})
    if porkbun.get("api_key") and porkbun.get("api_secret"):
        manager.add_api_client(
            "porkbun",
            PorkbunAPIClient(porkbun["api_key"], porkbun["api_secret"]),
            set_primary=False,
        )

    namecheap = registrars.get("namecheap", {})
    if namecheap.get("api_key") and namecheap.get("username"):
        manager.add_api_client(
            "namecheap",
            NamecheapAPIClient(
                api_key=namecheap["api_key"],
                username=namecheap["username"],
                client_ip=namecheap.get("client_ip", "127.0.0.1"),
                sandbox=_to_bool(namecheap.get("sandbox", False)),
                contact_profile=namecheap.get("contact_profile", {}),
            ),
            set_primary=False,
        )

    if not manager.api_clients:
        print("Error: No API credentials configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    default_registrar = config.get("default_registrar")
    if default_registrar and not manager.set_primary_provider(default_registrar):
        print(
            f"Warning: default registrar '{default_registrar}' is not configured; "
            "using first available registrar."
        )
    
    # Keep backward-compatible attribute populated for callers that expect it.
    if manager.primary_provider:
        manager.api_client = manager.api_clients[manager.primary_provider]
    
    # Load saved state
    manager.import_state(config)
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config.update(manager.export_state())
    save_config(config)


def _as_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


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
        provider = domain.get("provider", "unknown")
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Provider: {provider}")

        purchased_at = _as_datetime(domain.get("purchased_at"))
        expires_at = _as_datetime(domain.get("expires_at"))
        if purchased_at:
            print(f"   Purchased: {purchased_at.strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"   Purchased: {domain.get('purchased_at', 'unknown')}")
        if expires_at:
            print(f"   Expires: {expires_at.strftime('%Y-%m-%d')}")
        else:
            print(f"   Expires: {domain.get('expires_at', 'unknown')}")
        print()


def search_domains(provider=None):
    """Search for available cheap domains"""
    manager, _ = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    if provider:
        print(f"Using provider: {provider}")
    else:
        print("Using all configured providers (primary first)")
    print("Searching for domains under $5...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(
            max_price=5.0,
            max_attempts=1,
            provider=provider,
        )
        
        if domain_info:
            print(
                f"  Found: {domain_info['domain']} - ${domain_info['price']} "
                f"(provider: {domain_info.get('provider', 'unknown')})"
            )
        else:
            print("  No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(provider=None):
    """Rotate to a new domain"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation ===\n")
    
    budget_status = manager.get_budget_status()
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")
    print(f"Primary Provider: {budget_status.get('primary_provider') or 'none'}")
    providers = ", ".join(budget_status.get("providers", [])) or "none"
    print(f"Configured Providers: {providers}\n")
    
    if budget_status['remaining'] < 1:
        print("Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(
        max_price=min(5.0, budget_status['remaining']),
        provider=provider,
    )
    
    if not domain_info:
        print("Could not find an available cheap domain within budget.")
        return
    
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']}")
    print(f"Provider: {domain_info.get('provider', 'unknown')}")
    
    confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Purchase cancelled.")
        return
    
    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price'],
        provider=domain_info.get('provider') or provider,
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
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"  Primary Provider: {budget_status.get('primary_provider') or 'none'}")
    print(f"  Configured Providers: {', '.join(budget_status.get('providers', [])) or 'none'}")
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
  python domain_rotation_cli.py config --registrar porkbun     # Configure Porkbun
  python domain_rotation_cli.py config --registrar namecheap   # Configure Namecheap
  python domain_rotation_cli.py status     # Show current status
  python domain_rotation_cli.py search     # Search for available domains
  python domain_rotation_cli.py rotate --provider porkbun      # Rotate using one provider
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
        help='Registrar to configure (used with config command)'
    )
    parser.add_argument(
        '--provider',
        choices=['porkbun', 'namecheap'],
        help='Restrict search/rotation to one provider'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api(registrar=args.registrar)
    elif args.command == 'status':
        show_status()
    elif args.command == 'search':
        search_domains(provider=args.provider)
    elif args.command == 'rotate':
        rotate_domain(provider=args.provider)
    elif args.command == 'list':
        list_domains()


if __name__ == '__main__':
    main()
