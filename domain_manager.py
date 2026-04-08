"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DomainAPIClient:
    """
    Base class for domain registrar API clients
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def search_domain(self, domain: str) -> Dict:
        """Search if domain is available"""
        raise NotImplementedError
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """Purchase domain"""
        raise NotImplementedError
    
    def get_pricing(self, tld: str) -> Dict:
        """Get pricing for TLD"""
        raise NotImplementedError


class PorkbunAPIClient(DomainAPIClient):
    """
    Porkbun API client for domain management
    https://porkbun.com/api/json/v3/documentation
    """
    
    BASE_URL = "https://porkbun.com/api/json/v3"
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()
    
    def _make_request(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make API request"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        payload = {
            "apikey": self.api_key,
            "secretapikey": self.api_secret
        }
        
        if data:
            payload.update(data)
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Porkbun API request failed: {e}")
            return {"status": "ERROR", "message": str(e)}
    
    def search_domain(self, domain: str) -> Dict:
        """Check if domain is available"""
        result = self._make_request("domain/check", {"domain": domain})
        
        return {
            "domain": domain,
            "available": result.get("status") == "SUCCESS" and result.get("isAvailable", False),
            "price": result.get("price"),
            "currency": result.get("currency", "USD")
        }
    
    def purchase_domain(self, domain: str, years: int = 1) -> Dict:
        """
        Purchase domain
        Note: This actually purchases the domain and charges your account
        """
        result = self._make_request("domain/create", {
            "domain": domain,
            "years": years
        })
        
        return {
            "success": result.get("status") == "SUCCESS",
            "domain": domain,
            "message": result.get("message", ""),
            "order_id": result.get("orderId")
        }
    
    def get_pricing(self, tld: str = "com") -> Dict:
        """Get pricing for TLD"""
        result = self._make_request("pricing/get", {"tld": tld})
        
        if result.get("status") == "SUCCESS":
            pricing = result.get("pricing", {})
            return {
                "tld": tld,
                "registration": pricing.get("registration"),
                "renewal": pricing.get("renewal"),
                "transfer": pricing.get("transfer"),
                "currency": "USD"
            }
        
        return {}
    
    def list_domains(self) -> List[str]:
        """List owned domains"""
        result = self._make_request("domain/listAll")
        
        if result.get("status") == "SUCCESS":
            domains = result.get("domains", [])
            return [d.get("domain") for d in domains if d.get("domain")]
        
        return []


class DomainRotationManager:
    """
    Manage domain rotation for burner emails
    Automatically purchase cheap domains and rotate them
    """
    
    def __init__(self, api_client: Optional[DomainAPIClient] = None, 
                 monthly_budget: float = 50.0):
        self.api_client = api_client
        self.api_provider = self._infer_provider(api_client) if api_client else None
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
    
    @staticmethod
    def _infer_provider(api_client: DomainAPIClient) -> str:
        """Infer provider name from API client class name."""
        class_name = api_client.__class__.__name__.lower()
        return class_name.replace("apiclient", "") or "custom"

    @staticmethod
    def _parse_price(price: Any, default: float = 999.0) -> float:
        """Normalize registrar price values to float."""
        if isinstance(price, (int, float)):
            return float(price)
        if isinstance(price, str):
            normalized = (
                price.replace("$", "")
                .replace("€", "")
                .replace(",", "")
                .strip()
            )
            try:
                return float(normalized)
            except ValueError:
                return default
        return default

    @staticmethod
    def _serialize_domain_record(record: Dict) -> Dict:
        """Convert in-memory domain record to JSON-serializable structure."""
        serialized = dict(record)
        for field in ("purchased_at", "expires_at"):
            value = serialized.get(field)
            if isinstance(value, datetime):
                serialized[field] = value.isoformat()
        return serialized

    @staticmethod
    def _deserialize_domain_record(record: Dict) -> Dict:
        """Convert JSON-stored domain record to in-memory structure."""
        deserialized = dict(record)
        for field in ("purchased_at", "expires_at"):
            value = deserialized.get(field)
            if isinstance(value, str):
                try:
                    deserialized[field] = datetime.fromisoformat(value)
                except ValueError:
                    # Keep raw value when legacy/invalid data is encountered.
                    pass
        return deserialized

    def set_api_client(self, api_client: DomainAPIClient, provider: Optional[str] = None):
        """Set the domain API client"""
        self.api_client = api_client
        self.api_provider = (provider or self._infer_provider(api_client)).lower()

    def configure(self, api_key: str, secret_key: Optional[str] = None,
                  monthly_budget: Optional[float] = None,
                  provider: str = "porkbun") -> Dict:
        """
        Configure domain manager from UI/API style inputs.
        """
        normalized_provider = provider.lower().strip()
        if normalized_provider != "porkbun":
            raise ValueError(f"Unsupported provider: {provider}")

        if not api_key or not secret_key:
            raise ValueError("Both api_key and secret_key are required")

        if monthly_budget is not None:
            self.monthly_budget = float(monthly_budget)

        self.set_api_client(PorkbunAPIClient(api_key, secret_key), provider=normalized_provider)
        return self.get_config()

    def get_config(self) -> Dict:
        """Return non-sensitive domain configuration details."""
        return {
            "configured": self.api_client is not None,
            "provider": self.api_provider,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
        }
    
    def generate_random_domain(self, tld: str = "xyz", length: int = 8) -> str:
        """
        Generate random domain name
        Uses cheap TLDs like .xyz, .club, .online
        """
        chars = string.ascii_lowercase + string.digits
        random_name = ''.join(random.choice(chars) for _ in range(length))
        return f"{random_name}.{tld}"
    
    def find_cheap_available_domain(self, max_price: float = 5.0, 
                                   max_attempts: int = 10) -> Optional[Dict]:
        """
        Find a cheap available domain
        Returns domain info or None
        """
        if not self.api_client:
            logger.error("No API client configured")
            return None
        
        # Try cheap TLDs
        cheap_tlds = ["xyz", "club", "online", "site", "website"]
        
        for attempt in range(max_attempts):
            tld = random.choice(cheap_tlds)
            domain = self.generate_random_domain(tld)
            
            result = self.api_client.search_domain(domain)
            
            if result.get("available"):
                price = self._parse_price(result.get("price"), default=999.0)
                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld
                    }
        
        return None

    def search_cheap_domains(self, max_price: float = 5.0, limit: int = 5,
                             max_attempts_per_result: int = 5) -> List[Dict]:
        """
        Find multiple available cheap domains.
        """
        results: List[Dict] = []
        seen = set()
        total_attempts = max(limit * max_attempts_per_result, limit)

        for _ in range(total_attempts):
            if len(results) >= limit:
                break
            domain_info = self.find_cheap_available_domain(
                max_price=max_price,
                max_attempts=1,
            )
            if domain_info and domain_info["domain"] not in seen:
                seen.add(domain_info["domain"])
                results.append(domain_info)
        return results
    
    def purchase_domain_if_budget_allows(self, domain: str, price: float) -> bool:
        """
        Purchase domain if within budget
        Returns True on success
        """
        if not self.api_client:
            logger.error("No API client configured")
            return False
        
        # Check budget
        if self.current_spending + price > self.monthly_budget:
            logger.warning(f"Budget exceeded. Current: ${self.current_spending}, "
                          f"Requested: ${price}, Budget: ${self.monthly_budget}")
            return False
        
        # Attempt purchase
        result = self.api_client.purchase_domain(domain, years=1)
        
        if result.get("success"):
            self.current_spending += price
            self.owned_domains.append({
                "domain": domain,
                "price": price,
                "purchased_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=365)
            })
            
            # Set as active if no active domain
            if not self.active_domain:
                self.active_domain = domain
            
            logger.info(f"Successfully purchased domain: {domain} for ${price}")
            return True
        else:
            logger.error(f"Failed to purchase domain: {result.get('message')}")
            return False
    
    def rotate_domain(self) -> Optional[str]:
        """
        Rotate to a new domain
        Finds and purchases a new cheap domain
        """
        # Find cheap domain
        domain_info = self.find_cheap_available_domain()
        
        if not domain_info:
            logger.error("Could not find available cheap domain")
            return None
        
        # Purchase domain
        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"], 
            domain_info["price"]
        )
        
        if success:
            self.active_domain = domain_info["domain"]
            return self.active_domain
        
        return None

    def rotate_domain_with_result(self) -> Dict:
        """
        Rotate domain and return API-friendly structured result.
        """
        domain = self.rotate_domain()
        if domain:
            return {
                "success": True,
                "domain": domain,
                "budget_status": self.get_budget_status(),
            }
        return {
            "success": False,
            "error": "Could not rotate to a new domain within current constraints",
            "budget_status": self.get_budget_status(),
        }
    
    def get_active_domain(self) -> Optional[str]:
        """Get currently active domain"""
        return self.active_domain
    
    def get_owned_domains(self) -> List[Dict]:
        """Get list of owned domains"""
        return self.owned_domains
    
    def get_budget_status(self) -> Dict:
        """Get budget information"""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining": self.monthly_budget - self.current_spending,
            "domains_owned": len(self.owned_domains)
        }

    def export_state(self) -> Dict:
        """Export manager state as JSON-serializable data."""
        return {
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "active_domain": self.active_domain,
            "owned_domains": [
                self._serialize_domain_record(record) for record in self.owned_domains
            ],
        }

    def import_state(self, state: Dict):
        """Import manager state from persisted data."""
        if not isinstance(state, dict):
            return

        if "monthly_budget" in state:
            self.monthly_budget = float(state["monthly_budget"])
        if "current_spending" in state:
            self.current_spending = float(state["current_spending"])
        self.active_domain = state.get("active_domain")

        owned_domains = state.get("owned_domains", [])
        if isinstance(owned_domains, list):
            self.owned_domains = [
                self._deserialize_domain_record(record)
                for record in owned_domains
                if isinstance(record, dict)
            ]


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
