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
        """Test configure/get_config APIs used by routes"""
        manager = DomainRotationManager(monthly_budget=5.0)

        with patch("domain_manager.PorkbunAPIClient") as mock_client_class:
            mock_client_class.return_value = Mock(spec=DomainAPIClient)
            manager.configure(
                api_key="pk_test",
                secret_key="sk_test",
                monthly_budget=12.5,
            )

        config = manager.get_config()
        assert config["api_key"] == "pk_test"
        assert config["secret_key"] == "sk_test"
        assert config["monthly_budget"] == 12.5
        assert config["provider"] == "porkbun"
        assert config["active_provider"] == "porkbun"
        assert "porkbun" in config["registered_providers"]

    def test_add_and_switch_provider_clients(self):
        """Test registering and switching active providers"""
        porkbun_client = Mock(spec=DomainAPIClient)
        namecheap_client = Mock(spec=DomainAPIClient)
        manager = DomainRotationManager(porkbun_client)

        manager.add_api_client("namecheap", namecheap_client)
        assert manager.set_active_api_client("namecheap") is True
        assert manager.api_client is namecheap_client
        assert manager.active_api_client_name == "namecheap"
        assert manager.set_active_api_client("missing") is False

    def test_search_cheap_domains_list_api(self):
        """Test list helper for cheap domain search"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "price": "1.29",
        }
        manager = DomainRotationManager(mock_client)

        results = manager.search_cheap_domains(limit=3, max_attempts=5)
        assert len(results) == 3
        assert all(item["price"] <= 5.0 for item in results)
        assert all("domain" in item for item in results)

    def test_generate_domain_from_pattern(self):
        """Test custom pattern rendering"""
        manager = DomainRotationManager()
        generated = manager.generate_domain_from_pattern(
            "burner-{timestamp}-{random}",
            tld="xyz",
        )
        assert generated.endswith(".xyz")
        assert generated.startswith("burner-")
        assert "{timestamp}" not in generated
        assert "{random}" not in generated

    def test_rotate_to_new_domain_structured_response(self):
        """Test compatibility rotation response shape"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "price": "2.50",
        }
        mock_client.purchase_domain.return_value = {"success": True}
        manager = DomainRotationManager(mock_client, monthly_budget=50.0)

        result = manager.rotate_to_new_domain()
        assert result["success"] is True
        assert "domain" in result
        assert result["provider"] == "default"

    def test_configure_domain_dns_stores_record(self):
        """Test DNS config storage compatibility hook"""
        manager = DomainRotationManager()
        result = manager.configure_domain_dns(
            domain="example.xyz",
            mx_record="mail.example.xyz",
            txt_record="v=spf1 -all",
        )
        assert result["success"] is True
        assert result["dns"]["mx_record"] == "mail.example.xyz"
        assert manager.domain_dns_configs["example.xyz"]["txt_record"] == "v=spf1 -all"


class TestNamecheapAPIClient:
    """Test Namecheap API client behavior"""

    @patch("domain_manager.requests.Session")
    def test_search_domain_available_from_xml(self, mock_session_class):
        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = '<ApiResponse Status="OK"><DomainCheckResult Available="true"/></ApiResponse>'
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = NamecheapAPIClient(
            api_key="test_key",
            username="test_user",
            client_ip="1.2.3.4",
        )
        result = client.search_domain("example.xyz")
        assert result["available"] is True
        assert result["provider"] == "namecheap"
