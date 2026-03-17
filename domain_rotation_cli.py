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


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("Supported providers: porkbun, namecheap")
    print("Porkbun API docs: https://porkbun.com/account/api")
    print("Namecheap API docs: https://www.namecheap.com/support/api/\n")
    
    config = load_config()
    providers = config.setdefault("providers", {})
    selected_provider = (config.get("provider", "porkbun") or "porkbun").lower()
    
    print("Current configuration:")
    print(f"  Active Provider: {selected_provider}")
    
    if config.get('monthly_budget') is not None:
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    for provider_name in ("porkbun", "namecheap"):
        provider_cfg = providers.get(provider_name, {})
        has_key = bool(provider_cfg.get("api_key"))
        masked = f"{'*' * 20}{provider_cfg['api_key'][-4:]}" if has_key else "Not configured"
        print(f"  {provider_name.title()} API Key: {masked}")

    print("\nEnter new values (or press Enter to keep current):\n")

    provider_input = input("Active Provider [porkbun/namecheap]: ").strip().lower()
    if provider_input in {"porkbun", "namecheap"}:
        selected_provider = provider_input
    config["provider"] = selected_provider

    provider_cfg = providers.setdefault(selected_provider, {})
    api_key = input(f"{selected_provider.title()} API Key: ").strip()
    if api_key:
        provider_cfg["api_key"] = api_key

    if selected_provider == "porkbun":
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            provider_cfg["api_secret"] = api_secret
    elif selected_provider == "namecheap":
        username = input("Namecheap Username: ").strip()
        if username:
            provider_cfg["username"] = username

        client_ip = input("Namecheap Client IP (whitelisted): ").strip()
        if client_ip:
            provider_cfg["client_ip"] = client_ip

        sandbox = input("Use Namecheap sandbox? [y/N]: ").strip().lower()
        if sandbox:
            provider_cfg["sandbox"] = sandbox in {"y", "yes", "true", "1"}

        print(
            "Optional: set contact profile fields for purchases "
            "(FirstName, LastName, Address1, City, StateProvince, PostalCode, Country, Phone, EmailAddress)."
        )
        if input("Configure purchase contact profile now? [y/N]: ").strip().lower() in {"y", "yes"}:
            contact_profile = provider_cfg.setdefault("contact_profile", {})
            for key in (
                "FirstName",
                "LastName",
                "Address1",
                "City",
                "StateProvince",
                "PostalCode",
                "Country",
                "Phone",
                "EmailAddress",
            ):
                value = input(f"  {key}: ").strip()
                if value:
                    contact_profile[key] = value

    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config['monthly_budget'] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif 'monthly_budget' not in config:
        config['monthly_budget'] = 50.0
    
    config["providers"] = providers
    save_config(config)
    print("\n✅ Configuration updated successfully!")


def get_manager():
    """Get configured domain manager"""
    config = load_config()

    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))
    providers = config.get("providers", {})
    active_provider = (config.get("provider", "porkbun") or "porkbun").lower()

    # Backward compatibility for older config shape.
    if not providers and config.get("api_key"):
        providers = {
            "porkbun": {
                "api_key": config.get("api_key"),
                "api_secret": config.get("api_secret"),
            }
        }
        config["providers"] = providers

    for provider_name, provider_cfg in providers.items():
        api_key = provider_cfg.get("api_key")
        if not api_key:
            continue

        if provider_name == "porkbun":
            api_secret = provider_cfg.get("api_secret")
            if not api_secret:
                continue
            manager.configure(
                provider="porkbun",
                api_key=api_key,
                secret_key=api_secret,
                monthly_budget=config.get("monthly_budget", 50.0),
            )
        elif provider_name == "namecheap":
            username = provider_cfg.get("username")
            client_ip = provider_cfg.get("client_ip")
            if not username or not client_ip:
                continue
            manager.configure(
                provider="namecheap",
                api_key=api_key,
                username=username,
                client_ip=client_ip,
                sandbox=provider_cfg.get("sandbox", False),
                contact_profile=provider_cfg.get("contact_profile"),
                monthly_budget=config.get("monthly_budget", 50.0),
            )

    if not manager.get_provider_names():
        print("❌ Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    if active_provider and not manager.set_active_provider(active_provider):
        # Keep first configured provider as active if the configured value is stale.
        pass

    if config.get("state"):
        manager.import_state(config["state"])
    else:
        # Backward compatibility for old in-root state fields.
        manager.import_state({
            "current_spending": config.get("current_spending", 0.0),
            "owned_domains": config.get("owned_domains", []),
            "active_domain": config.get("active_domain"),
            "monthly_budget": config.get("monthly_budget", 50.0),
            "active_provider": active_provider,
        })

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['state'] = manager.export_state()
    config['provider'] = manager.active_provider or config.get("provider", "porkbun")
    save_config(config)


def _format_datetime(value):
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime('%Y-%m-%d %H:%M')
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
        provider = domain.get("provider", "unknown")
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Price: ${domain['price']}")
        print(f"   Provider: {provider}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'))}")
        expires_value = _format_datetime(domain.get('expires_at'))
        print(f"   Expires: {expires_value.split(' ')[0] if ' ' in expires_value else expires_value}")
        print()


def search_domains(provider_preference=None):
    """Search for available cheap domains"""
    manager, config = get_manager()
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    if provider_preference:
        print(f"Provider preference: {provider_preference}")
    print("Searching for domains under $5...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        domain_info = manager.find_cheap_available_domain(
            max_price=5.0,
            max_attempts=1,
            provider_preference=provider_preference,
        )
        
        if domain_info:
            print(
                f"  ✅ Found: {domain_info['domain']} - ${domain_info['price']} "
                f"({domain_info.get('provider', 'unknown')})"
            )
        else:
            print(f"  ❌ No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(provider_preference=None):
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
    
    print("Searching for available cheap domain...")

    domain_info = manager.find_cheap_available_domain(
        max_price=min(5.0, budget_status['remaining']),
        provider_preference=provider_preference,
    )

    if not domain_info:
        print("❌ Could not find an available cheap domain within budget.")
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
        domain_info["domain"],
        domain_info["price"],
        provider=domain_info.get("provider"),
    )

    if success:
        print(
            f"\n✅ Successfully purchased and activated: {domain_info['domain']} "
            f"({domain_info.get('provider', 'unknown')})"
        )
        save_manager_state(manager, config)
    else:
        print("\n❌ Failed to purchase domain. Check API credentials, contact profile, and budget.")


def show_status():
    """Show current status"""
    manager, config = get_manager()
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"Active Provider: {manager.active_provider or 'None'}")
    print(f"Configured Providers: {', '.join(manager.get_provider_names())}")
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
        choices=['porkbun', 'namecheap'],
        help='Optional provider preference for search/rotate operations',
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status()
    elif args.command == 'search':
        search_domains(provider_preference=args.provider)
    elif args.command == 'rotate':
        rotate_domain(provider_preference=args.provider)
    elif args.command == 'list':
        list_domains()


if __name__ == '__main__':
    main()
