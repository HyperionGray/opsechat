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
        """Test manager configuration and masked secrets output."""
        manager = DomainRotationManager()
        masked = manager.configure(
            api_key="pk1_testvalue",
            secret_key="sk1_testsecret",
            monthly_budget=12.5
        )

        assert masked["configured"] is True
        assert masked["monthly_budget"] == 12.5
        assert masked["api_key"].endswith("alue")
        assert "*" in masked["api_key"]
        assert masked["secret_key"].endswith("cret")

        unmasked = manager.get_config(mask_secrets=False)
        assert unmasked["api_key"] == "pk1_testvalue"
        assert unmasked["secret_key"] == "sk1_testsecret"

    def test_search_cheap_domains(self):
        """Test multi-domain search API."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.side_effect = (
            lambda domain: {"available": True, "domain": domain, "price": "1.99", "currency": "USD"}
        )

        manager = DomainRotationManager(mock_client)
        manager.generate_random_domain = Mock(side_effect=[
            "one.xyz",
            "two.xyz",
            "one.xyz",
            "three.xyz",
            "four.xyz",
        ])

        results = manager.search_cheap_domains(tlds=["xyz"], limit=3, max_attempts=5, max_price=2.5)
        assert len(results) == 3
        assert len({item["domain"] for item in results}) == 3
        assert all(item["price"] <= 2.5 for item in results)

    def test_rotate_to_new_domain(self):
        """Test detailed rotation result API."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "nextdomain.xyz",
            "price": "2.75",
            "currency": "USD"
        }
        mock_client.purchase_domain.return_value = {
            "success": True,
            "domain": "nextdomain.xyz"
        }

        manager = DomainRotationManager(mock_client, monthly_budget=20.0)
        result = manager.rotate_to_new_domain(max_price=3.0, max_attempts=1, tlds=["xyz"])

        assert result["success"] is True
        assert result["domain"] == "nextdomain.xyz"
        assert result["cost"] == 2.75
        assert manager.active_domain == "nextdomain.xyz"

    def test_purchase_in_test_mode_without_api_client(self):
        """Test simulated purchases in test mode."""
        manager = DomainRotationManager(monthly_budget=10.0)
        manager.set_test_mode(True)

        assert manager.purchase_domain_if_budget_allows("simulated.xyz", 1.5) is True
        assert manager.get_active_domain() == "simulated.xyz"
        assert len(manager.get_owned_domains()) == 1

    def test_import_export_state(self):
        """Test JSON-safe state import/export."""
        manager = DomainRotationManager(monthly_budget=50.0)
        manager.import_state({
            "monthly_budget": 25.0,
            "current_spending": "2.99",
            "active_domain": "saved.xyz",
            "owned_domains": [
                {
                    "domain": "saved.xyz",
                    "price": "2.99",
                    "purchased_at": "2026-01-01T00:00:00Z",
                    "expires_at": "2027-01-01T00:00:00Z"
                }
            ],
            "test_mode": True
        })

        exported = manager.export_state()
        assert exported["monthly_budget"] == 25.0
        assert exported["current_spending"] == 2.99
        assert exported["active_domain"] == "saved.xyz"
        assert exported["test_mode"] is True
        assert exported["owned_domains"][0]["domain"] == "saved.xyz"
