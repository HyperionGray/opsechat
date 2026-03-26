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
from typing import Any, Dict, List
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


def _format_datetime(value):
    """Format datetime or datetime-like string for display."""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).strftime('%Y-%m-%d %H:%M')
        except ValueError:
            return value
    return "unknown"


def _deserialize_owned_domains(raw_domains):
    """Deserialize domain state loaded from JSON config."""
    parsed: List[Dict[str, Any]] = []
    for item in raw_domains or []:
        if not isinstance(item, dict):
            continue
        domain_data = dict(item)
        for key in ("purchased_at", "expires_at"):
            value = domain_data.get(key)
            if isinstance(value, str):
                try:
                    domain_data[key] = datetime.fromisoformat(value)
                except ValueError:
                    pass
        parsed.append(domain_data)
    return parsed


def _serialize_owned_domains(owned_domains):
    """Serialize domain state for JSON config."""
    serialized = []
    for domain in owned_domains:
        if not isinstance(domain, dict):
            continue
        domain_data = dict(domain)
        for key in ("purchased_at", "expires_at"):
            value = domain_data.get(key)
            if isinstance(value, datetime):
                domain_data[key] = value.isoformat()
        serialized.append(domain_data)
    return serialized


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("This tool supports multiple registrars for domain management.")
    print("Primary registrar options: porkbun, namecheap")
    print("You can optionally configure one fallback registrar.\n")
    
    config = load_config()
    
    print("Current configuration:")
    provider = config.get("provider", "porkbun")
    print(f"  Primary Provider: {provider}")
    if config.get('api_key'):
        print(f"  Primary API Key: {'*' * 20}{config['api_key'][-4:]}")
    else:
        print("  Primary API Key: Not configured")

    fallback_provider = config.get("fallback_provider")
    if fallback_provider:
        print(f"  Fallback Provider: {fallback_provider}")
        if config.get("fallback_api_key"):
            print(f"  Fallback API Key: {'*' * 20}{config['fallback_api_key'][-4:]}")
        else:
            print("  Fallback API Key: Not configured")
    else:
        print("  Fallback Provider: None")

    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    provider_input = input(f"Primary Provider [porkbun/namecheap] (current: {provider}): ").strip().lower()
    provider = provider_input or provider
    if provider not in {"porkbun", "namecheap"}:
        print("Invalid provider, defaulting to porkbun")
        provider = "porkbun"
    config["provider"] = provider

    api_key = input(f"{provider.title()} API Key: ").strip()
    if api_key:
        config['api_key'] = api_key

    if provider == "porkbun":
        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            config['api_secret'] = api_secret
        # Clear Namecheap-only fields from primary profile.
        config.pop("username", None)
        config.pop("client_ip", None)
        config.pop("sandbox", None)
    else:
        username = input(f"Namecheap Username [{config.get('username', '')}]: ").strip()
        if username:
            config["username"] = username
        client_ip = input(f"Namecheap Client IP [{config.get('client_ip', '')}]: ").strip()
        if client_ip:
            config["client_ip"] = client_ip
        sandbox = input(
            f"Use Namecheap Sandbox? [y/N] (current: {'y' if config.get('sandbox') else 'n'}): "
        ).strip().lower()
        if sandbox in {"y", "yes"}:
            config["sandbox"] = True
        elif sandbox in {"n", "no"}:
            config["sandbox"] = False
        # Clear Porkbun-only secret field if switching providers.
        config.pop("api_secret", None)

    fallback_provider_current = config.get("fallback_provider", "none")
    fallback_provider_input = input(
        f"Fallback Provider [none/porkbun/namecheap] (current: {fallback_provider_current}): "
    ).strip().lower()
    fallback_provider = fallback_provider_input or fallback_provider_current
    if fallback_provider in {"", "none"}:
        config.pop("fallback_provider", None)
        config.pop("fallback_api_key", None)
        config.pop("fallback_api_secret", None)
        config.pop("fallback_username", None)
        config.pop("fallback_client_ip", None)
        config.pop("fallback_sandbox", None)
    elif fallback_provider in {"porkbun", "namecheap"}:
        config["fallback_provider"] = fallback_provider
        fallback_api_key = input(f"{fallback_provider.title()} Fallback API Key: ").strip()
        if fallback_api_key:
            config["fallback_api_key"] = fallback_api_key
        if fallback_provider == "porkbun":
            fallback_api_secret = getpass("Porkbun Fallback API Secret: ").strip()
            if fallback_api_secret:
                config["fallback_api_secret"] = fallback_api_secret
            config.pop("fallback_username", None)
            config.pop("fallback_client_ip", None)
            config.pop("fallback_sandbox", None)
        else:
            fallback_username = input(
                f"Namecheap Fallback Username [{config.get('fallback_username', '')}]: "
            ).strip()
            if fallback_username:
                config["fallback_username"] = fallback_username
            fallback_client_ip = input(
                f"Namecheap Fallback Client IP [{config.get('fallback_client_ip', '')}]: "
            ).strip()
            if fallback_client_ip:
                config["fallback_client_ip"] = fallback_client_ip
            fallback_sandbox = input(
                f"Use Namecheap Fallback Sandbox? [y/N] "
                f"(current: {'y' if config.get('fallback_sandbox') else 'n'}): "
            ).strip().lower()
            if fallback_sandbox in {"y", "yes"}:
                config["fallback_sandbox"] = True
            elif fallback_sandbox in {"n", "no"}:
                config["fallback_sandbox"] = False
            config.pop("fallback_api_secret", None)
    else:
        print("Invalid fallback provider, removing fallback configuration.")
        config.pop("fallback_provider", None)
    
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

    provider = config.get("provider", "porkbun")
    if not config.get("api_key"):
        print("Error: API key not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    configure_kwargs = {
        "provider": provider,
        "api_key": config.get("api_key"),
        "monthly_budget": config.get("monthly_budget", 50.0),
    }
    if provider == "porkbun":
        configure_kwargs["secret_key"] = config.get("api_secret")
        if not configure_kwargs["secret_key"]:
            print("Error: Porkbun secret key not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
    elif provider == "namecheap":
        configure_kwargs["username"] = config.get("username")
        configure_kwargs["client_ip"] = config.get("client_ip")
        configure_kwargs["sandbox"] = bool(config.get("sandbox", False))
        if not configure_kwargs["username"] or not configure_kwargs["client_ip"]:
            print("Error: Namecheap username/client_ip not configured.")
            print("Run: python domain_rotation_cli.py config")
            sys.exit(1)
    else:
        print(f"Error: Unsupported provider '{provider}'.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    fallback_provider = config.get("fallback_provider")
    if fallback_provider and config.get("fallback_api_key"):
        configure_kwargs["fallback_provider"] = fallback_provider
        configure_kwargs["fallback_api_key"] = config.get("fallback_api_key")
        if fallback_provider == "porkbun":
            configure_kwargs["fallback_secret_key"] = config.get("fallback_api_secret")
        elif fallback_provider == "namecheap":
            configure_kwargs["fallback_username"] = config.get("fallback_username")
            configure_kwargs["fallback_client_ip"] = config.get("fallback_client_ip")
            configure_kwargs["fallback_sandbox"] = bool(config.get("fallback_sandbox", False))

    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))
    config_result = manager.configure(**configure_kwargs)
    if not config_result.get("success"):
        print(f"Error configuring domain manager: {config_result.get('message')}")
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
        active = " [ACTIVE]" if domain['domain'] == manager.active_domain else ""
        provider = domain.get("provider", "unknown")
        print(f"{i}. {domain['domain']}{active}")
        print(f"   Provider: {provider}")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'))}")
        print(f"   Expires: {_format_datetime(domain.get('expires_at'))}")
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
            provider = domain_info.get("provider", "unknown")
            print(f"  Found: {domain_info['domain']} - ${domain_info['price']} ({provider})")
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
        print("❌ Insufficient budget remaining this month.")
        return
    
    print("Searching for available cheap domain...")
    
    domain_info = manager.find_cheap_available_domain(max_price=min(5.0, budget_status['remaining']))
    
    if not domain_info:
        print("❌ Could not find an available cheap domain within budget.")
        return
    
    provider = domain_info.get("provider", "unknown")
    print(f"\nFound: {domain_info['domain']} for ${domain_info['price']} via {provider}")
    
    confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Purchase cancelled.")
        return
    
    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info['domain'],
        domain_info['price'],
        api_client=domain_info.get('api_client')
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
