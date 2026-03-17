"""
Tests for domain management module
"""
from datetime import datetime
import pytest
from unittest.mock import Mock, patch
from domain_manager import (
    DomainAPIClient, PorkbunAPIClient, DomainRotationManager, NamecheapAPIClient
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

    def test_rotate_to_new_domain_result_shape(self):
        """Test structured rotate result"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "test789.xyz",
            "price": 2.49
        }
        mock_client.purchase_domain.return_value = {
            "success": True,
            "domain": "test789.xyz"
        }

        manager = DomainRotationManager(monthly_budget=50.0)
        manager.add_api_client("porkbun", mock_client, set_active=True)
        result = manager.rotate_to_new_domain()

        assert result["success"] is True
        assert result["domain"].endswith(".xyz")
        assert result["provider"] == "porkbun"

    def test_configure_and_get_config(self):
        """Test dynamic provider configuration metadata"""
        manager = DomainRotationManager(monthly_budget=10.0)
        with patch("domain_manager.PorkbunAPIClient") as mock_porkbun:
            manager.configure(
                provider="porkbun",
                api_key="pk_test",
                secret_key="sk_test",
                monthly_budget=25.0,
            )
            assert mock_porkbun.called

        config = manager.get_config()
        assert config["configured"] is True
        assert config["active_provider"] == "porkbun"
        assert "porkbun" in config["providers"]
        assert config["monthly_budget"] == 25.0

    def test_find_domain_uses_pricing_fallback(self):
        """When search has no price, fallback to provider pricing endpoint."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {"available": True, "domain": "abc.xyz", "price": None}
        mock_client.get_pricing.return_value = {"registration": "2.99"}

        manager = DomainRotationManager(monthly_budget=20.0)
        manager.add_api_client("porkbun", mock_client, set_active=True)

        result = manager.find_cheap_available_domain(max_price=3.0, max_attempts=1)
        assert result is not None
        assert result["price"] == 2.99
        assert result["provider"] == "porkbun"

    def test_export_import_state_roundtrip(self):
        """State export/import should preserve datetimes and metadata."""
        manager = DomainRotationManager(monthly_budget=30.0)
        manager.current_spending = 5.0
        manager.active_domain = "roundtrip.xyz"
        manager.active_provider = "porkbun"
        manager.owned_domains = [{
            "domain": "roundtrip.xyz",
            "price": 1.99,
            "purchased_at": datetime.now(),
            "expires_at": datetime.now(),
            "provider": "porkbun",
        }]

        exported = manager.export_state()
        assert isinstance(exported["owned_domains"][0]["purchased_at"], str)
        assert isinstance(exported["owned_domains"][0]["expires_at"], str)

        restored = DomainRotationManager(monthly_budget=1.0)
        restored.import_state(exported)
        assert restored.active_domain == "roundtrip.xyz"
        assert restored.active_provider == "porkbun"
        assert restored.current_spending == 5.0
        assert restored.owned_domains[0]["domain"] == "roundtrip.xyz"
        assert hasattr(restored.owned_domains[0]["purchased_at"], "isoformat")


class TestNamecheapAPIClient:
    """Test Namecheap API client parsing behavior."""

    @patch("domain_manager.requests.Session")
    def test_search_domain_available(self, mock_session_class):
        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<ApiResponse Status="OK">
  <CommandResponse>
    <DomainCheckResult Domain="example.xyz" Available="true" IsPremiumName="false" />
  </CommandResponse>
</ApiResponse>
"""
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = NamecheapAPIClient(
            api_key="test_key",
            username="test_user",
            client_ip="127.0.0.1",
            sandbox=True,
        )
        result = client.search_domain("example.xyz")
        assert result["available"] is True
        assert result["domain"] == "example.xyz"
