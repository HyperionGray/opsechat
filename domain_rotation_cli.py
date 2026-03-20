#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It supports Porkbun, Namecheap, and auto-selection across configured registrars.

Usage:
    python domain_rotation_cli.py config                    # Configure API credentials
    python domain_rotation_cli.py status                    # Show budget status
    python domain_rotation_cli.py search                    # Search for available cheap domains
    python domain_rotation_cli.py rotate                    # Rotate to a new domain
    python domain_rotation_cli.py list                      # List owned domains
    python domain_rotation_cli.py --provider namecheap list # Override provider for one command
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple
from pathlib import Path
from getpass import getpass

from domain_manager import (
    DomainRotationManager,
    MultiRegistrarClient,
    NamecheapAPIClient,
    PorkbunAPIClient,
)


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def _mask_secret(value: str) -> str:
    """Mask a sensitive value while leaving trailing chars for identification."""
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * 20}{value[-4:]}"


def normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize config and preserve backward compatibility."""
    normalized = dict(config or {})

    # Backward compatibility with old key names.
    if normalized.get("api_key") and not normalized.get("porkbun_api_key"):
        normalized["porkbun_api_key"] = normalized["api_key"]
    if normalized.get("api_secret") and not normalized.get("porkbun_api_secret"):
        normalized["porkbun_api_secret"] = normalized["api_secret"]

    if not normalized.get("namecheap_username") and normalized.get("namecheap_api_user"):
        normalized["namecheap_username"] = normalized["namecheap_api_user"]

    if "monthly_budget" not in normalized:
        normalized["monthly_budget"] = 50.0

    if "namecheap_use_sandbox" not in normalized:
        normalized["namecheap_use_sandbox"] = False

    provider = normalized.get("provider")
    if provider not in ("auto", "porkbun", "namecheap"):
        has_porkbun = bool(
            normalized.get("porkbun_api_key") and normalized.get("porkbun_api_secret")
        )
        has_namecheap = bool(
            normalized.get("namecheap_api_user")
            and normalized.get("namecheap_api_key")
            and normalized.get("namecheap_client_ip")
        )
        if has_porkbun and has_namecheap:
            provider = "auto"
        elif has_namecheap:
            provider = "namecheap"
        elif has_porkbun:
            provider = "porkbun"
        else:
            provider = "auto"
    normalized["provider"] = provider
    return normalized


def serialize_domain_records(domains: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Serialize manager domain records to JSON-compatible values."""
    serialized = []
    for domain in domains:
        record = dict(domain)
        for field in ("purchased_at", "expires_at"):
            value = record.get(field)
            if isinstance(value, datetime):
                record[field] = value.isoformat()
        serialized.append(record)
    return serialized


def deserialize_domain_records(domains: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deserialize persisted domain records into runtime objects."""
    deserialized = []
    for domain in domains:
        record = dict(domain)
        for field in ("purchased_at", "expires_at"):
            value = record.get(field)
            if isinstance(value, str):
                try:
                    record[field] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep legacy or malformed values as-is for resilience.
                    pass
        deserialized.append(record)
    return deserialized


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return normalize_config({})
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return normalize_config(json.load(f))
    except Exception as e:
        print(f"Error loading config: {e}")
        return normalize_config({})


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
    print("Supported providers: porkbun, namecheap, auto")
    print("Porkbun API docs: https://porkbun.com/account/api")
    print("Namecheap API docs: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    
    print("Current configuration:")
    print(f"  Provider: {config.get('provider', 'auto')}")
    if config.get("porkbun_api_key"):
        print(f"  Porkbun API Key: {_mask_secret(config['porkbun_api_key'])}")
    else:
        print("  Porkbun API Key: Not configured")

    if config.get("namecheap_api_user"):
        print(f"  Namecheap API User: {config['namecheap_api_user']}")
    else:
        print("  Namecheap API User: Not configured")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    provider = input(
        f"Provider [auto|porkbun|namecheap] [{config.get('provider', 'auto')}]: "
    ).strip().lower()
    if provider:
        if provider not in ("auto", "porkbun", "namecheap"):
            print("Invalid provider, keeping previous value")
        else:
            config["provider"] = provider
    else:
        config["provider"] = config.get("provider", "auto")
    
    if config["provider"] in ("auto", "porkbun"):
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            config['porkbun_api_key'] = api_key
    
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['porkbun_api_secret'] = api_secret

    if config["provider"] in ("auto", "namecheap"):
        api_user = input(
            f"Namecheap API User [{config.get('namecheap_api_user', '')}]: "
        ).strip()
        if api_user:
            config["namecheap_api_user"] = api_user

        username = input(
            f"Namecheap Username [{config.get('namecheap_username', config.get('namecheap_api_user', ''))}]: "
        ).strip()
        if username:
            config["namecheap_username"] = username

        api_key = getpass("Namecheap API Key: ").strip()
        if api_key:
            config["namecheap_api_key"] = api_key

        client_ip = input(
            f"Namecheap Client IP [{config.get('namecheap_client_ip', '')}]: "
        ).strip()
        if client_ip:
            config["namecheap_client_ip"] = client_ip

        sandbox = input(
            f"Use Namecheap sandbox? [y/N] [{'y' if config.get('namecheap_use_sandbox') else 'n'}]: "
        ).strip().lower()
        if sandbox in ("y", "yes"):
            config["namecheap_use_sandbox"] = True
        elif sandbox in ("n", "no"):
            config["namecheap_use_sandbox"] = False

        print("\nOptional Namecheap contact profile (required to purchase via Namecheap):")
        contact_fields = [
            ("first_name", "First name"),
            ("last_name", "Last name"),
            ("address1", "Address line 1"),
            ("city", "City"),
            ("state_province", "State/Province"),
            ("postal_code", "Postal code"),
            ("country", "Country (2-letter code)"),
            ("phone", "Phone (+1.5555555555 format)"),
            ("email_address", "Email address"),
            ("organization_name", "Organization (optional)"),
        ]
        for key, label in contact_fields:
            config_key = f"namecheap_contact_{key}"
            value = input(f"{label} [{config.get(config_key, '')}]: ").strip()
            if value:
                config[config_key] = value
    
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


def _build_clients(config: Dict[str, Any], provider_override: str = None) -> Tuple[List[Any], str]:
    """Build one or more registrar clients from config."""
    selected_provider = provider_override or config.get("provider", "auto")
    clients = []

    if selected_provider in ("auto", "porkbun"):
        if config.get("porkbun_api_key") and config.get("porkbun_api_secret"):
            clients.append(
                PorkbunAPIClient(config["porkbun_api_key"], config["porkbun_api_secret"])
            )
        elif selected_provider == "porkbun":
            print("Error: Porkbun credentials missing.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)

    if selected_provider in ("auto", "namecheap"):
        has_namecheap_config = bool(
            config.get("namecheap_api_user")
            and config.get("namecheap_api_key")
            and config.get("namecheap_client_ip")
        )
        if has_namecheap_config:
            contact_profile = {
                "first_name": config.get("namecheap_contact_first_name", ""),
                "last_name": config.get("namecheap_contact_last_name", ""),
                "address1": config.get("namecheap_contact_address1", ""),
                "city": config.get("namecheap_contact_city", ""),
                "state_province": config.get("namecheap_contact_state_province", ""),
                "postal_code": config.get("namecheap_contact_postal_code", ""),
                "country": config.get("namecheap_contact_country", ""),
                "phone": config.get("namecheap_contact_phone", ""),
                "email_address": config.get("namecheap_contact_email_address", ""),
                "organization_name": config.get("namecheap_contact_organization_name", ""),
            }
            clients.append(
                NamecheapAPIClient(
                    api_user=config["namecheap_api_user"],
                    api_key=config["namecheap_api_key"],
                    client_ip=config["namecheap_client_ip"],
                    username=config.get("namecheap_username") or config["namecheap_api_user"],
                    use_sandbox=bool(config.get("namecheap_use_sandbox", False)),
                    default_contact=contact_profile,
                )
            )
        elif selected_provider == "namecheap":
            print("Error: Namecheap credentials missing.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)

    if not clients:
        print("Error: No registrar credentials configured for selected provider.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    return clients, selected_provider


def get_manager(provider_override: str = None):
    """Get configured domain manager and effective provider details."""
    config = load_config()
    clients, selected_provider = _build_clients(config, provider_override=provider_override)

    client = clients[0] if len(clients) == 1 else MultiRegistrarClient(clients)
    manager = DomainRotationManager(
        api_client=client,
        monthly_budget=config.get('monthly_budget', 50.0)
    )
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        manager.owned_domains = deserialize_domain_records(config['owned_domains'])
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config, selected_provider, [c.name for c in clients]


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    config['owned_domains'] = serialize_domain_records(manager.owned_domains)
    config['active_domain'] = manager.active_domain
    save_config(config)


def _format_datetime(value: Any, fmt: str) -> str:
    """Format datetime-like values safely."""
    if isinstance(value, datetime):
        return value.strftime(fmt)
    return str(value)


def list_domains(provider_override: str = None):
    """List owned domains"""
    manager, _config, selected_provider, active_clients = get_manager(provider_override=provider_override)
    
    print("\n=== Owned Domains ===\n")
    print(f"Selected Provider: {selected_provider} ({', '.join(active_clients)})\n")
    
    domains = manager.get_owned_domains()
    
    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return
    
    for i, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain['domain'] == manager.active_domain else ""
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        if domain.get("registrar"):
            print(f"   Registrar: {domain['registrar']}")
        if domain.get("purchased_at") is not None:
            print(f"   Purchased: {_format_datetime(domain['purchased_at'], '%Y-%m-%d %H:%M')}")
        if domain.get("expires_at") is not None:
            print(f"   Expires: {_format_datetime(domain['expires_at'], '%Y-%m-%d')}")
        print()


def search_domains(provider_override: str = None):
    """Search for available cheap domains"""
    manager, _config, selected_provider, active_clients = get_manager(provider_override=provider_override)
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Selected Provider: {selected_provider} ({', '.join(active_clients)})")
    print("Searching for domains under $5...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
        
        if domain_info:
            registrar = domain_info.get("registrar", "unknown")
            print(f"  Found: {domain_info['domain']} - ${domain_info['price']} ({registrar})")
        else:
            print("  No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(provider_override: str = None):
    """Rotate to a new domain"""
    manager, config, selected_provider, active_clients = get_manager(provider_override=provider_override)
    
    print("\n=== Domain Rotation ===\n")
    print(f"Selected Provider: {selected_provider} ({', '.join(active_clients)})\n")
    
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
    if domain_info.get("registrar"):
        print(f"Registrar: {domain_info['registrar']}")
    
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


def show_status(provider_override: str = None):
    """Show current status"""
    manager, _config, selected_provider, active_clients = get_manager(provider_override=provider_override)
    
    print("\n=== Domain Rotation Status ===\n")
    print(f"Selected Provider: {selected_provider}")
    print(f"Active Registrars: {', '.join(active_clients)}\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
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
        description='OpSecChat Domain Rotation CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python domain_rotation_cli.py config     # Configure API credentials
  python domain_rotation_cli.py status     # Show current status
  python domain_rotation_cli.py --provider auto search
  python domain_rotation_cli.py --provider namecheap list
  python domain_rotation_cli.py search     # Search for available domains
  python domain_rotation_cli.py rotate     # Rotate to a new domain
  python domain_rotation_cli.py list       # List owned domains
        """
    )

    parser.add_argument(
        '--provider',
        choices=['auto', 'porkbun', 'namecheap'],
        help='Override configured provider for this command'
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
        show_status(provider_override=args.provider)
    elif args.command == 'search':
        search_domains(provider_override=args.provider)
    elif args.command == 'rotate':
        rotate_domain(provider_override=args.provider)
    elif args.command == 'list':
        list_domains(provider_override=args.provider)


if __name__ == '__main__':
    main()
