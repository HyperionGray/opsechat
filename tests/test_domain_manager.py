"""
Tests for domain management module
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
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

    def test_state_export_and_load_round_trip(self):
        """State export/load should preserve values and normalize datetimes."""
        now = datetime(2026, 3, 1, 10, 30, 0)
        manager = DomainRotationManager(monthly_budget=50.0)
        manager.current_spending = 2.99
        manager.owned_domains = [{
            "domain": "test123.xyz",
            "price": "2.99",
            "purchased_at": now,
            "expires_at": now + timedelta(days=365)
        }]
        manager.active_domain = "test123.xyz"

        state = manager.export_state()

        assert isinstance(state["owned_domains"][0]["purchased_at"], str)
        assert isinstance(state["owned_domains"][0]["expires_at"], str)

        reloaded = DomainRotationManager(monthly_budget=50.0)
        reloaded.load_state(state)

        assert reloaded.current_spending == 2.99
        assert reloaded.active_domain == "test123.xyz"
        assert len(reloaded.owned_domains) == 1
        assert isinstance(reloaded.owned_domains[0]["purchased_at"], datetime)
        assert isinstance(reloaded.owned_domains[0]["expires_at"], datetime)
        assert reloaded.owned_domains[0]["price"] == 2.99

    def test_cleanup_expired_domains_updates_active_domain(self):
        """Expired domains should be removed and active domain reassigned."""
        now = datetime(2026, 3, 10, 12, 0, 0)
        manager = DomainRotationManager(monthly_budget=50.0)
        manager.owned_domains = [
            {"domain": "old.xyz", "expires_at": now - timedelta(days=1)},
            {"domain": "current.xyz", "expires_at": now + timedelta(days=30)}
        ]
        manager.active_domain = "old.xyz"

        summary = manager.cleanup_expired_domains(reference_time=now)

        assert summary["removed_count"] == 1
        assert summary["removed_domains"] == ["old.xyz"]
        assert summary["remaining_count"] == 1
        assert summary["active_domain"] == "current.xyz"
        assert manager.active_domain == "current.xyz"

    def test_sync_owned_domains_adds_new_domains_without_duplicates(self):
        """Sync should add missing domains and ignore duplicates."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.list_domains.return_value = [
            "existing.xyz", "newdomain.xyz", "newdomain.xyz", ""
        ]

        manager = DomainRotationManager(api_client=mock_client, monthly_budget=50.0)
        manager.owned_domains = [{"domain": "existing.xyz"}]
        manager.active_domain = "existing.xyz"

        result = manager.sync_owned_domains()

        assert result["success"] is True
        assert result["added_count"] == 1
        assert result["added_domains"] == ["newdomain.xyz"]
        assert result["local_total"] == 2
