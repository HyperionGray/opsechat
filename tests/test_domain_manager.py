"""
Tests for domain management module
"""
import pytest
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

    def test_configure_sets_api_and_policy(self):
        """Test configure stores credentials and policy values"""
        manager = DomainRotationManager()
        result = manager.configure(
            api_key="pk_test_1234",
            secret_key="sk_test_5678",
            monthly_budget=42.5,
            max_domain_price=3.25,
            cheap_tlds=["xyz", ".club", "ONLINE"]
        )

        assert result["success"] is True
        assert manager.api_client is not None
        assert manager.monthly_budget == 42.5
        assert manager.max_domain_price == 3.25
        assert manager.cheap_tlds == ["xyz", "club", "online"]

    def test_get_config_masks_secrets(self):
        """Test get_config masks API credentials by default"""
        manager = DomainRotationManager()
        manager.configure("pk_abcdefghijkl", "sk_abcdefghijkl", 20.0)

        config = manager.get_config(mask_secrets=True)
        assert config["api_configured"] is True
        assert config["api_key"].endswith("ijkl")
        assert "*" in config["api_key"]
        assert config["api_secret"].endswith("ijkl")
        assert "*" in config["api_secret"]

    def test_find_cheap_available_domain_ignores_invalid_price(self):
        """Test invalid registrar prices are skipped safely"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.side_effect = [
            {"available": True, "domain": "bad.xyz", "price": "N/A"},
            {"available": True, "domain": "good.xyz", "price": "2.10"},
        ]

        manager = DomainRotationManager(mock_client)
        result = manager.find_cheap_available_domain(max_price=5.0, max_attempts=2, tlds=["xyz"])

        assert result is not None
        assert result["price"] == 2.10

    def test_rotate_domain_return_details(self):
        """Test detailed rotation response shape"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "next123.xyz",
            "price": 1.99
        }
        mock_client.purchase_domain.return_value = {"success": True}

        manager = DomainRotationManager(mock_client, monthly_budget=10.0)
        manager.active_domain = "old123.xyz"
        result = manager.rotate_domain(return_details=True)

        assert result["success"] is True
        assert result["domain"] == "next123.xyz"
        assert result["previous_domain"] == "old123.xyz"
        assert result["price"] == 1.99
        assert result["remaining_budget"] == 8.01

    def test_export_import_state_round_trip(self):
        """Test serialized state can be imported back safely"""
        manager = DomainRotationManager(monthly_budget=30.0, max_domain_price=4.0, cheap_tlds=["xyz"])
        manager.current_spending = 3.5
        manager.active_domain = "active.xyz"
        manager.owned_domains = [{
            "domain": "active.xyz",
            "price": 3.5,
            "purchased_at": "2026-03-01T10:30:00",
            "expires_at": "2027-03-01T10:30:00",
        }]

        exported = manager.export_state()
        restored = DomainRotationManager()
        restored.import_state(exported)

        assert restored.current_spending == 3.5
        assert restored.monthly_budget == 30.0
        assert restored.max_domain_price == 4.0
        assert restored.cheap_tlds == ["xyz"]
        assert restored.active_domain == "active.xyz"
        assert len(restored.owned_domains) == 1
        assert restored.owned_domains[0]["domain"] == "active.xyz"
