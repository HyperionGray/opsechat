"""
Tests for domain management module
"""
import pytest
from unittest.mock import Mock, patch
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

    def test_find_cheap_available_domain_uses_pricing_fallback(self):
        """If search API omits a price, fallback to registrar pricing"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "fallback123.xyz",
            "price": None,
            "currency": "USD",
        }
        mock_client.get_pricing.return_value = {"registration": "1.49"}

        manager = DomainRotationManager(mock_client)
        result = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1, tlds=["xyz"])

        assert result is not None
        assert result["price"] == 1.49
        assert result["domain"].endswith(".xyz")

    def test_rotate_domain_with_details(self):
        """Structured rotate result should include success and price"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "domain": "testrotate.xyz",
            "price": 2.99,
        }
        mock_client.purchase_domain.return_value = {"success": True}

        manager = DomainRotationManager(mock_client, monthly_budget=50.0)
        result = manager.rotate_domain_with_details()

        assert result["success"] is True
        assert result["domain"] == manager.active_domain
        assert result["price"] == 2.99

    def test_configure_namecheap(self):
        """Manager should configure Namecheap client from credentials"""
        manager = DomainRotationManager()
        cfg = manager.configure(
            api_key="nc_key",
            registrar="namecheap",
            api_user="nc_api_user",
            username="nc_username",
            client_ip="10.0.0.1",
            monthly_budget=25.0,
        )

        assert isinstance(manager.api_client, NamecheapAPIClient)
        assert cfg["registrar"] == "namecheap"
        assert cfg["monthly_budget"] == 25.0
        assert cfg["registrar_settings"]["api_user"] == "nc_api_user"

    def test_export_import_state(self):
        """Exported state should round-trip through import_state"""
        manager = DomainRotationManager(monthly_budget=40.0)
        manager.current_spending = 3.5
        manager.active_domain = "active.xyz"
        manager.owned_domains = [
            {
                "domain": "active.xyz",
                "price": 3.5,
                "purchased_at": __import__("datetime").datetime.now(),
                "expires_at": __import__("datetime").datetime.now(),
            }
        ]

        exported = manager.export_state()
        clone = DomainRotationManager()
        clone.import_state(exported)

        assert clone.monthly_budget == 40.0
        assert clone.current_spending == 3.5
        assert clone.active_domain == "active.xyz"
        assert len(clone.owned_domains) == 1


class TestNamecheapAPIClient:
    """Test Namecheap XML parsing behavior"""

    @patch('domain_manager.requests.Session')
    def test_search_domain_available(self, mock_session_class):
        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
<ApiResponse Status="OK" xmlns="http://api.namecheap.com/xml.response">
  <CommandResponse Type="namecheap.domains.check">
    <DomainCheckResult Domain="example123xyz.com" Available="true" />
  </CommandResponse>
</ApiResponse>"""
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = NamecheapAPIClient(
            api_key="key",
            api_user="apiuser",
            username="user",
            client_ip="127.0.0.1",
            use_sandbox=True,
        )

        result = client.search_domain("example123xyz.com")
        assert result["available"] is True
        assert result["domain"] == "example123xyz.com"

    @patch('domain_manager.requests.Session')
    def test_purchase_domain_failure_bubbles_message(self, mock_session_class):
        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
<ApiResponse Status="ERROR" xmlns="http://api.namecheap.com/xml.response">
  <Errors>
    <Error Number="3051510">Missing required parameter RegistrantFirstName</Error>
  </Errors>
</ApiResponse>"""
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = NamecheapAPIClient(
            api_key="key",
            api_user="apiuser",
            username="user",
            client_ip="127.0.0.1",
        )

        result = client.purchase_domain("example123xyz.com")
        assert result["success"] is False
        assert "Missing required parameter" in result["message"]
