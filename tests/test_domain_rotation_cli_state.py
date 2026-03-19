"""
State handling tests for domain_rotation_cli.
"""

from datetime import datetime

import domain_rotation_cli


def test_get_manager_deserializes_owned_domain_datetimes(monkeypatch, tmp_path):
    """Owned domain timestamps should be converted back to datetime objects."""
    config_path = tmp_path / "domain_config.json"
    config_path.write_text(
        """
{
  "api_key": "k",
  "api_secret": "s",
  "current_spending": 1.25,
  "active_domain": "active.xyz",
  "owned_domains": [
    {
      "domain": "active.xyz",
      "price": 1.25,
      "purchased_at": "2026-03-01T10:00:00",
      "expires_at": "2027-03-01T10:00:00"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    class FakeClient:
        def __init__(self, api_key, api_secret):
            self.api_key = api_key
            self.api_secret = api_secret

    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)
    monkeypatch.setattr(domain_rotation_cli, "PorkbunAPIClient", FakeClient)

    manager, config = domain_rotation_cli.get_manager()
    domain_record = manager.owned_domains[0]

    assert config["active_domain"] == "active.xyz"
    assert isinstance(domain_record["purchased_at"], datetime)
    assert isinstance(domain_record["expires_at"], datetime)


def test_save_manager_state_serializes_datetimes(monkeypatch, tmp_path):
    """Saving manager state should serialize datetime objects as ISO strings."""
    config_path = tmp_path / "domain_config.json"
    monkeypatch.setattr(domain_rotation_cli, "CONFIG_FILE", config_path)

    manager = domain_rotation_cli.DomainRotationManager()
    manager.current_spending = 3.5
    manager.active_domain = "saved.xyz"
    manager.owned_domains = [
        {
            "domain": "saved.xyz",
            "price": 3.5,
            "purchased_at": datetime(2026, 3, 10, 12, 30, 0),
            "expires_at": datetime(2027, 3, 10, 12, 30, 0),
        }
    ]

    config = {"api_key": "k", "api_secret": "s"}
    domain_rotation_cli.save_manager_state(manager, config)
    saved = domain_rotation_cli.load_config()

    assert saved["current_spending"] == 3.5
    assert saved["active_domain"] == "saved.xyz"
    assert isinstance(saved["owned_domains"][0]["purchased_at"], str)
    assert isinstance(saved["owned_domains"][0]["expires_at"], str)
