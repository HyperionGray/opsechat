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


def _serialize_owned_domains(domains):
    """Convert datetime values to ISO strings for JSON persistence."""
    serialized = []
    for domain in domains:
        item = dict(domain)
        purchased_at = item.get("purchased_at")
        expires_at = item.get("expires_at")
        if isinstance(purchased_at, datetime):
            item["purchased_at"] = purchased_at.isoformat()
        if isinstance(expires_at, datetime):
            item["expires_at"] = expires_at.isoformat()
        serialized.append(item)
    return serialized


def _deserialize_owned_domains(domains):
    """Convert ISO datetime strings back into datetime objects."""
    parsed = []
    for domain in domains:
        item = dict(domain)
        purchased_at = item.get("purchased_at")
        expires_at = item.get("expires_at")
        if isinstance(purchased_at, str):
            try:
                item["purchased_at"] = datetime.fromisoformat(purchased_at)
            except ValueError:
                pass
        if isinstance(expires_at, str):
            try:
                item["expires_at"] = datetime.fromisoformat(expires_at)
            except ValueError:
                pass
        parsed.append(item)
    return parsed


def _prompt_namecheap_contact_profile():
    """Collect minimum Namecheap contact profile required for domain purchase."""
    print("\nNamecheap requires registrant contact profile data for purchases.")
    print("Press Enter to skip any field (purchase will be blocked until profile is complete).\n")
    fields = [
        "FirstName",
        "LastName",
        "Address1",
        "City",
        "StateProvince",
        "PostalCode",
        "Country",
        "Phone",
        "EmailAddress",
    ]
    profile = {}
    for field in fields:
        value = input(f"{field}: ").strip()
        if value:
            profile[field] = value
    return profile


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("This tool supports Porkbun and Namecheap APIs.")
    print("Porkbun API keys: https://porkbun.com/account/api")
    print("Namecheap API docs: https://www.namecheap.com/support/api/intro/\n")
    
    config = load_config()
    providers = config.setdefault("providers", {})
    porkbun_cfg = providers.get("porkbun", {})
    namecheap_cfg = providers.get("namecheap", {})
    
    print("Current configuration:")
    if porkbun_cfg.get("api_key"):
        print(f"  Porkbun API Key: {'*' * 20}{porkbun_cfg['api_key'][-4:]}")
    else:
        print("  Porkbun API Key: Not configured")

    if namecheap_cfg.get("api_key"):
        print(f"  Namecheap API Key: {'*' * 20}{namecheap_cfg['api_key'][-4:]}")
    else:
        print("  Namecheap API Key: Not configured")

    if config.get("monthly_budget"):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")

    print("\nProvider choices: porkbun, namecheap")
    provider = input("Provider to configure [porkbun]: ").strip().lower() or "porkbun"
    if provider not in ("porkbun", "namecheap"):
        print("Invalid provider. Choose 'porkbun' or 'namecheap'.")
        return

    print("\nEnter new values (or press Enter to keep current):\n")

    provider_cfg = providers.setdefault(provider, {})

    if provider == "porkbun":
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            provider_cfg["api_key"] = api_key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            provider_cfg["api_secret"] = api_secret
    else:
        api_user = input("Namecheap API User: ").strip()
        if api_user:
            provider_cfg["api_user"] = api_user
        username = input("Namecheap Username (blank = API user): ").strip()
        if username:
            provider_cfg["username"] = username
        api_key = input("Namecheap API Key: ").strip()
        if api_key:
            provider_cfg["api_key"] = api_key
        client_ip = input("Namecheap Client IP (required by Namecheap): ").strip()
        if client_ip:
            provider_cfg["client_ip"] = client_ip
        sandbox = input("Use Namecheap sandbox? (yes/no) [no]: ").strip().lower()
        if sandbox in ("yes", "no"):
            provider_cfg["sandbox"] = sandbox == "yes"
        contact_profile = _prompt_namecheap_contact_profile()
        if contact_profile:
            provider_cfg["contact_profile"] = contact_profile

    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config["monthly_budget"] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif "monthly_budget" not in config:
        config["monthly_budget"] = 50.0

    providers[provider] = provider_cfg
    config["providers"] = providers

    save_config(config)
    print("\n✅ Configuration updated successfully!")


def get_manager(preferred_provider=None):
    """Get configured domain manager"""
    config = load_config()

    providers = config.get("providers")
    # Backward compatibility with old single-provider flat config
    if not providers and config.get("api_key") and config.get("api_secret"):
        providers = {
            "porkbun": {
                "api_key": config["api_key"],
                "api_secret": config["api_secret"],
            }
        }

    if not providers:
        print("❌ Error: API credentials not configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(monthly_budget=config.get("monthly_budget", 50.0))
    configured_providers = []

    porkbun_cfg = providers.get("porkbun", {})
    if porkbun_cfg.get("api_key") and porkbun_cfg.get("api_secret"):
        manager.add_api_client(
            "porkbun",
            PorkbunAPIClient(porkbun_cfg["api_key"], porkbun_cfg["api_secret"]),
        )
        configured_providers.append("porkbun")

    namecheap_cfg = providers.get("namecheap", {})
    if namecheap_cfg.get("api_user") and namecheap_cfg.get("api_key"):
        manager.add_api_client(
            "namecheap",
            NamecheapAPIClient(
                api_user=namecheap_cfg["api_user"],
                api_key=namecheap_cfg["api_key"],
                username=namecheap_cfg.get("username"),
                client_ip=namecheap_cfg.get("client_ip"),
                sandbox=bool(namecheap_cfg.get("sandbox", False)),
                contact_profile=namecheap_cfg.get("contact_profile"),
            ),
        )
        configured_providers.append("namecheap")

    if not configured_providers:
        print("❌ Error: no valid provider credentials configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    if preferred_provider and preferred_provider != "any":
        if preferred_provider not in configured_providers:
            print(f"❌ Error: provider '{preferred_provider}' is not configured.")
            print(f"Configured providers: {', '.join(configured_providers)}")
            sys.exit(1)
        manager.active_provider = preferred_provider
    elif configured_providers:
        manager.active_provider = configured_providers[0]

    # Load saved state
    if config.get("current_spending"):
        manager.current_spending = config["current_spending"]
    if config.get("owned_domains"):
        manager.owned_domains = _deserialize_owned_domains(config["owned_domains"])
    if config.get("active_domain"):
        manager.active_domain = config["active_domain"]
    if config.get("active_provider"):
        manager.active_provider = config["active_provider"]

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config["current_spending"] = manager.current_spending
    config["owned_domains"] = _serialize_owned_domains(manager.owned_domains)
    config["active_domain"] = manager.active_domain
    config["active_provider"] = manager.active_provider
    save_config(config)


def list_domains(provider):
    """List owned domains"""
    manager, config = get_manager(provider)
    
    print("\n=== Owned Domains ===\n")
    
    domains = manager.get_owned_domains()
    
    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return
    
    for i, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain.get("domain") == manager.active_domain else ""
        print(f"{i}. {domain.get('domain', 'unknown')}{active}")
        print(f"   Provider: {domain.get('provider', 'unknown')}")
        print(f"   Price: ${domain.get('price', 'n/a')}")

        purchased_at = domain.get("purchased_at")
        if isinstance(purchased_at, datetime):
            purchased_text = purchased_at.strftime("%Y-%m-%d %H:%M")
        else:
            purchased_text = str(purchased_at or "n/a")
        expires_at = domain.get("expires_at")
        if isinstance(expires_at, datetime):
            expires_text = expires_at.strftime("%Y-%m-%d")
        else:
            expires_text = str(expires_at or "n/a")

        print(f"   Purchased: {purchased_text}")
        print(f"   Expires: {expires_text}")
        print()


def search_domains(provider, max_price):
    """Search for available cheap domains"""
    manager, config = get_manager(provider)
    
    print("\n=== Searching for Available Cheap Domains ===\n")
    print(f"Searching for domains under ${max_price}...\n")
    
    for i in range(5):
        print(f"Attempt {i+1}/5...")
        target_provider = None if provider == "any" else provider
        domain_info = manager.find_cheap_available_domain(
            max_price=max_price,
            max_attempts=1,
            provider=target_provider,
        )
        
        if domain_info:
            print(
                f"  ✅ Found: {domain_info['domain']} - ${domain_info['price']} "
                f"({domain_info.get('provider', 'unknown')})"
            )
        else:
            print(f"  ❌ No cheap domain found in this attempt")
    
    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(provider, max_price):
    """Rotate to a new domain"""
    manager, config = get_manager(provider)
    
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
    
    target_provider = None if provider == "any" else provider
    domain_info = manager.find_cheap_available_domain(
        max_price=min(max_price, budget_status["remaining"]),
        provider=target_provider,
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
        domain_info['domain'],
        domain_info['price'],
        provider=domain_info.get("provider"),
    )
    
    if success:
        print(f"\n✅ Successfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\n❌ Failed to purchase domain. Check API credentials and budget.")


def show_status(provider):
    """Show current status"""
    manager, config = get_manager(provider)
    
    print("\n=== Domain Rotation Status ===\n")
    
    budget_status = manager.get_budget_status()
    
    print(f"Active Domain: {manager.active_domain or 'None'}")
    print(f"Active Provider: {manager.active_provider or 'None'}")
    print(f"Configured Providers: {', '.join(manager.get_available_providers())}")
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
        choices=['any', 'porkbun', 'namecheap'],
        default='any',
        help="Select registrar provider (default: any configured provider)"
    )

    parser.add_argument(
        '--max-price',
        type=float,
        default=5.0,
        help='Maximum domain price in USD when searching/rotating (default: 5.0)'
    )
    
    args = parser.parse_args()
    
    if args.command == 'config':
        configure_api()
    elif args.command == 'status':
        show_status(args.provider)
    elif args.command == 'search':
        search_domains(args.provider, args.max_price)
    elif args.command == 'rotate':
        rotate_domain(args.provider, args.max_price)
    elif args.command == 'list':
        list_domains(args.provider)


if __name__ == '__main__':
    main()
