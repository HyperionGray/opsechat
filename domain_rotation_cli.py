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
from domain_manager import (
    DomainRotationManager,
    SUPPORTED_REGISTRARS,
    create_domain_api_client,
)


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'
DEFAULT_PROVIDER = "porkbun"


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


def _mask_secret(value):
    if not value:
        return "Not configured"
    return f"{'*' * 12}{str(value)[-4:]}"


def _coerce_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def serialize_owned_domains(domains):
    """Convert datetime fields into JSON-safe strings."""
    serialized = []
    for item in domains or []:
        if not isinstance(item, dict):
            continue
        converted = dict(item)
        for key in ("purchased_at", "expires_at"):
            if isinstance(converted.get(key), datetime):
                converted[key] = converted[key].isoformat()
        serialized.append(converted)
    return serialized


def deserialize_owned_domains(domains):
    """Parse datetime strings back into datetime objects when possible."""
    parsed = []
    for item in domains or []:
        if not isinstance(item, dict):
            continue
        converted = dict(item)
        for key in ("purchased_at", "expires_at"):
            value = converted.get(key)
            if isinstance(value, str):
                try:
                    converted[key] = datetime.fromisoformat(value)
                except ValueError:
                    pass
        parsed.append(converted)
    return parsed


def _prompt_namecheap_contact_profile(existing):
    profile = dict(existing or {})
    print("\nOptional: default Namecheap contact profile for purchases.")
    print("Leave blank to keep existing value.\n")
    fields = [
        ("first_name", "First Name"),
        ("last_name", "Last Name"),
        ("address1", "Address Line 1"),
        ("city", "City"),
        ("state", "State/Province"),
        ("postal_code", "Postal Code"),
        ("country", "Country Code (e.g. US)"),
        ("phone", "Phone (+1.5555555555 format)"),
        ("email", "Email"),
    ]
    for key, label in fields:
        prompt = f"{label} [{profile.get(key, '')}]: " if profile.get(key) else f"{label}: "
        value = input(prompt).strip()
        if value:
            profile[key] = value
    return profile


def configure_api(provider_override=None):
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print(f"Supported providers: {', '.join(SUPPORTED_REGISTRARS)}\n")

    config = load_config()
    current_provider = (provider_override or config.get("provider") or DEFAULT_PROVIDER).lower()
    if current_provider not in SUPPORTED_REGISTRARS:
        current_provider = DEFAULT_PROVIDER

    print(f"Current provider: {current_provider}")
    provider_input = input(
        f"Provider [{current_provider}] ({'/'.join(SUPPORTED_REGISTRARS)}): "
    ).strip().lower()
    provider = provider_input or current_provider
    if provider not in SUPPORTED_REGISTRARS:
        print(f"Invalid provider '{provider}', defaulting to {DEFAULT_PROVIDER}")
        provider = DEFAULT_PROVIDER
    config["provider"] = provider

    print("\nCurrent configuration:")
    if provider == "porkbun":
        print(f"  API Key: {_mask_secret(config.get('porkbun_api_key') or config.get('api_key'))}")
        print(f"  API Secret: {_mask_secret(config.get('porkbun_api_secret') or config.get('api_secret'))}")
    elif provider == "namecheap":
        print(f"  Username: {config.get('namecheap_username', 'Not configured')}")
        print(f"  API Key: {_mask_secret(config.get('namecheap_api_key'))}")
        print(f"  Client IP: {config.get('namecheap_client_ip', '127.0.0.1')}")
        print(f"  Sandbox: {bool(config.get('namecheap_sandbox', False))}")

    if config.get("monthly_budget") is not None:
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")

    print("\nEnter new values (or press Enter to keep current):\n")

    if provider == "porkbun":
        print("Porkbun API docs: https://porkbun.com/account/api")
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            config["porkbun_api_key"] = api_key
            config["api_key"] = api_key  # Backward-compatible key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config["porkbun_api_secret"] = api_secret
            config["api_secret"] = api_secret  # Backward-compatible key

    elif provider == "namecheap":
        print("Namecheap API docs: https://www.namecheap.com/support/api/intro/")
        username = input(f"Namecheap Username [{config.get('namecheap_username', '')}]: ").strip()
        if username:
            config["namecheap_username"] = username

        api_key = input("Namecheap API Key: ").strip()
        if api_key:
            config["namecheap_api_key"] = api_key

        client_ip = input(f"Client IP [{config.get('namecheap_client_ip', '127.0.0.1')}]: ").strip()
        if client_ip:
            config["namecheap_client_ip"] = client_ip
        elif "namecheap_client_ip" not in config:
            config["namecheap_client_ip"] = "127.0.0.1"

        sandbox_input = input(
            f"Use Namecheap sandbox? [current: {bool(config.get('namecheap_sandbox', False))}] (y/N): "
        ).strip()
        if sandbox_input:
            config["namecheap_sandbox"] = _coerce_bool(sandbox_input)

        configure_contact = input("Configure default Namecheap contact profile now? (y/N): ").strip()
        if configure_contact and _coerce_bool(configure_contact):
            config["namecheap_contact_profile"] = _prompt_namecheap_contact_profile(
                config.get("namecheap_contact_profile")
            )

    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config["monthly_budget"] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif "monthly_budget" not in config:
        config["monthly_budget"] = 50.0

    save_config(config)
    print("\nConfiguration updated successfully.")


def get_manager(provider_override=None):
    """Get configured domain manager"""
    config = load_config()

    provider = (provider_override or config.get("provider") or DEFAULT_PROVIDER).lower()
    if provider not in SUPPORTED_REGISTRARS:
        print(f"Error: unsupported provider '{provider}'.")
        print(f"Supported providers: {', '.join(SUPPORTED_REGISTRARS)}")
        sys.exit(1)

    try:
        if provider == "porkbun":
            api_key = config.get("porkbun_api_key") or config.get("api_key")
            api_secret = config.get("porkbun_api_secret") or config.get("api_secret")
            client = create_domain_api_client(
                provider,
                api_key=api_key,
                api_secret=api_secret,
            )
        else:
            client = create_domain_api_client(
                provider,
                api_key=config.get("namecheap_api_key"),
                username=config.get("namecheap_username"),
                client_ip=config.get("namecheap_client_ip", "127.0.0.1"),
                sandbox=bool(config.get("namecheap_sandbox", False)),
                contact_profile=config.get("namecheap_contact_profile"),
            )
    except ValueError as exc:
        print(f"Error: {exc}")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get("monthly_budget", 50.0)
    )

    # Load saved state
    if config.get("current_spending"):
        manager.current_spending = config["current_spending"]
    if config.get("owned_domains"):
        manager.owned_domains = deserialize_owned_domains(config["owned_domains"])
    if config.get("active_domain"):
        manager.active_domain = config["active_domain"]

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config["current_spending"] = manager.current_spending
    config["owned_domains"] = serialize_owned_domains(manager.owned_domains)
    config["active_domain"] = manager.active_domain
    save_config(config)


def _format_datetime(value, fmt):
    if isinstance(value, datetime):
        return value.strftime(fmt)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime(fmt)
        except ValueError:
            return value
    return "unknown"


def list_domains(provider_override=None):
    """List owned domains"""
    manager, _ = get_manager(provider_override)

    print("\n=== Owned Domains ===\n")

    domains = manager.get_owned_domains()

    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return

    for i, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain.get("domain") == manager.active_domain else ""
        print(f"{i}. {domain.get('domain', 'unknown')}{active}")
        print(f"   Price: ${domain.get('price', 'n/a')}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'), '%Y-%m-%d %H:%M')}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'), '%Y-%m-%d')}")
        print()


def search_domains(provider_override=None):
    """Search for available cheap domains"""
    manager, _ = get_manager(provider_override)

    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")

    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)

        if domain_info:
            provider = domain_info.get("provider") or (provider_override or "current-provider")
            print(f"  Found: {domain_info['domain']} - ${domain_info['price']} ({provider})")
        else:
            print("  No cheap domain found in this attempt")

    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(provider_override=None):
    """Rotate to a new domain"""
    manager, config = get_manager(provider_override)

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
        print(f"\nSuccessfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\nFailed to purchase domain. Check API credentials and budget.")


def show_status(provider_override=None):
    """Show current status"""
    manager, config = get_manager(provider_override)

    print("\n=== Domain Rotation Status ===\n")

    budget_status = manager.get_budget_status()

    provider = (provider_override or config.get("provider") or DEFAULT_PROVIDER).lower()
    print(f"Provider: {provider}")
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")

    if manager.active_domain:
        print(f"\nCurrent burner email domain: {manager.active_domain}")
        print(f"   Configure your email system to use: user@{manager.active_domain}")


def list_providers():
    """Show supported domain registrar providers."""
    config = load_config()
    active = (config.get("provider") or DEFAULT_PROVIDER).lower()
    print("\n=== Supported Providers ===\n")
    for provider in SUPPORTED_REGISTRARS:
        marker = " (active)" if provider == active else ""
        print(f"- {provider}{marker}")
    print("\nUse: python domain_rotation_cli.py config --provider <name>")


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
  python domain_rotation_cli.py providers  # Show supported registrars
        """
    )

    parser.add_argument(
        'command',
        choices=['config', 'status', 'search', 'rotate', 'list', 'providers'],
        help='Command to execute'
    )
    parser.add_argument(
        '--provider',
        choices=list(SUPPORTED_REGISTRARS),
        help='Override configured registrar provider for this command'
    )

    args = parser.parse_args()

    if args.command == 'config':
        configure_api(args.provider)
    elif args.command == 'status':
        show_status(args.provider)
    elif args.command == 'search':
        search_domains(args.provider)
    elif args.command == 'rotate':
        rotate_domain(args.provider)
    elif args.command == 'list':
        list_domains(args.provider)
    elif args.command == 'providers':
        list_providers()


if __name__ == '__main__':
    main()
