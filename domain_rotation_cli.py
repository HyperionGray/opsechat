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
from domain_manager import DomainRotationManager, NamecheapAPIClient, PorkbunAPIClient


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


def _parse_optional_datetime(value):
    """Parse ISO datetime from config, returning original value on failure."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _format_datetime(value):
    """Format datetime-like values for display."""
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, str):
        return value
    return "unknown"


def configure_api():
    """Configure API credentials"""
    print("\n=== Domain API Configuration ===\n")
    print("This tool supports Porkbun and Namecheap for domain management.")
    print("Porkbun API credentials: https://porkbun.com/account/api")
    print("Namecheap API credentials: https://www.namecheap.com/support/api/\n")
    
    config = load_config()
    providers = config.get('providers', {})
    if not providers and config.get('api_key') and config.get('api_secret'):
        # Backward compatibility with legacy config format
        providers = {
            "porkbun": {
                "api_key": config.get("api_key", ""),
                "api_secret": config.get("api_secret", "")
            }
        }
    
    print("Current configuration:")
    if providers.get("porkbun", {}).get("api_key"):
        print(f"  Porkbun: configured (key ending ...{providers['porkbun']['api_key'][-4:]})")
    else:
        print("  Porkbun: not configured")

    if providers.get("namecheap", {}).get("api_key"):
        nc_user = providers["namecheap"].get("api_user", "unknown")
        print(f"  Namecheap: configured (api_user={nc_user})")
    else:
        print("  Namecheap: not configured")

    print(f"  Primary provider: {config.get('primary_provider', 'porkbun')}")
    print(f"  Fallback providers: {config.get('fallback_providers', [])}")
    
    if config.get('monthly_budget'):
        print(f"  Monthly Budget: ${config['monthly_budget']}")
    else:
        print("  Monthly Budget: Not configured")
    
    print("\nEnter new values (or press Enter to keep current):\n")

    new_providers = dict(providers)

    configure_porkbun = input("Configure Porkbun credentials? (yes/no) [yes]: ").strip().lower()
    if configure_porkbun in ("", "yes", "y"):
        porkbun_cfg = dict(new_providers.get("porkbun", {}))
        api_key = input("Porkbun API Key: ").strip()
        if api_key:
            porkbun_cfg['api_key'] = api_key

        api_secret = getpass("Porkbun API Secret: ").strip()
        if api_secret:
            porkbun_cfg['api_secret'] = api_secret

        if porkbun_cfg.get("api_key") and porkbun_cfg.get("api_secret"):
            new_providers["porkbun"] = porkbun_cfg

    configure_namecheap = input("Configure Namecheap credentials? (yes/no) [no]: ").strip().lower()
    if configure_namecheap in ("yes", "y"):
        nc_cfg = dict(new_providers.get("namecheap", {}))
        nc_key = input("Namecheap API Key: ").strip()
        if nc_key:
            nc_cfg["api_key"] = nc_key
        nc_user = input("Namecheap API User: ").strip()
        if nc_user:
            nc_cfg["api_user"] = nc_user
        username = input("Namecheap Username [optional, defaults to API user]: ").strip()
        if username:
            nc_cfg["username"] = username
        client_ip = input(f"Namecheap Client IP [{nc_cfg.get('client_ip', '127.0.0.1')}]: ").strip()
        if client_ip:
            nc_cfg["client_ip"] = client_ip
        elif "client_ip" not in nc_cfg:
            nc_cfg["client_ip"] = "127.0.0.1"
        sandbox = input(f"Use Namecheap sandbox? (yes/no) [{'yes' if nc_cfg.get('sandbox') else 'no'}]: ").strip().lower()
        if sandbox in ("yes", "y"):
            nc_cfg["sandbox"] = True
        elif sandbox in ("no", "n"):
            nc_cfg["sandbox"] = False

        if nc_cfg.get("api_key") and nc_cfg.get("api_user"):
            new_providers["namecheap"] = nc_cfg

    if not new_providers:
        print("No provider credentials configured. Keeping previous settings.")
    else:
        config["providers"] = new_providers

    primary_default = config.get("primary_provider", "porkbun")
    primary = input(f"Primary provider [porkbun/namecheap] [{primary_default}]: ").strip().lower()
    if primary:
        config["primary_provider"] = primary
    elif "primary_provider" not in config:
        config["primary_provider"] = primary_default

    fallback_raw = input(
        f"Fallback providers (comma-separated) [{','.join(config.get('fallback_providers', []))}]: "
    ).strip()
    if fallback_raw:
        config["fallback_providers"] = [p.strip().lower() for p in fallback_raw.split(",") if p.strip()]
    elif "fallback_providers" not in config:
        config["fallback_providers"] = []
    
    budget = input("Monthly Budget (USD) [default: 50]: ").strip()
    if budget:
        try:
            config['monthly_budget'] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif 'monthly_budget' not in config:
        config['monthly_budget'] = 50.0

    # Clean up legacy keys now that provider config is stored under `providers`.
    config.pop("api_key", None)
    config.pop("api_secret", None)
    
    save_config(config)
    print("\n✅ Configuration updated successfully!")


def get_manager():
    """Get configured domain manager"""
    config = load_config()

    providers = config.get("providers", {})
    if not providers and config.get('api_key') and config.get('api_secret'):
        # Legacy config migration path.
        providers = {
            "porkbun": {
                "api_key": config.get("api_key"),
                "api_secret": config.get("api_secret")
            }
        }

    if not providers:
        print("❌ Error: No API providers configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    manager = DomainRotationManager(monthly_budget=config.get('monthly_budget', 50.0))

    for provider_name, provider_cfg in providers.items():
        provider_key = provider_name.lower()
        if provider_key == "porkbun":
            key = provider_cfg.get("api_key")
            secret = provider_cfg.get("api_secret")
            if key and secret:
                manager.register_api_client("porkbun", PorkbunAPIClient(key, secret))
        elif provider_key == "namecheap":
            key = provider_cfg.get("api_key")
            api_user = provider_cfg.get("api_user")
            if key and api_user:
                manager.register_api_client(
                    "namecheap",
                    NamecheapAPIClient(
                        api_key=key,
                        api_user=api_user,
                        username=provider_cfg.get("username") or api_user,
                        client_ip=provider_cfg.get("client_ip", "127.0.0.1"),
                        sandbox=bool(provider_cfg.get("sandbox", False)),
                        contact_profile=provider_cfg.get("contact_profile")
                    )
                )

    if not manager.api_clients:
        print("❌ Error: Provider config exists but is incomplete.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    primary_provider = config.get("primary_provider")
    if primary_provider:
        try:
            manager.set_primary_provider(primary_provider)
        except ValueError:
            # Fall back to first configured provider if stale config is present.
            pass
    manager.set_fallback_providers(config.get("fallback_providers", []))
    
    # Load saved state
    if config.get('current_spending'):
        manager.current_spending = config['current_spending']
    if config.get('owned_domains'):
        restored = []
        for domain in config['owned_domains']:
            item = dict(domain)
            item["purchased_at"] = _parse_optional_datetime(item.get("purchased_at"))
            item["expires_at"] = _parse_optional_datetime(item.get("expires_at"))
            restored.append(item)
        manager.owned_domains = restored
    if config.get('active_domain'):
        manager.active_domain = config['active_domain']
    
    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config"""
    config['current_spending'] = manager.current_spending
    serialized_domains = []
    for domain in manager.owned_domains:
        item = dict(domain)
        if isinstance(item.get("purchased_at"), datetime):
            item["purchased_at"] = item["purchased_at"].isoformat()
        if isinstance(item.get("expires_at"), datetime):
            item["expires_at"] = item["expires_at"].isoformat()
        serialized_domains.append(item)
    config['owned_domains'] = serialized_domains
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
        print(f"{i}. {domain['domain']}{active} ({provider})")
        print(f"   Price: ${domain['price']}")
        print(f"   Purchased: {_format_datetime(domain.get('purchased_at'))}")
        expires_at = domain.get("expires_at")
        if isinstance(expires_at, datetime):
            expires_display = expires_at.strftime('%Y-%m-%d')
        else:
            expires_display = str(expires_at or "unknown")
        print(f"   Expires: {expires_display}")
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
            print(f"  ✅ Found: {domain_info['domain']} - ${domain_info['price']} ({provider})")
        else:
            print(f"  ❌ No cheap domain found in this attempt")
    
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
    print(f"Primary Provider: {manager.primary_provider}")
    print(f"Fallback Providers: {manager.fallback_providers}\n")
    
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
        provider=provider
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
    print(f"Primary Provider: {manager.primary_provider or 'None'}")
    print(f"Fallback Providers: {manager.fallback_providers}")
    print(f"Configured Providers: {', '.join(sorted(manager.api_clients.keys()))}")
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
        description='OpSecChat Domain Rotation CLI',
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
