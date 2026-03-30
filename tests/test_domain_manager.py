"""
Tests for domain management module.
"""
from unittest.mock import Mock, patch

from domain_manager import DomainAPIClient, DomainRotationManager, PorkbunAPIClient


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
        mock_client.provider_name = "mock-provider"
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
        mock_client.provider_name = "mock-provider"
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
        assert manager.get_owned_domains()[0]["provider"] == "mock-provider"
    
    def test_purchase_domain_if_budget_allows_exceeds_budget(self):
        """Test domain purchase exceeds budget"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.provider_name = "mock-provider"
        
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
        assert "provider_spending" in status
        assert "provider_budgets" in status
    
    def test_rotate_domain(self):
        """Test domain rotation"""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.provider_name = "mock-provider"
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
        assert manager.active_provider == "mock-provider"

    def test_round_robin_failover_uses_next_provider(self):
        """Round-robin strategy should fail over to next provider."""
        first = Mock(spec=DomainAPIClient)
        first.provider_name = "first"
        first.search_domain.return_value = {
            "available": False,
            "domain": "ignored.xyz",
            "price": 2.50
        }

        second = Mock(spec=DomainAPIClient)
        second.provider_name = "second"
        second.search_domain.return_value = {
            "available": True,
            "domain": "candidate.xyz",
            "price": 1.99
        }

        manager = DomainRotationManager(monthly_budget=50.0, selection_strategy="round-robin")
        manager.add_provider("first", first)
        manager.add_provider("second", second)

        result = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)

        assert result is not None
        assert result["provider"] == "second"
        assert result["price"] == 1.99

    def test_cheapest_strategy_prefers_lower_price(self):
        """Cheapest strategy should choose lower available price."""
        expensive = Mock(spec=DomainAPIClient)
        expensive.provider_name = "expensive"
        expensive.search_domain.return_value = {
            "available": True,
            "domain": "candidate.xyz",
            "price": "4.99"
        }

        cheap = Mock(spec=DomainAPIClient)
        cheap.provider_name = "cheap"
        cheap.search_domain.return_value = {
            "available": True,
            "domain": "candidate.xyz",
            "price": "1.49"
        }

        manager = DomainRotationManager(monthly_budget=50.0, selection_strategy="cheapest")
        manager.add_provider("expensive", expensive)
        manager.add_provider("cheap", cheap)

        result = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)

        assert result is not None
        assert result["provider"] == "cheap"
        assert result["price"] == 1.49

    def test_provider_budget_enforced(self):
        """Provider budget should block purchases even if global budget allows."""
        provider = Mock(spec=DomainAPIClient)
        provider.provider_name = "limited"
        provider.purchase_domain.return_value = {"success": True, "domain": "test123.xyz"}

        manager = DomainRotationManager(monthly_budget=50.0)
        manager.add_provider("limited", provider, monthly_budget=1.00)

        result = manager.purchase_domain_if_budget_allows(
            "test123.xyz",
            2.00,
            provider_name="limited"
        )

        assert result is False
        assert manager.current_spending == 0.0
        assert len(manager.owned_domains) == 0

    def test_rotate_to_new_domain_returns_structured_result(self):
        """rotate_to_new_domain should return structured success payload."""
        provider = Mock(spec=DomainAPIClient)
        provider.provider_name = "mock-provider"
        provider.search_domain.return_value = {
            "available": True,
            "price": "2.25"
        }
        provider.purchase_domain.return_value = {
            "success": True
        }

        manager = DomainRotationManager(provider, monthly_budget=50.0)
        result = manager.rotate_to_new_domain(max_price=5.0, max_attempts=1)

        assert result["success"] is True
        assert result["domain"].endswith((".xyz", ".club", ".online", ".site", ".website"))
        assert result["cost"] == 2.25
        assert result["provider"] == "mock-provider"
