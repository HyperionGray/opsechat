"""
Tests for domain management module
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from domain_manager import (
    DomainAPIClient, PorkbunAPIClient, DomainRotationManager
)


def test_domain_api_client_is_abstract():
    """Base client cannot be instantiated directly."""
    with pytest.raises(TypeError):
        DomainAPIClient("api-key")


class TestPorkbunAPIClient:
    """Test Porkbun API client"""
    
    @patch('domain_manager.requests.Session')
    def test_search_domain_available(self, mock_session_class):
        """Test domain availability search"""
        # Setup mock
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "SUCCESS",
            "isAvailable": True,
            "price": "2.99",
            "currency": "USD"
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # Create client
        client = PorkbunAPIClient("test_key", "test_secret")
        
        # Search domain
        result = client.search_domain("test123.xyz")
        
        assert result["available"] is True
        assert result["domain"] == "test123.xyz"
        assert result["price"] == "2.99"
    
    @patch('domain_manager.requests.Session')
    def test_search_domain_unavailable(self, mock_session_class):
        """Test domain unavailable"""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "SUCCESS",
            "isAvailable": False
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = PorkbunAPIClient("test_key", "test_secret")
        result = client.search_domain("google.com")
        
        assert result["available"] is False
    
    @patch('domain_manager.requests.Session')
    def test_get_pricing(self, mock_session_class):
        """Test pricing retrieval"""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "SUCCESS",
            "pricing": {
                "registration": "9.99",
                "renewal": "9.99",
                "transfer": "9.99"
            }
        }
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        client = PorkbunAPIClient("test_key", "test_secret")
        result = client.get_pricing("com")
        
        assert result["tld"] == "com"
        assert result["registration"] == "9.99"


class TestDomainRotationManager:
    """Test domain rotation manager"""
    
    def test_generate_random_domain(self):
        """Test random domain generation"""
        manager = DomainRotationManager()
        
        domain = manager.generate_random_domain("xyz", 8)
        
        assert domain.endswith(".xyz")
        assert len(domain.split(".")[0]) == 8
    
    def test_find_cheap_available_domain_no_client(self):
        """Test finding domain without API client"""
        manager = DomainRotationManager()
        
        result = manager.find_cheap_available_domain()
        
        assert result is None
    
    def test_find_cheap_available_domain_success(self):
        """Test finding cheap domain successfully"""
        # Create mock API client
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "test123.xyz",
            "price": 2.99
        }
        
        manager = DomainRotationManager(mock_client)
        result = manager.find_cheap_available_domain(max_price=5.0, max_attempts=3)
        
        assert result is not None
        assert result["domain"].endswith((".xyz", ".club", ".online", ".site", ".website"))
        assert result["price"] <= 5.0
    
    def test_purchase_domain_if_budget_allows_success(self):
        """Test domain purchase within budget"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.purchase_domain.return_value = {
            "success": True,
            "domain": "test123.xyz",
            "order_id": "12345"
        }
        
        manager = DomainRotationManager(mock_client, monthly_budget=50.0)
        result = manager.purchase_domain_if_budget_allows("test123.xyz", 2.99)
        
        assert result is True
        assert manager.current_spending == 2.99
        assert len(manager.owned_domains) == 1
        assert manager.active_domain == "test123.xyz"
    
    def test_purchase_domain_if_budget_allows_exceeds_budget(self):
        """Test domain purchase exceeds budget"""
        mock_client = Mock(spec=DomainAPIClient)
        
        manager = DomainRotationManager(mock_client, monthly_budget=5.0)
        manager.current_spending = 4.0
        
        result = manager.purchase_domain_if_budget_allows("test123.xyz", 2.0)
        
        assert result is False
        assert manager.current_spending == 4.0
        assert len(manager.owned_domains) == 0
    
    def test_get_budget_status(self):
        """Test budget status retrieval"""
        manager = DomainRotationManager(monthly_budget=50.0)
        manager.current_spending = 10.0
        manager.owned_domains = [{"domain": "test.xyz"}]
        
        status = manager.get_budget_status()
        
        assert status["monthly_budget"] == 50.0
        assert status["current_spending"] == 10.0
        assert status["remaining"] == 40.0
        assert status["domains_owned"] == 1
    
    def test_rotate_domain(self):
        """Test domain rotation"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "test456.xyz",
            "price": 2.99
        }
        mock_client.purchase_domain.return_value = {
            "success": True,
            "domain": "test456.xyz"
        }
        
        manager = DomainRotationManager(mock_client, monthly_budget=50.0)
        new_domain = manager.rotate_domain()
        
        assert new_domain is not None
        assert manager.active_domain == new_domain

    def test_parse_price_formats(self):
        """Test price parsing for registrar response formats."""
        manager = DomainRotationManager()
        assert manager._parse_price("$2.99 USD") == 2.99
        assert manager._parse_price("1,234.56") == 1234.56
        assert manager._parse_price("not-a-price") is None

    def test_find_cheap_available_domain_skips_invalid_price(self):
        """Skip available domains when registrar price is invalid."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.side_effect = [
            {"available": True, "price": "N/A"},
            {"available": True, "price": "$3.25"},
        ]
        manager = DomainRotationManager(mock_client)

        result = manager.find_cheap_available_domain(max_price=5.0, max_attempts=2)

        assert result is not None
        assert result["price"] == 3.25

    def test_purchase_domain_rejects_invalid_price(self):
        """Invalid purchase price should fail early."""
        mock_client = Mock(spec=DomainAPIClient)
        manager = DomainRotationManager(mock_client, monthly_budget=50.0)

        result = manager.purchase_domain_if_budget_allows("test123.xyz", "n/a")

        assert result is False
        mock_client.purchase_domain.assert_not_called()

    def test_configure_and_get_config(self):
        """Manager exposes config metadata for UI/CLI integrations."""
        manager = DomainRotationManager()
        config = manager.configure("pk_test", secret_key="sk_test", monthly_budget=12.5)

        assert config["configured"] is True
        assert config["api_key_configured"] is True
        assert config["api_secret_configured"] is True
        assert config["monthly_budget"] == 12.5

        with_secrets = manager.get_config(include_secrets=True)
        assert with_secrets["api_key"] == "pk_test"
        assert with_secrets["api_secret"] == "sk_test"

    def test_export_and_load_state_roundtrip(self):
        """Persisted state should roundtrip through JSON-safe payload."""
        manager = DomainRotationManager(monthly_budget=20.0)
        manager.current_spending = 4.2
        manager.active_domain = "abc123.xyz"
        manager.owned_domains = [{
            "domain": "abc123.xyz",
            "price": 2.1,
            "purchased_at": datetime(2026, 1, 2, 3, 4, 5),
            "expires_at": datetime(2027, 1, 2, 3, 4, 5),
        }]

        state = manager.export_state()
        assert isinstance(state["owned_domains"][0]["purchased_at"], str)

        restored = DomainRotationManager(monthly_budget=20.0)
        restored.load_state(state)
        assert restored.current_spending == 4.2
        assert restored.active_domain == "abc123.xyz"
        assert restored.owned_domains[0]["domain"] == "abc123.xyz"
        assert isinstance(restored.owned_domains[0]["purchased_at"], datetime)
