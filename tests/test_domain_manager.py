"""
Tests for domain management module
"""
import pytest
from unittest.mock import Mock, patch
from domain_manager import (
    DomainAPIClient,
    PorkbunAPIClient,
    NamecheapAPIClient,
    DomainRotationManager,
    create_domain_api_client
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

    def test_configure_porkbun(self):
        """Test manager configure helper for Porkbun."""
        manager = DomainRotationManager()
        result = manager.configure(
            registrar="porkbun",
            api_key="pk_test",
            api_secret="sk_test",
            monthly_budget=25.0
        )

        assert result["configured"] is True
        assert result["registrar"] == "porkbun"
        assert manager.monthly_budget == 25.0
        assert isinstance(manager.api_client, PorkbunAPIClient)

    def test_configure_namecheap(self):
        """Test manager configure helper for Namecheap."""
        manager = DomainRotationManager()
        result = manager.configure(
            registrar="namecheap",
            api_key="nc_key",
            username="nc_user",
            client_ip="203.0.113.1",
            monthly_budget=30.0
        )

        assert result["configured"] is True
        assert result["registrar"] == "namecheap"
        assert result["username"] == "nc_user"
        assert isinstance(manager.api_client, NamecheapAPIClient)

    def test_normalize_price_currency_string(self):
        """Test currency string normalization."""
        assert DomainRotationManager._normalize_price("$2.99") == 2.99
        assert DomainRotationManager._normalize_price("€3.50") == 3.5
        assert DomainRotationManager._normalize_price("N/A") is None


class TestNamecheapAPIClient:
    """Test Namecheap API client."""

    @patch('domain_manager.requests.Session')
    def test_search_domain_available(self, mock_session_class):
        """Test Namecheap availability parsing from XML."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = (
            '<ApiResponse Status="OK">'
            '<CommandResponse>'
            '<DomainCheckResult Domain="example.xyz" Available="true" '
            'IsPremiumName="false" />'
            '</CommandResponse>'
            '</ApiResponse>'
        )
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = NamecheapAPIClient(
            api_key="nc_key",
            username="nc_user",
            client_ip="203.0.113.1"
        )
        result = client.search_domain("example.xyz")

        assert result["domain"] == "example.xyz"
        assert result["available"] is True
        assert result["currency"] == "USD"

    @patch('domain_manager.requests.Session')
    def test_purchase_requires_contact_profile(self, mock_session_class):
        """Test Namecheap purchase guard when contact profile is missing."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        client = NamecheapAPIClient(
            api_key="nc_key",
            username="nc_user",
            client_ip="203.0.113.1"
        )
        result = client.purchase_domain("example.xyz")

        assert result["success"] is False
        assert "contact profile" in result["message"].lower()

    @patch('domain_manager.requests.Session')
    def test_purchase_domain_success(self, mock_session_class):
        """Test Namecheap purchase XML parsing."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = (
            '<ApiResponse Status="OK">'
            '<CommandResponse>'
            '<DomainCreateResult Domain="example.xyz" Registered="true" '
            'OrderID="123456" />'
            '</CommandResponse>'
            '</ApiResponse>'
        )
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = NamecheapAPIClient(
            api_key="nc_key",
            username="nc_user",
            client_ip="203.0.113.1",
            contact_profile={"email_address": "ops@example.com"}
        )
        result = client.purchase_domain("example.xyz")

        assert result["success"] is True
        assert result["order_id"] == "123456"


def test_create_domain_api_client_namecheap():
    """Test registrar factory for Namecheap."""
    client = create_domain_api_client(
        "namecheap",
        api_key="nc_key",
        username="nc_user",
        client_ip="203.0.113.1"
    )
    assert isinstance(client, NamecheapAPIClient)
