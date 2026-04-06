#!/usr/bin/env python3
"""
Domain Rotation CLI for burner emails.

Usage:
    python domain_rotation_cli.py list
    python domain_rotation_cli.py search [--provider auto|porkbun|namecheap]
    python domain_rotation_cli.py rotate [--provider auto|porkbun|namecheap]
    python domain_rotation_cli.py status
    python domain_rotation_cli.py config
"""

import argparse
import json
import os
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Dict, List

from domain_manager import DomainRotationManager, NamecheapAPIClient, PorkbunAPIClient


CONFIG_FILE = Path.home() / ".opsechat" / "domain_config.json"
SUPPORTED_PROVIDERS = ("auto", "porkbun", "namecheap")


def _mask_secret(value: str) -> str:
    """Mask API secrets for terminal display."""
    if not value:
        return "Not configured"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * 12}{value[-4:]}"


def _parse_datetime(value):
    """Parse datetime values loaded from config JSON."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _deserialize_owned_domains(records: List[Dict]) -> List[Dict]:
    """Convert persisted domain records into runtime structures."""
    parsed_records = []
    for record in records or []:
        parsed = dict(record)
        for field_name in ("purchased_at", "expires_at"):
            parsed_dt = _parse_datetime(parsed.get(field_name))
            if parsed_dt:
                parsed[field_name] = parsed_dt
        parsed_records.append(parsed)
    return parsed_records


def _serialize_owned_domains(records: List[Dict]) -> List[Dict]:
    """Convert runtime domain records into JSON-safe objects."""
    serialized_records = []
    for record in records or []:
        serialized = dict(record)
        for field_name in ("purchased_at", "expires_at"):
            if isinstance(serialized.get(field_name), datetime):
                serialized[field_name] = serialized[field_name].isoformat()
        serialized_records.append(serialized)
    return serialized_records


def load_config():
    """Load configuration from file."""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

    # Backward compatibility with older flat Porkbun config fields.
    if ("api_key" in config or "api_secret" in config) and "porkbun" not in config:
        config["porkbun"] = {
            "api_key": config.get("api_key", ""),
            "api_secret": config.get("api_secret", ""),
        }

    if "provider" not in config:
        config["provider"] = "porkbun" if config.get("porkbun") else "auto"

    return config


def save_config(config):
    """Save configuration to file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as config_file:
            json.dump(config, config_file, indent=2)
        os.chmod(CONFIG_FILE, 0o600)
        print(f"Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")


def configure_api():
    """Configure API credentials for one or more providers."""
    print("\n=== Domain API Configuration ===\n")
    print("Supported registrars:")
    print("  - Porkbun:   https://porkbun.com/account/api")
    print("  - Namecheap: https://www.namecheap.com/support/api/intro/\n")

    config = load_config()
    porkbun = dict(config.get("porkbun", {}))
    namecheap = dict(config.get("namecheap", {}))
    current_provider = config.get("provider", "auto")

    print("Current configuration:")
    print(f"  Preferred Provider: {current_provider}")
    print(f"  Porkbun API Key: {_mask_secret(porkbun.get('api_key', ''))}")
    print(f"  Namecheap API Key: {_mask_secret(namecheap.get('api_key', ''))}")
    print(f"  Monthly Budget: ${config.get('monthly_budget', 50.0)}")

    print("\nEnter new values or press Enter to keep current values.\n")

    provider_value = input(
        f"Preferred Provider [auto|porkbun|namecheap] ({current_provider}): "
    ).strip().lower()
    if provider_value:
        if provider_value not in SUPPORTED_PROVIDERS:
            print("Invalid provider. Keeping current provider.")
        else:
            config["provider"] = provider_value

    budget = input(
        f"Monthly Budget (USD) [{config.get('monthly_budget', 50.0)}]: "
    ).strip()
    if budget:
        try:
            config["monthly_budget"] = float(budget)
        except ValueError:
            print("Invalid budget amount, keeping previous value")
    elif "monthly_budget" not in config:
        config["monthly_budget"] = 50.0

    print("\nPorkbun configuration")
    porkbun_api_key = input("  API Key: ").strip()
    if porkbun_api_key:
        porkbun["api_key"] = porkbun_api_key
    porkbun_api_secret = getpass("  API Secret: ").strip()
    if porkbun_api_secret:
        porkbun["api_secret"] = porkbun_api_secret
    if porkbun:
        config["porkbun"] = porkbun

    configure_namecheap = input("\nConfigure Namecheap now? (y/N): ").strip().lower()
    if configure_namecheap in ("y", "yes"):
        print("\nNamecheap configuration")
        api_user = input(
            f"  ApiUser [{namecheap.get('api_user', '')}]: "
        ).strip()
        if api_user:
            namecheap["api_user"] = api_user
        username = input(
            f"  UserName [{namecheap.get('username', '')}]: "
        ).strip()
        if username:
            namecheap["username"] = username
        client_ip = input(
            f"  Client IP [{namecheap.get('client_ip', '')}]: "
        ).strip()
        if client_ip:
            namecheap["client_ip"] = client_ip
        api_key = getpass("  API Key: ").strip()
        if api_key:
            namecheap["api_key"] = api_key
        sandbox = input(
            f"  Use sandbox (y/N) [{ 'y' if namecheap.get('use_sandbox') else 'n' }]: "
        ).strip().lower()
        if sandbox in ("y", "yes"):
            namecheap["use_sandbox"] = True
        elif sandbox in ("n", "no"):
            namecheap["use_sandbox"] = False
        config["namecheap"] = namecheap

    # Keep legacy fields in sync for users upgrading from older CLI versions.
    if config.get("porkbun"):
        config["api_key"] = config["porkbun"].get("api_key", "")
        config["api_secret"] = config["porkbun"].get("api_secret", "")

    save_config(config)
    print("\nConfiguration updated successfully.")


def _validate_provider(provider: str, manager: DomainRotationManager) -> str:
    """Validate provider argument against configured clients."""
    if provider == "auto":
        return provider
    if provider not in manager.get_provider_names():
        print(f"Error: provider '{provider}' is not configured.")
        print(f"Configured providers: {', '.join(manager.get_provider_names())}")
        sys.exit(1)
    return provider


def get_manager():
    """Get configured domain manager with one or more providers."""
    config = load_config()

    manager = DomainRotationManager(monthly_budget=config.get("monthly_budget", 50.0))

    porkbun = config.get("porkbun", {})
    if porkbun.get("api_key") and porkbun.get("api_secret"):
        manager.add_api_client(
            "porkbun",
            PorkbunAPIClient(porkbun["api_key"], porkbun["api_secret"]),
        )

    namecheap = config.get("namecheap", {})
    if (
        namecheap.get("api_user")
        and namecheap.get("api_key")
        and namecheap.get("username")
        and namecheap.get("client_ip")
    ):
        manager.add_api_client(
            "namecheap",
            NamecheapAPIClient(
                api_user=namecheap["api_user"],
                api_key=namecheap["api_key"],
                username=namecheap["username"],
                client_ip=namecheap["client_ip"],
                use_sandbox=bool(namecheap.get("use_sandbox", False)),
            ),
        )

    if not manager.get_provider_names():
        print("Error: No API credentials configured.")
        print("Run: python domain_rotation_cli.py config")
        sys.exit(1)

    preferred_provider = config.get("provider", "auto")
    if preferred_provider in ("porkbun", "namecheap") and not manager.set_primary_provider(
        preferred_provider
    ):
        print(
            f"Warning: preferred provider '{preferred_provider}' is not configured. "
            "Using first configured provider."
        )

    manager.current_spending = float(config.get("current_spending", 0.0))
    manager.owned_domains = _deserialize_owned_domains(config.get("owned_domains", []))
    manager.active_domain = config.get("active_domain")

    return manager, config


def save_manager_state(manager, config):
    """Save manager state to config."""
    config["current_spending"] = manager.current_spending
    config["owned_domains"] = _serialize_owned_domains(manager.owned_domains)
    config["active_domain"] = manager.active_domain
    save_config(config)


def list_domains():
    """List owned domains."""
    manager, _config = get_manager()

    print("\n=== Owned Domains ===\n")

    domains = manager.get_owned_domains()
    if not domains:
        print("No domains owned yet.")
        print("Run: python domain_rotation_cli.py rotate")
        return

    for index, domain in enumerate(domains, 1):
        active = " [ACTIVE]" if domain.get("domain") == manager.active_domain else ""
        provider = domain.get("provider", "unknown")
        purchased = domain.get("purchased_at")
        expires = domain.get("expires_at")
        purchased_text = (
            purchased.strftime("%Y-%m-%d %H:%M")
            if isinstance(purchased, datetime)
            else str(purchased or "unknown")
        )
        expires_text = (
            expires.strftime("%Y-%m-%d")
            if isinstance(expires, datetime)
            else str(expires or "unknown")
        )

        print(f"{index}. {domain.get('domain', 'unknown')}{active}")
        print(f"   Provider: {provider}")
        print(f"   Price: ${domain.get('price', 'unknown')}")
        print(f"   Purchased: {purchased_text}")
        print(f"   Expires: {expires_text}")
        print()


def search_domains(provider: str):
    """Search for available cheap domains."""
    manager, _config = get_manager()
    provider = _validate_provider(provider, manager)

    print("\n=== Searching for Available Cheap Domains ===\n")
    print("Searching for domains under $5...\n")
    if provider != "auto":
        print(f"Using provider: {provider}\n")

    for attempt in range(5):
        print(f"Attempt {attempt + 1}/5...")
        domain_info = manager.find_cheap_available_domain(
            max_price=5.0,
            max_attempts=1,
            provider_name=provider,
        )

        if domain_info:
            found_provider = domain_info.get("provider", "unknown")
            print(
                f"  Found: {domain_info['domain']} - ${domain_info['price']} "
                f"(provider: {found_provider})"
            )
        else:
            print("  No cheap domain found in this attempt")

    print("\nTo purchase a domain, run: python domain_rotation_cli.py rotate")


def rotate_domain(provider: str):
    """Rotate to a new domain."""
    manager, config = get_manager()
    provider = _validate_provider(provider, manager)

    print("\n=== Domain Rotation ===\n")

    budget_status = manager.get_budget_status()
    print(f"Monthly Budget: ${budget_status['monthly_budget']}")
    print(f"Current Spending: ${budget_status['current_spending']}")
    print(f"Remaining: ${budget_status['remaining']}")
    print(f"Domains Owned: {budget_status['domains_owned']}\n")

    if budget_status["remaining"] < 1:
        print("Insufficient budget remaining this month.")
        return

    print("Searching for available cheap domain...")
    domain_info = manager.find_cheap_available_domain(
        max_price=min(5.0, budget_status["remaining"]),
        provider_name=provider,
    )

    if not domain_info:
        print("Could not find an available cheap domain within budget.")
        return

    print(
        f"\nFound: {domain_info['domain']} for ${domain_info['price']} "
        f"(provider: {domain_info.get('provider', 'unknown')})"
    )

    confirm = input("\nProceed with purchase? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Purchase cancelled.")
        return

    print("\nPurchasing domain...")
    success = manager.purchase_domain_if_budget_allows(
        domain_info["domain"],
        domain_info["price"],
        provider_name=domain_info.get("provider"),
    )

    if success:
        print(f"\nSuccessfully purchased and activated: {domain_info['domain']}")
        save_manager_state(manager, config)
    else:
        print("\nFailed to purchase domain. Check API credentials and budget.")


def show_status():
    """Show current domain rotation status."""
    manager, config = get_manager()

    print("\n=== Domain Rotation Status ===\n")
    print(f"Preferred Provider: {config.get('provider', 'auto')}")
    print(f"Configured Providers: {', '.join(manager.get_provider_names())}")

    budget_status = manager.get_budget_status()
    print(f"\nActive Domain: {manager.active_domain or 'None'}")
    print("\nBudget:")
    print(f"  Monthly: ${budget_status['monthly_budget']}")
    print(f"  Spent: ${budget_status['current_spending']}")
    print(f"  Remaining: ${budget_status['remaining']}")
    print(f"\nDomains Owned: {budget_status['domains_owned']}")

    if manager.active_domain:
        print(f"\nCurrent burner email domain: {manager.active_domain}")
        print(f"Configure your email system to use: user@{manager.active_domain}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="OpSecChat Domain Rotation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python domain_rotation_cli.py config
  python domain_rotation_cli.py status
  python domain_rotation_cli.py search --provider auto
  python domain_rotation_cli.py rotate --provider namecheap
  python domain_rotation_cli.py list
        """,
    )

    parser.add_argument(
        "command",
        choices=["config", "status", "search", "rotate", "list"],
        help="Command to execute",
    )
    parser.add_argument(
        "--provider",
        choices=SUPPORTED_PROVIDERS,
        default="auto",
        help="Provider to use for search/rotate commands (default: auto)",
    )

    args = parser.parse_args()

    if args.command == "config":
        configure_api()
    elif args.command == "status":
        show_status()
    elif args.command == "search":
        search_domains(args.provider)
    elif args.command == "rotate":
        rotate_domain(args.provider)
    elif args.command == "list":
        list_domains()


if __name__ == "__main__":
    main()
