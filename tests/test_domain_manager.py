"""
Tests for domain management module
"""
import pytest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET
from domain_manager import (
    DomainAPIClient, PorkbunAPIClient, NamecheapAPIClient, DomainRotationManager
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


class TestNamecheapAPIClient:
    """Test Namecheap API client"""

    def test_search_domain_available_with_pricing(self):
        """Search returns availability and pricing lookup is used."""
        client = NamecheapAPIClient(api_user="api-user", api_key="api-key")
        client._make_request = Mock(return_value={
            "success": True,
            "root": ET.fromstring(
                '<ApiResponse Status="OK"><CommandResponse>'
                '<DomainCheckResult Domain="example.xyz" Available="true" />'
                '</CommandResponse></ApiResponse>'
            )
        })
        client.get_pricing = Mock(return_value={"registration": 1.49})

        result = client.search_domain("example.xyz")

        assert result["available"] is True
        assert result["price"] == 1.49
        client.get_pricing.assert_called_once_with("xyz")

    def test_purchase_domain_requires_contact(self):
        """Purchase fails when contact details are missing."""
        client = NamecheapAPIClient(api_user="api-user", api_key="api-key")
        result = client.purchase_domain("example.xyz")

        assert result["success"] is False
        assert "Missing required Namecheap contact fields" in result["message"]


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

    def test_configure_and_get_config_porkbun(self):
        """Manager stores provider configuration and budget."""
        manager = DomainRotationManager(monthly_budget=25.0)
        manager.configure(
            api_key="pk_live_test",
            secret_key="sk_live_test",
            monthly_budget=50.0,
            provider="porkbun"
        )

        config = manager.get_config()
        assert config["primary_provider"] == "porkbun"
        assert config["monthly_budget"] == 50.0
        assert config["providers"]["porkbun"]["configured"] is True

    def test_multi_provider_fallback_finds_domain(self):
        """If primary provider has no result, fallback provider can succeed."""
        primary = Mock(spec=DomainAPIClient)
        fallback = Mock(spec=DomainAPIClient)

        primary.search_domain.return_value = {"available": False}
        fallback.search_domain.return_value = {
            "available": True,
            "domain": "fallback123.xyz",
            "price": 1.99,
        }

        manager = DomainRotationManager(monthly_budget=50.0)
        manager.add_api_client("porkbun", primary)
        manager.add_api_client("namecheap", fallback)
        manager.set_primary_provider("porkbun")

        result = manager.find_cheap_available_domain(max_price=5.0, max_attempts=2)

        assert result is not None
        assert result["provider"] == "namecheap"
        assert result["price"] == 1.99

    def test_rotate_domain_return_details(self):
        """Detailed rotate response includes provider and budget status."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "abc123.xyz",
            "price": 1.49,
        }
        mock_client.purchase_domain.return_value = {
            "success": True,
            "domain": "abc123.xyz",
        }

        manager = DomainRotationManager(monthly_budget=10.0)
        manager.add_api_client("porkbun", mock_client)
        manager.set_primary_provider("porkbun")

        result = manager.rotate_domain(return_details=True)

        assert result["success"] is True
        assert result["domain"] == "abc123.xyz"
        assert result["provider"] == "porkbun"
        assert result["budget_status"]["current_spending"] == 1.49
