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

    def test_configure_sets_client_and_budget(self):
        """configure() should initialize provider and budget"""
        manager = DomainRotationManager(monthly_budget=10.0)
        config = manager.configure(
            api_key="pk_test_1234",
            secret_key="sk_test_5678",
            monthly_budget=25.0
        )

        assert manager.api_client is not None
        assert manager.monthly_budget == 25.0
        assert config["configured"] is True
        assert config["api_key_last4"] == "1234"
        assert config["remaining_budget"] == 25.0

    def test_search_cheap_domains_returns_sorted_matches(self):
        """search_cheap_domains should return sorted priced results"""
        mock_client = Mock(spec=DomainAPIClient)
        responses = [
            {"available": True, "price": "3.50", "currency": "USD"},
            {"available": True, "price": "1.99", "currency": "USD"},
            {"available": False, "price": "0.99", "currency": "USD"},
            {"available": True, "price": "2.25", "currency": "USD"},
        ]

        def search_side_effect(_domain):
            if responses:
                return responses.pop(0)
            return {"available": False, "price": "99.99", "currency": "USD"}

        mock_client.search_domain.side_effect = search_side_effect

        manager = DomainRotationManager(mock_client)
        results = manager.search_cheap_domains(tlds=["xyz"], max_price=5.0, limit=3)

        assert len(results) == 3
        assert [entry["price"] for entry in results] == [1.99, 2.25, 3.5]
        assert all(entry["domain"].endswith(".xyz") for entry in results)

    def test_export_and_load_state_normalizes_datetime(self):
        """state export/load should be JSON-safe and type-safe"""
        manager = DomainRotationManager(monthly_budget=50.0)
        manager.current_spending = 3.0
        manager.active_domain = "one.xyz"
        manager.owned_domains = [{
            "domain": "one.xyz",
            "price": 3.0,
            "purchased_at": datetime(2026, 1, 1, 12, 0, 0),
            "expires_at": datetime(2027, 1, 1, 12, 0, 0)
        }]

        exported = manager.export_state()
        assert exported["current_spending"] == 3.0
        assert isinstance(exported["owned_domains"][0]["purchased_at"], str)
        assert isinstance(exported["owned_domains"][0]["expires_at"], str)

        loaded = DomainRotationManager(monthly_budget=50.0)
        loaded.load_state(
            owned_domains=exported["owned_domains"],
            current_spending=exported["current_spending"],
            active_domain=exported["active_domain"]
        )
        assert loaded.current_spending == 3.0
        assert loaded.active_domain == "one.xyz"
        assert isinstance(loaded.owned_domains[0]["purchased_at"], datetime)
        assert isinstance(loaded.owned_domains[0]["expires_at"], datetime)

    def test_rotate_to_new_domain_returns_structured_success(self):
        """rotate_to_new_domain should return structured API response"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "price": 2.99,
            "currency": "USD"
        }
        mock_client.purchase_domain.return_value = {
            "success": True,
            "domain": "new.xyz"
        }

        manager = DomainRotationManager(mock_client, monthly_budget=20.0)
        manager.active_domain = "old.xyz"
        result = manager.rotate_to_new_domain()

        assert result["success"] is True
        assert result["previous_domain"] == "old.xyz"
        assert result["domain"].endswith((".xyz", ".club", ".online", ".site", ".website"))
        assert result["cost"] == 2.99
        assert "budget_status" in result
