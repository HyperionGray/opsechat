"""Tests for domain management module."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from domain_manager import DomainAPIClient, DomainRotationManager, PorkbunAPIClient


class TestPorkbunAPIClient:
    """Test Porkbun API client."""

    @patch("domain_manager.requests.Session")
    def test_search_domain_available(self, mock_session_class):
        """Test domain availability search."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "SUCCESS",
            "isAvailable": True,
            "price": "2.99",
            "currency": "USD",
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = PorkbunAPIClient("test_key", "test_secret")
        result = client.search_domain("test123.xyz")

        assert result["available"] is True
        assert result["domain"] == "test123.xyz"
        assert result["price"] == "2.99"

    @patch("domain_manager.requests.Session")
    def test_search_domain_unavailable(self, mock_session_class):
        """Test domain unavailable."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {"status": "SUCCESS", "isAvailable": False}
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = PorkbunAPIClient("test_key", "test_secret")
        result = client.search_domain("google.com")

        assert result["available"] is False

    @patch("domain_manager.requests.Session")
    def test_get_pricing(self, mock_session_class):
        """Test pricing retrieval."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "SUCCESS",
            "pricing": {
                "registration": "9.99",
                "renewal": "9.99",
                "transfer": "9.99",
            },
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = PorkbunAPIClient("test_key", "test_secret")
        result = client.get_pricing("com")

        assert result["tld"] == "com"
        assert result["registration"] == "9.99"


class TestDomainRotationManager:
    """Test domain rotation manager."""

    def test_generate_random_domain(self):
        """Test random domain generation."""
        manager = DomainRotationManager()
        domain = manager.generate_random_domain("xyz", 8)

        assert domain.endswith(".xyz")
        assert len(domain.split(".")[0]) == 8

    def test_find_cheap_available_domain_no_client(self):
        """Test finding domain without API client."""
        manager = DomainRotationManager()
        assert manager.find_cheap_available_domain() is None

    def test_find_cheap_available_domain_success(self):
        """Test finding cheap domain successfully."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "test123.xyz",
            "price": 2.99,
        }

        manager = DomainRotationManager(mock_client)
        result = manager.find_cheap_available_domain(max_price=5.0, max_attempts=3)

        assert result is not None
        assert result["domain"].endswith((".xyz", ".club", ".online", ".site", ".website"))
        assert result["price"] <= 5.0

    def test_find_cheap_available_domain_unparseable_price_is_skipped(self):
        """Unparseable prices should be ignored rather than crashing."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "badprice.xyz",
            "price": "N/A",
        }
        manager = DomainRotationManager(mock_client)

        result = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
        assert result is None

    def test_purchase_domain_if_budget_allows_success(self):
        """Test domain purchase within budget."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.purchase_domain.return_value = {
            "success": True,
            "domain": "test123.xyz",
            "order_id": "12345",
        }

        manager = DomainRotationManager(mock_client, monthly_budget=50.0)
        result = manager.purchase_domain_if_budget_allows("test123.xyz", 2.99)

        assert result["success"] is True
        assert manager.current_spending == 2.99
        assert len(manager.owned_domains) == 1
        assert manager.active_domain == "test123.xyz"
        assert isinstance(manager.owned_domains[0]["purchased_at"], datetime)

    def test_purchase_domain_if_budget_allows_exceeds_budget(self):
        """Test domain purchase exceeds budget."""
        mock_client = Mock(spec=DomainAPIClient)
        manager = DomainRotationManager(mock_client, monthly_budget=5.0)
        manager.current_spending = 4.0

        result = manager.purchase_domain_if_budget_allows("test123.xyz", 2.0)

        assert result["success"] is False
        assert result["message"] == "Budget exceeded"
        assert manager.current_spending == 4.0
        assert len(manager.owned_domains) == 0

    def test_get_budget_status(self):
        """Test budget status retrieval."""
        manager = DomainRotationManager(monthly_budget=50.0)
        manager.current_spending = 10.0
        manager.owned_domains = [{"domain": "test.xyz"}]

        status = manager.get_budget_status()

        assert status["monthly_budget"] == 50.0
        assert status["current_spending"] == 10.0
        assert status["remaining"] == 40.0
        assert status["domains_owned"] == 1

    def test_rotate_domain(self):
        """Test domain rotation returns structured success."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "test456.xyz",
            "price": 2.99,
        }
        mock_client.purchase_domain.return_value = {
            "success": True,
            "domain": "test456.xyz",
        }

        manager = DomainRotationManager(mock_client, monthly_budget=50.0)
        result = manager.rotate_domain()

        assert result["success"] is True
        assert "domain" in result
        assert manager.active_domain == result["domain"]

    def test_export_and_load_state_round_trip(self):
        """State export should be JSON-safe and loadable."""
        manager = DomainRotationManager(monthly_budget=50.0)
        manager.current_spending = 5.5
        manager.active_domain = "active.xyz"
        manager.owned_domains = [
            {
                "domain": "active.xyz",
                "price": 1.23,
                "purchased_at": datetime(2026, 1, 1, 12, 0, 0),
                "expires_at": datetime(2027, 1, 1, 12, 0, 0),
            }
        ]

        exported = manager.export_state()
        assert isinstance(exported["owned_domains"][0]["purchased_at"], str)
        assert isinstance(exported["owned_domains"][0]["expires_at"], str)

        restored = DomainRotationManager(monthly_budget=50.0)
        restored.load_state(exported)
        assert restored.current_spending == 5.5
        assert restored.active_domain == "active.xyz"
        assert isinstance(restored.owned_domains[0]["purchased_at"], datetime)
        assert isinstance(restored.owned_domains[0]["expires_at"], datetime)

    def test_prune_expired_domains(self):
        """Pruning should remove expired entries and keep active in sync."""
        manager = DomainRotationManager(monthly_budget=50.0)
        now = datetime.now()
        manager.owned_domains = [
            {
                "domain": "expired.xyz",
                "expires_at": now - timedelta(days=1),
            },
            {
                "domain": "valid.xyz",
                "expires_at": now + timedelta(days=1),
            },
        ]
        manager.active_domain = "expired.xyz"

        result = manager.prune_expired_domains(now=now)

        assert result["removed"] == 1
        assert result["remaining"] == 1
        assert result["active_domain"] == "valid.xyz"
        assert manager.active_domain == "valid.xyz"
