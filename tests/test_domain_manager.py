"""
Tests for domain management module
"""
import os
import pytest
from unittest.mock import Mock, patch
from domain_manager import (
    DomainAPIClient, PorkbunAPIClient, DomainRotationManager
)
import domain_rotation_cli


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
        manager.generate_random_domain = Mock(return_value="test456.xyz")
        result = manager.rotate_domain()
        
        assert result["success"] is True
        assert result["active_domain"] == "test456.xyz"
        assert manager.active_domain == "test456.xyz"

    def test_search_cheap_domains_respects_limit(self):
        """Test searching multiple cheap domains with a result limit."""
        mock_client = Mock(spec=DomainAPIClient)
        mock_client.search_domain.return_value = {
            "available": True,
            "price": "1.99",
        }
        manager = DomainRotationManager(mock_client)

        results = manager.search_cheap_domains(limit=3, max_attempts=20)

        assert len(results) == 3
        assert all(item["price"] <= 5.0 for item in results)

    def test_set_monthly_budget_clamps_to_zero(self):
        """Test monthly budget setter clamps negative values."""
        manager = DomainRotationManager(monthly_budget=10.0)
        updated = manager.set_monthly_budget(-5.0)

        assert updated == 0.0
        assert manager.monthly_budget == 0.0

    def test_provider_registration_and_switch(self):
        """Test adding and switching named API providers."""
        primary = Mock(spec=DomainAPIClient)
        backup = Mock(spec=DomainAPIClient)
        manager = DomainRotationManager(primary)

        manager.add_api_client("backup", backup)
        switched = manager.use_api_client("backup")

        assert switched is True
        assert manager.api_client is backup
        assert manager.active_provider == "backup"


class TestDomainRotationCLI:
    """Tests for domain rotation CLI automation helpers."""

    def test_apply_env_overrides(self, monkeypatch):
        """Environment variables should override config values."""
        monkeypatch.setenv("OPSECHAT_DOMAIN_API_KEY", "pk1_env")
        monkeypatch.setenv("OPSECHAT_DOMAIN_API_SECRET", "sk1_env")
        monkeypatch.setenv("OPSECHAT_DOMAIN_MONTHLY_BUDGET", "77.5")

        merged = domain_rotation_cli.apply_env_overrides({
            "api_key": "pk1_file",
            "api_secret": "sk1_file",
            "monthly_budget": 10.0,
        })

        assert merged["api_key"] == "pk1_env"
        assert merged["api_secret"] == "sk1_env"
        assert merged["monthly_budget"] == 77.5

    def test_rotate_domain_auto_dry_run_returns_success(self):
        """Dry-run mode should not purchase and should exit cleanly."""
        manager = Mock()
        manager.get_budget_status.return_value = {
            "monthly_budget": 50.0,
            "current_spending": 1.0,
            "remaining": 49.0,
            "domains_owned": 1,
        }
        manager.find_cheap_available_domain.return_value = {
            "domain": "dryrun123.xyz",
            "price": 2.5,
            "tld": "xyz",
        }
        manager.purchase_domain_if_budget_allows = Mock()

        with patch("domain_rotation_cli.get_manager", return_value=(manager, {})):
            with patch("domain_rotation_cli._emit_result") as emit_mock:
                exit_code = domain_rotation_cli.rotate_domain_auto(
                    max_price=5.0,
                    max_attempts=10,
                    dry_run=True,
                    output_json=True,
                )

        assert exit_code == 0
        manager.purchase_domain_if_budget_allows.assert_not_called()
        emit_mock.assert_called_once()

    def test_rotate_domain_auto_budget_exhausted(self):
        """Budget exhaustion should produce a non-zero exit code."""
        manager = Mock()
        manager.get_budget_status.return_value = {
            "monthly_budget": 50.0,
            "current_spending": 50.0,
            "remaining": 0.0,
            "domains_owned": 3,
        }

        with patch("domain_rotation_cli.get_manager", return_value=(manager, {})):
            with patch("domain_rotation_cli._emit_result") as emit_mock:
                exit_code = domain_rotation_cli.rotate_domain_auto(
                    max_price=5.0,
                    max_attempts=10,
                    dry_run=False,
                )

        assert exit_code == 2
        emit_mock.assert_called_once()
