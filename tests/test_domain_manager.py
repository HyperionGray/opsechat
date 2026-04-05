"""
Tests for domain management module
"""
from datetime import datetime
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

    def test_configure_and_get_config(self):
        """Test web-facing configuration helpers"""
        manager = DomainRotationManager(monthly_budget=20.0)
        result = manager.configure(
            api_key="pk1_test",
            secret_key="sk1_secret",
            monthly_budget=15.5
        )

        assert result["success"] is True
        config = manager.get_config()
        assert config["configured"] is True
        assert config["monthly_budget"] == 15.5
        assert config["api_key"] != "pk1_test"
        assert manager.active_api_client_name == "porkbun"

    def test_add_and_switch_api_clients(self):
        """Test multi-provider registration and switching"""
        client_a = Mock(spec=DomainAPIClient)
        client_b = Mock(spec=DomainAPIClient)
        manager = DomainRotationManager()

        manager.add_api_client("provider_a", client_a, make_default=True)
        manager.add_api_client("provider_b", client_b)

        assert manager.get_api_clients() == ["provider_a", "provider_b"]
        assert manager.api_client is client_a
        assert manager.set_active_api_client("provider_b") is True
        assert manager.api_client is client_b
        assert manager.set_active_api_client("missing") is False

    def test_search_cheap_domains_returns_multiple(self):
        """Test multi-result cheap domain search"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "price": "2.49",
            "currency": "USD"
        }
        manager = DomainRotationManager(mock_client)

        domains = manager.search_cheap_domains(tlds=["xyz"], max_price=3.0, limit=3, max_attempts=5)

        assert len(domains) == 3
        assert all(item["price"] <= 3.0 for item in domains)
        assert all(item["domain"].endswith(".xyz") for item in domains)

    def test_test_mode_purchase_does_not_call_api(self):
        """Test dry-run mode avoids registrar purchase call"""
        mock_client = Mock(spec=DomainAPIClient)
        manager = DomainRotationManager(mock_client, monthly_budget=10.0)
        manager.set_test_mode(True)

        success = manager.purchase_domain_if_budget_allows("dryrun.xyz", 1.5)

        assert success is True
        mock_client.purchase_domain.assert_not_called()
        assert manager.active_domain == "dryrun.xyz"

    def test_export_and_load_state_round_trip(self):
        """Test JSON-safe state persistence helpers"""
        manager = DomainRotationManager(monthly_budget=30.0)
        manager.current_spending = 3.25
        manager.owned_domains = [{
            "domain": "example.xyz",
            "price": 3.25,
            "purchased_at": datetime(2026, 1, 2, 3, 4, 5),
            "expires_at": datetime(2027, 1, 2, 3, 4, 5)
        }]
        manager.active_domain = "example.xyz"

        exported = manager.export_state()
        assert isinstance(exported["owned_domains"][0]["purchased_at"], str)
        assert isinstance(exported["owned_domains"][0]["expires_at"], str)

        restored = DomainRotationManager(monthly_budget=30.0)
        restored.load_state(exported)
        restored_domain = restored.owned_domains[0]
        assert restored.current_spending == 3.25
        assert restored.active_domain == "example.xyz"
        assert restored_domain["domain"] == "example.xyz"
        assert hasattr(restored_domain["purchased_at"], "year")

    def test_rotate_to_new_domain_structured_response(self):
        """Test structured rotate compatibility method"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "price": "1.99",
            "currency": "USD"
        }
        mock_client.purchase_domain.return_value = {"success": True, "domain": "new.xyz"}
        manager = DomainRotationManager(mock_client, monthly_budget=10.0)

        result = manager.rotate_to_new_domain(max_price=3.0)

        assert result["success"] is True
        assert result["domain"] == manager.active_domain
        assert result["cost"] == 1.99
