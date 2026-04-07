"""
Tests for domain management module
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from domain_manager import (
    DomainAPIClient, PorkbunAPIClient, DomainRotationManager
)


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

    @patch("domain_manager.PorkbunAPIClient")
    def test_configure_sets_client_and_budget(self, mock_porkbun):
        """Configure should set API client and update budget."""
        manager = DomainRotationManager(monthly_budget=50.0)
        manager.configure(api_key="pk_test_1234", secret_key="sk_test_5678", monthly_budget=25.0)

        mock_porkbun.assert_called_once_with("pk_test_1234", "sk_test_5678")
        assert manager.api_client is not None
        assert manager.monthly_budget == 25.0

    def test_get_config_masks_secrets(self):
        """Configuration view should not expose raw API credentials."""
        manager = DomainRotationManager()
        manager.set_api_client(PorkbunAPIClient("pk_live_abcdef", "sk_live_uvwxyz"))
        manager.current_spending = 3.5
        manager.active_domain = "test.xyz"
        config = manager.get_config()

        assert config["configured"] is True
        assert config["provider"] == "PorkbunAPIClient"
        assert config["api_key"].endswith("cdef")
        assert "*" in config["api_key"]
        assert config["api_secret"].endswith("wxyz")
        assert "*" in config["api_secret"]
        assert config["active_domain"] == "test.xyz"

    def test_export_import_state_roundtrip(self):
        """State export/import should preserve values and normalize datetimes."""
        manager = DomainRotationManager(monthly_budget=40.0)
        manager.current_spending = 7.25
        manager.active_domain = "active.xyz"
        manager.owned_domains = [
            {
                "domain": "active.xyz",
                "price": 2.99,
                "purchased_at": datetime(2026, 1, 2, 3, 4, 5),
                "expires_at": datetime(2027, 1, 2, 3, 4, 5),
            }
        ]

        exported = manager.export_state()
        assert isinstance(exported["owned_domains"][0]["purchased_at"], str)
        assert isinstance(exported["owned_domains"][0]["expires_at"], str)

        restored = DomainRotationManager()
        restored.import_state(exported)

        assert restored.monthly_budget == 40.0
        assert restored.current_spending == 7.25
        assert restored.active_domain == "active.xyz"
        assert isinstance(restored.owned_domains[0]["purchased_at"], datetime)
        assert isinstance(restored.owned_domains[0]["expires_at"], datetime)

    def test_rotate_domain_with_result_returns_error_payload(self):
        """Structured rotate API should return a stable failure payload."""
        manager = DomainRotationManager()
        result = manager.rotate_domain_with_result()

        assert result["success"] is False
        assert "error" in result
        assert result["active_domain"] is None
