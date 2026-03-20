#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It supports multiple registrar providers (currently Porkbun and Namecheap).

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
from domain_manager import PorkbunAPIClient, NamecheapAPIClient, DomainRotationManager


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


def migrate_legacy_config(config):
    """Normalize older flat config keys into provider-aware structure."""
    providers = config.get("providers", {})

    # Legacy Porkbun keys
    if config.get("api_key") and config.get("api_secret"):
        providers.setdefault("porkbun", {})
        providers["porkbun"].setdefault("api_key", config.get("api_key"))
        providers["porkbun"].setdefault("api_secret", config.get("api_secret"))

    # Legacy state keys
    if any(key in config for key in ("current_spending", "owned_domains", "active_domain")):
        state = config.get("state", {})
        if "current_spending" in config:
            state.setdefault("current_spending", config.get("current_spending"))
        if "owned_domains" in config:
            state.setdefault("owned_domains", config.get("owned_domains"))
        if "active_domain" in config:
            state.setdefault("active_domain", config.get("active_domain"))
        config["state"] = state

    config["providers"] = providers
    config.setdefault("preferred_provider", "porkbun")
    config.setdefault("monthly_budget", 50.0)
    return config


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
    print("Supported providers: porkbun, namecheap")
    print("Porkbun docs: https://porkbun.com/account/api")
    print("Namecheap docs: https://www.namecheap.com/support/api/intro/\n")

    config = migrate_legacy_config(load_config())
    providers = config.get("providers", {})
    preferred_provider = config.get("preferred_provider", "porkbun")

    print("Current configuration:")
    print(f"  Preferred provider: {preferred_provider}")
    print(f"  Configured providers: {', '.join(sorted(providers.keys())) or 'none'}")
    print(f"  Monthly Budget: ${config.get('monthly_budget', 50.0)}")

    provider = input("Provider to configure [porkbun/namecheap]: ").strip().lower() or preferred_provider
    if provider not in {"porkbun", "namecheap"}:
        print("Invalid provider. Use 'porkbun' or 'namecheap'.")
        return

    providers.setdefault(provider, {})
    provider_config = providers[provider]

    print("\nEnter new values (or press Enter to keep current):\n")
    if provider == "porkbun":
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            provider_config["api_key"] = api_key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            provider_config["api_secret"] = api_secret
    else:
        api_key = input("Namecheap API Key: ").strip()
        if api_key:
            provider_config["api_key"] = api_key

        username = input("Namecheap Username: ").strip()
        if username:
            provider_config["username"] = username

        client_ip = input("Namecheap Client IP (allowed in API settings): ").strip()
        if client_ip:
            provider_config["client_ip"] = client_ip

        api_user = input("Namecheap API User [optional, defaults to username]: ").strip()
        if api_user:
            provider_config["api_user"] = api_user

    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config["monthly_budget"] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif "monthly_budget" not in config:
        config["monthly_budget"] = 50.0

    config["preferred_provider"] = provider
    config["providers"] = providers
    save_config(config)
    print("\nConfiguration updated successfully.")


def get_manager():
    """Get configured domain manager"""
    config = migrate_legacy_config(load_config())
    providers = config.get("providers", {})

    if not providers:
        print("Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(monthly_budget=config.get("monthly_budget", 50.0))

    for provider_name, provider_cfg in providers.items():
        if provider_name == "porkbun":
            if not provider_cfg.get("api_key") or not provider_cfg.get("api_secret"):
                continue
            manager.add_api_client(
                "porkbun",
                PorkbunAPIClient(provider_cfg["api_key"], provider_cfg["api_secret"]),
            )
        elif provider_name == "namecheap":
            required = ("api_key", "username", "client_ip")
            if not all(provider_cfg.get(key) for key in required):
                continue
            manager.add_api_client(
                "namecheap",
                NamecheapAPIClient(
                    api_key=provider_cfg["api_key"],
                    username=provider_cfg["username"],
                    client_ip=provider_cfg["client_ip"],
                    api_user=provider_cfg.get("api_user"),
                ),
            )

    if not manager.api_clients:
        print("Error: No complete provider configuration found.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    preferred = config.get("preferred_provider")
    if preferred:
        manager.set_provider_priority([preferred] + [p for p in manager.api_clients.keys() if p != preferred])

    # Load saved state
    state = config.get("state", {})
    manager.import_state(state)

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config["state"] = manager.export_state()
    save_config(config)


def _format_datetime(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value
    return "unknown"


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
        print(f"   Provider: {domain.get('provider', 'unknown')}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'))}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'))}")
        print()


def search_domains(provider=None):
    """Search for available cheap domains"""
    manager, config = get_manager()
    providers = None if provider in (None, "all") else [provider]
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(
            max_price=5.0,
            max_attempts=1,
            providers=providers,
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
    providers = None if provider in (None, "all") else [provider]
    
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
    
    domain_info = manager.find_cheap_available_domain(
        max_price=min(5.0, budget_status['remaining']),
        providers=providers,
    )
    
    if not domain_info:
        print("Could not find an available cheap domain within budget.")
        return
    
    print(
        f"\nFound: {domain_info['domain']} for ${domain_info['price']} "
        f"via {domain_info.get('provider', 'unknown')}"
    )
    
    confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Purchase cancelled.")
        return
    
    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price'],
        provider=domain_info.get("provider"),
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
    print(f"Active Provider: {budget_status.get('active_provider') or 'None'}")
    print(f"Available Providers: {', '.join(budget_status.get('providers', [])) or 'None'}")
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
    parser.add_argument(
        '--provider',
        choices=['porkbun', 'namecheap', 'all'],
        default='all',
        help='Provider to use for search/rotate operations'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
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
