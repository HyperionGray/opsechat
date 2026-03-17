#!/usr/bin/env python3
"""
Domain Rotation CLI for Burner Emails

This CLI tool allows easy rotation of domains for burner email services.
It integrates with Porkbun and Namecheap APIs.

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
from domain_manager import NamecheapAPIClient, PorkbunAPIClient, DomainRotationManager


CONFIG_FILE = Path.home() / '.opsechat' / 'domain_config.json'


def load_config():
    """Load configuration from file"""
    if not CONFIG_FILE.exists():
        return {"providers": {}, "monthly_budget": 50.0}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return migrate_legacy_config(config)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {"providers": {}, "monthly_budget": 50.0}


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


def migrate_legacy_config(config):
    """Migrate legacy single-provider config to multi-provider layout."""
    if not isinstance(config, dict):
        return {"providers": {}, "monthly_budget": 50.0}

    providers = config.get("providers")
    if not isinstance(providers, dict):
        providers = {}

    legacy_key = config.get("api_key")
    legacy_secret = config.get("api_secret")
    if legacy_key and legacy_secret and "porkbun" not in providers:
        providers["porkbun"] = {
            "api_key": legacy_key,
            "api_secret": legacy_secret,
        }

    config["providers"] = providers
    config.setdefault("monthly_budget", 50.0)
    if "default_provider" not in config and providers:
        config["default_provider"] = "porkbun" if "porkbun" in providers else next(iter(providers))
    return config


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported providers: porkbun, namecheap")
    print("Porkbun API credentials: https://porkbun.com/account/api")
    print("Namecheap API docs: https://www.namecheap.com/support/api/\n")
    
    config = load_config()
    providers = config.setdefault("providers", {})
    
    print("Current configuration:")
    print(f"  Providers configured: {', '.join(sorted(providers.keys())) or 'none'}")
    print(f"  Default provider: {config.get('default_provider', 'not set')}")
    
    if "porkbun" in providers and providers["porkbun"].get("api_key"):
        print("  Porkbun API Key: configured")
    else:
        print("  Porkbun API Key: not configured")

    if "namecheap" in providers and providers["namecheap"].get("api_key"):
        print("  Namecheap API Key: configured")
    else:
        print("  Namecheap API Key: not configured")

    print(f"  Monthly Budget: ${config.get('monthly_budget', 50.0)}")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    configure_porkbun = input("Configure Porkbun credentials? (yes/no) [yes]: ").strip().lower()
    if configure_porkbun in ("", "y", "yes"):
        porkbun = providers.setdefault("porkbun", {})
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            porkbun["api_key"] = api_key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            porkbun["api_secret"] = api_secret

    configure_namecheap = input("Configure Namecheap credentials? (yes/no) [no]: ").strip().lower()
    if configure_namecheap in ("y", "yes"):
        namecheap = providers.setdefault("namecheap", {})
        api_user = input("Namecheap ApiUser: ").strip()
        if api_user:
            namecheap["api_user"] = api_user

        api_key = input("Namecheap API Key: ").strip()
        if api_key:
            namecheap["api_key"] = api_key

        username = input("Namecheap UserName [defaults to ApiUser]: ").strip()
        if username:
            namecheap["username"] = username

        client_ip = input("Namecheap ClientIp [default: 127.0.0.1]: ").strip()
        if client_ip:
            namecheap["client_ip"] = client_ip

        use_sandbox = input("Use Namecheap sandbox? (yes/no) [no]: ").strip().lower()
        if use_sandbox in ("y", "yes"):
            namecheap["use_sandbox"] = True
        elif "use_sandbox" not in namecheap:
            namecheap["use_sandbox"] = False
    
    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config["monthly_budget"] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif "monthly_budget" not in config:
        config["monthly_budget"] = 50.0

    if providers:
        current_default = config.get("default_provider", "")
        default_provider = input(
            f"Default provider [{current_default or 'porkbun'}]: "
        ).strip().lower()
        if default_provider:
            if default_provider in providers:
                config["default_provider"] = default_provider
            else:
                print(f"Unknown provider '{default_provider}', keeping previous default.")
        elif "default_provider" not in config:
            config["default_provider"] = "porkbun" if "porkbun" in providers else next(iter(providers))

    config["providers"] = providers
    save_config(config)
    print("\nConfiguration updated successfully.")


def _build_manager_from_config(config):
    manager = DomainRotationManager(monthly_budget=config.get("monthly_budget", 50.0))
    providers = config.get("providers", {})
    default_provider = config.get("default_provider")

    for provider_name, provider_config in providers.items():
        try:
            if provider_name == "porkbun":
                key = provider_config.get("api_key")
                secret = provider_config.get("api_secret")
                if key and secret:
                    manager.add_api_client(
                        "porkbun",
                        PorkbunAPIClient(key, secret),
                        make_default=(default_provider == "porkbun"),
                    )
            elif provider_name == "namecheap":
                api_user = provider_config.get("api_user")
                api_key = provider_config.get("api_key")
                if api_user and api_key:
                    manager.add_api_client(
                        "namecheap",
                        NamecheapAPIClient(
                            api_user=api_user,
                            api_key=api_key,
                            username=provider_config.get("username"),
                            client_ip=provider_config.get("client_ip", "127.0.0.1"),
                            use_sandbox=bool(provider_config.get("use_sandbox", False)),
                        ),
                        make_default=(default_provider == "namecheap"),
                    )
        except Exception as e:
            print(f"Skipping provider '{provider_name}' due to configuration error: {e}")

    if default_provider and default_provider in manager.api_clients:
        manager.default_provider = default_provider

    manager.deserialize_state(config)
    return manager


def get_manager():
    """Get configured domain manager."""
    config = load_config()
    providers = config.get("providers", {})

    if not providers:
        print("Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = _build_manager_from_config(config)
    if not manager.list_providers():
        print("Error: No valid provider configuration found.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config.update(manager.serialize_state())
    save_config(config)


def _format_date(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value
    return "unknown"


def _normalize_provider_arg(provider):
    if provider == "default":
        return None
    return provider


def list_domains(provider=None):
    """List owned domains"""
    provider = _normalize_provider_arg(provider)
    manager, _ = get_manager()
    
    print("\n=== Owned Domains ===\n")
    
    domains = manager.get_owned_domains()
    if provider:
        domains = [d for d in domains if d.get("provider") == provider]
    
    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return
    
    for i, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain['domain'] == manager.active_domain else ""
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Provider: {domain.get('provider', 'unknown')}")
        print(f"   Purchased: {_format_date(domain.get('purchased_at'))}")
        print(f"   Expires: {_format_date(domain.get('expires_at'))[:10]}")
        print()


def search_domains(provider=None):
    """Search for available cheap domains"""
    provider = _normalize_provider_arg(provider)
    manager, _ = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
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
                f"(provider: {domain_info.get('provider')})"
            )
        else:
            print("  No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(provider=None):
    """Rotate to a new domain"""
    provider = _normalize_provider_arg(provider)
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
    
    domain_info = manager.find_cheap_available_domain(
        max_price=min(5.0, budget_status['remaining']),
        provider=provider,
    )
    
    if not domain_info:
        print("Could not find an available cheap domain within budget.")
        return
    
    print(
        f"\nFound: {domain_info['domain']} for ${domain_info['price']} "
        f"(provider: {domain_info.get('provider')})"
    )
    
    confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Purchase cancelled.")
        return
    
    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price'],
        provider=domain_info.get('provider'),
    )
    
    if success:
        print(f"\nSuccessfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\nFailed to purchase domain. Check API credentials and budget.")


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
    print(f"\nProviders: {', '.join(budget_status.get('providers', []))}")
    print(f"Default Provider: {budget_status.get('default_provider')}")
    
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
        choices=['porkbun', 'namecheap', 'default'],
        help='Limit command to one provider',
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
        list_domains(provider=args.provider)


if __name__ == '__main__':
    main()
