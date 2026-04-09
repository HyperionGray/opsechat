"""
Tests for domain management module
"""
from datetime import datetime
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
        
        assert result["success"] is True
        assert result["domain"] == "test123.xyz"
        assert manager.current_spending == 2.99
        assert len(manager.owned_domains) == 1
        assert manager.active_domain == "test123.xyz"
    
    def test_purchase_domain_if_budget_allows_exceeds_budget(self):
        """Test domain purchase exceeds budget"""
        mock_client = Mock(spec=DomainAPIClient)
        
        manager = DomainRotationManager(mock_client, monthly_budget=5.0)
        manager.current_spending = 4.0
        
        result = manager.purchase_domain_if_budget_allows("test123.xyz", 2.0)
        
        assert result["success"] is False
        assert result["message"] == "Budget exceeded"
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
        result = manager.rotate_domain()
        
        assert result["success"] is True
        assert result["active_domain"] == "test456.xyz"
        assert manager.active_domain == "test456.xyz"

    def test_search_available_domains_returns_sorted_candidates(self):
        """Test multi-candidate search and price normalization."""
        mock_client = Mock(spec=DomainAPIClient)

        search_results = {
            "alpha.xyz": {"domain": "alpha.xyz", "available": True, "price": "$4.20", "currency": "USD"},
            "beta.club": {"domain": "beta.club", "available": True, "price": "2.10", "currency": "USD"},
            "gamma.online": {"domain": "gamma.online", "available": True, "price": "9.99", "currency": "USD"},
            "delta.site": {"domain": "delta.site", "available": False, "price": "1.99", "currency": "USD"},
            "epsilon.website": {"domain": "epsilon.website", "available": True, "price": "3.50", "currency": "USD"},
        }
        mock_client.search_domain.side_effect = lambda domain: search_results[domain]

        manager = DomainRotationManager(mock_client)
        generated_domains = iter(
            ["alpha.xyz", "beta.club", "gamma.online", "delta.site", "epsilon.website"]
        )
        manager.generate_random_domain = lambda tld, length=8: next(generated_domains)

        candidates = manager.search_available_domains(
            max_price=5.0,
            max_attempts=5,
            max_results=5,
        )

        assert [c["domain"] for c in candidates] == ["beta.club", "epsilon.website", "alpha.xyz"]
        assert candidates[0]["price"] == 2.10
        assert candidates[1]["price"] == 3.50
        assert candidates[2]["price"] == 4.20

    def test_export_and_load_state_serializes_datetimes(self):
        """Test state persistence helpers for CLI/json storage."""
        manager = DomainRotationManager(monthly_budget=50.0)
        manager.current_spending = 3.25
        manager.active_domain = "persisted.xyz"
        manager.owned_domains = [{
            "domain": "persisted.xyz",
            "price": 3.25,
            "purchased_at": datetime(2026, 1, 2, 3, 4, 5),
            "expires_at": datetime(2027, 1, 2, 3, 4, 5),
        }]

        exported = manager.export_state()
        assert exported["owned_domains"][0]["purchased_at"].startswith("2026-01-02T03:04:05")

        loaded = DomainRotationManager(monthly_budget=1.0)
        loaded.load_state(exported)

        assert loaded.monthly_budget == 50.0
        assert loaded.current_spending == 3.25
        assert loaded.active_domain == "persisted.xyz"
        assert loaded.owned_domains[0]["domain"] == "persisted.xyz"
        assert loaded.owned_domains[0]["price"] == 3.25
        assert isinstance(loaded.owned_domains[0]["purchased_at"], datetime)
