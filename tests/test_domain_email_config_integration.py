"""
Integration-style tests for domain/email configuration routes.
"""
from unittest.mock import Mock

import pytest

from app_factory import create_app
from domain_manager import DomainAPIClient, DomainRotationManager


class FakeProvider(DomainAPIClient):
    """Minimal deterministic provider for DomainRotationManager tests."""

    def __init__(self, api_key: str = "k", api_secret: str = "s"):
        super().__init__(api_key=api_key, api_secret=api_secret)
        self.available = True
        self.price = 2.0
        self.purchase_success = True

    def search_domain(self, domain: str):
        return {
            "domain": domain,
            "available": self.available,
            "price": self.price,
            "currency": "USD",
        }

    def purchase_domain(self, domain: str, years: int = 1):
        return {"success": self.purchase_success, "domain": domain}

    def get_pricing(self, tld: str):
        return {"tld": tld, "registration": "2.00"}


def _get_email_config_view(app):
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "email_config":
            return app.view_functions["email_config"]
    raise AssertionError("email_config endpoint was not registered")


@pytest.fixture
def app():
    application = create_app()
    application.config["TESTING"] = True
    application.config["path"] = "test-path-12345"
    application.config["hostname"] = "localhost"
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        with app.app_context():
            yield c


class TestDomainRotationManagerFeature:
    def test_rotate_with_provider_fallback(self):
        manager = DomainRotationManager(monthly_budget=20.0)
        failing = FakeProvider()
        failing.available = False
        ok = FakeProvider()
        ok.price = 1.25

        manager.add_api_client("first", failing, make_primary=True)
        manager.add_api_client("second", ok, make_primary=False)

        result = manager.rotate_to_new_domain(max_price=5.0)
        assert result["success"] is True
        assert result["provider"] == "second"
        assert result["domain"].endswith((".xyz", ".club", ".online", ".site", ".website"))
        assert manager.get_active_domain() == result["domain"]

    def test_state_export_import_keeps_datetime_fields_usable(self):
        manager = DomainRotationManager(monthly_budget=20.0)
        provider = FakeProvider()
        manager.set_api_client(provider)

        assert manager.purchase_domain_if_budget_allows("example.xyz", 2.0) is True
        exported = manager.export_state()

        loaded = DomainRotationManager(monthly_budget=1.0)
        loaded.import_state(exported)

        domains = loaded.get_owned_domains()
        assert len(domains) == 1
        assert hasattr(domains[0]["purchased_at"], "strftime")
        assert hasattr(domains[0]["expires_at"], "strftime")


class TestEmailConfigRoute:
    def test_email_config_get_has_expected_context(self, app):
        view = _get_email_config_view(app)

        with app.test_request_context("/test-path-12345/email/config"):
            app.config["path"] = "test-path-12345"
            app.config["hostname"] = "localhost"

            with pytest.MonkeyPatch.context() as mp:
                render_mock = Mock(return_value="ok")
                mp.setattr("email_routes.render_template", render_mock)

                response = view("test-path-12345")
                assert response == "ok"

                _, kwargs = render_mock.call_args
                assert "config_status" in kwargs
                assert "budget_status" in kwargs
                assert "active_domain" in kwargs

    def test_domain_rotate_endpoint_redirects_and_sets_message(self, client):
        response = client.post("/test-path-12345/email/domain/rotate")
        assert response.status_code in (302, 303)
