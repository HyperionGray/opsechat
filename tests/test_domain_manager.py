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

    def test_configure_and_get_config(self):
        """Test manager configuration and masked config access"""
        manager = DomainRotationManager()
        result = manager.configure(
            api_key="pk1_testkey",
            secret_key="sk1_testsecret",
            monthly_budget=25.0
        )

        assert result is True
        cfg = manager.get_config()
        assert cfg["configured"] is True
        assert cfg["provider"] == "porkbun"
        assert cfg["monthly_budget"] == 25.0
        assert cfg["api_key_masked"].endswith("tkey")
        assert cfg["secret_key_masked"].endswith("cret")

    def test_search_cheap_domains_returns_sorted_matches(self):
        """Search should return multiple domains sorted by price"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.side_effect = [
            {"available": True, "domain": "a.xyz", "price": "4.50"},
            {"available": True, "domain": "b.xyz", "price": "1.99"},
            {"available": True, "domain": "c.xyz", "price": "3.25"},
        ]

        manager = DomainRotationManager(mock_client)
        results = manager.search_cheap_domains(limit=3, max_attempts=3)

        assert len(results) == 3
        assert [r["domain"] for r in results] == ["b.xyz", "c.xyz", "a.xyz"]
        assert all(isinstance(r["price"], float) for r in results)

    def test_rotate_to_new_domain_test_mode(self):
        """Test mode rotation should not call purchase API"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "testmode.xyz",
            "price": "2.49"
        }

        manager = DomainRotationManager(mock_client, monthly_budget=10.0)
        manager.set_test_mode(True)
        result = manager.rotate_to_new_domain()

        assert result["success"] is True
        assert result["domain"] == "testmode.xyz"
        assert result["cost"] == 2.49
        assert manager.active_domain == "testmode.xyz"
        mock_client.purchase_domain.assert_not_called()

    def test_state_export_import_round_trip(self):
        """Exported state should import with datetime restoration"""
        manager = DomainRotationManager(monthly_budget=20.0)
        manager.current_spending = 5.0
        manager.active_domain = "active.xyz"
        manager.owned_domains = [{
            "domain": "active.xyz",
            "price": 5.0,
            "purchased_at": "2026-03-30T10:11:12",
            "expires_at": "2027-03-30T10:11:12"
        }]

        # Import from json-safe strings
        manager.import_state(manager.export_state())
        exported = manager.export_state()

        assert exported["monthly_budget"] == 20.0
        assert exported["current_spending"] == 5.0
        assert exported["active_domain"] == "active.xyz"
        assert exported["owned_domains"][0]["purchased_at"].startswith("2026-03-30T10:11:12")
