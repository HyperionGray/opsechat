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


def normalize_config(config):
    """Normalize legacy and modern config shapes."""
    normalized = dict(config or {})

    providers = normalized.get("providers")
    if not isinstance(providers, dict):
        providers = {}

    # Migrate legacy flat keys into provider map.
    if normalized.get("api_key") and normalized.get("api_secret"):
        providers.setdefault("porkbun", {
            "api_key": normalized.get("api_key"),
            "api_secret": normalized.get("api_secret"),
        })

    normalized["providers"] = providers

    if "monthly_budget" not in normalized:
        normalized["monthly_budget"] = 50.0

    if not normalized.get("active_provider"):
        normalized["active_provider"] = "porkbun" if "porkbun" in providers else None

    if "state" not in normalized:
        normalized["state"] = {
            "current_spending": normalized.get("current_spending", 0.0),
            "owned_domains": normalized.get("owned_domains", []),
            "active_domain": normalized.get("active_domain"),
            "active_provider": normalized.get("active_provider"),
        }

    return normalized


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
    config = normalize_config(config)
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
    print("This tool supports Porkbun API for domain management.")
    print("You can get API credentials from: https://porkbun.com/account/api\n")
    
    config = load_config()
    
    providers = config.get("providers", {})
    active_provider = config.get("active_provider") or ("porkbun" if "porkbun" in providers else "porkbun")
    provider_config = providers.get(active_provider, {})

    print("Current configuration:")
    print(f"  Active Provider: {active_provider}")
    if provider_config.get('api_key'):
        print(f"  API Key: {'*' * 20}{provider_config['api_key'][-4:]}")
    else:
        print("  API Key: Not configured")
    print(f"  Monthly Budget: ${config.get('monthly_budget', 50.0)}")
    
    print("\nEnter new values (or press Enter to keep current):\n")
    
    provider = input(f"Provider [default: {active_provider}]: ").strip().lower() or active_provider
    if provider != "porkbun":
        print("Only 'porkbun' is currently supported in CLI configuration.")
        return

    api_key = input("Porkbun API Key: ").strip() or provider_config.get("api_key", "")
    api_secret = getpass("Porkbun API Secret: ").strip() or provider_config.get("api_secret", "")

    if not api_key or not api_secret:
        print("Both API key and secret are required.")
        return
    
    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config['monthly_budget'] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif 'monthly_budget' not in config:
        config['monthly_budget'] = 50.0

    config["providers"][provider] = {
        "api_key": api_key,
        "api_secret": api_secret,
    }
    config["active_provider"] = provider

    save_config(config)
    print("\n✅ Configuration updated successfully!")


def get_manager(provider_override=None):
    """Get configured domain manager"""
    config = load_config()

    providers = config.get("providers", {})
    if not providers:
        print("❌ Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    requested_provider = provider_override or config.get("active_provider")
    if requested_provider and requested_provider not in providers:
        print(f"❌ Error: Provider '{requested_provider}' is not configured.")
        sys.exit(1)

    manager = DomainRotationManager(monthly_budget=float(config.get('monthly_budget', 50.0)))
    for provider_name, provider_config in providers.items():
        if provider_name != "porkbun":
            continue
        api_key = provider_config.get("api_key", "")
        api_secret = provider_config.get("api_secret", "")
        if not api_key or not api_secret:
            continue
        manager.configure(
            api_key=api_key,
            secret_key=api_secret,
            monthly_budget=float(config.get("monthly_budget", 50.0)),
            provider=provider_name,
        )

    if requested_provider:
        manager.set_active_provider(requested_provider)

    manager.load_state(config.get("state", {}))
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config = normalize_config(config)
    config["state"] = manager.export_state()
    config["monthly_budget"] = manager.monthly_budget
    if manager.get_active_provider():
        config["active_provider"] = manager.get_active_provider()
    save_config(config)


def _format_datetime(value, fmt):
    if isinstance(value, datetime):
        return value.strftime(fmt)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime(fmt)
        except ValueError:
            return value
    return "Unknown"


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
        active = " [ACTIVE]" if domain['domain'] == manager.active_domain else ""
        provider = domain.get("provider", "unknown")
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Provider: {provider}")
        print(f"   Price: ${domain['price']}")
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
        domain_info = manager.find_cheap_available_domain(
            max_price=5.0,
            max_attempts=1,
            provider=provider_override,
        )
        
        if domain_info:
            print(
                f"  ✅ Found: {domain_info['domain']} - ${domain_info['price']} "
                f"(provider: {domain_info.get('provider', 'unknown')})"
            )
        else:
            print(f"  ❌ No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(provider_override=None):
    """Rotate to a new domain"""
    manager, config = get_manager(provider_override)
    
    print("\n=== Domain Rotation ===\n")
    
    budget_status = manager.get_budget_status()
    active_provider = manager.get_active_provider() or "none"
    print(f"Provider: {active_provider}")
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")
    
    if budget_status['remaining'] < 1:
        print("❌ Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(
        max_price=min(5.0, budget_status['remaining']),
        provider=provider_override,
    )
    
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
        domain_info['price'],
        provider=domain_info.get('provider') or provider_override,
    )
    
    if success:
        print(f"\n✅ Successfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\n❌ Failed to purchase domain. Check API credentials and budget.")


def show_status(provider_override=None):
    """Show current status"""
    manager, _ = get_manager(provider_override)
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"Active Provider: {manager.get_active_provider() or 'None'}")
    print(f"Configured Providers: {', '.join(manager.get_provider_names()) or 'None'}")
    print(f"\nBudget:")
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
        default=None,
        help='Optional provider override (example: porkbun)'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status(args.provider)
    elif args.command == 'search':
        search_domains(args.provider)
    elif args.command == 'rotate':
        rotate_domain(args.provider)
    elif args.command == 'list':
        list_domains(args.provider)


if __name__ == '__main__':
    main()
