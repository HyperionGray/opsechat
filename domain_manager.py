"""
Domain management and API integration
Supports automated domain purchasing for burner email rotation
"""
import requests
import random
import string
import logging
import time
from typing import Dict, List, Optional
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
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.5,
        timeout: int = 30,
    ):
        super().__init__(api_key, api_secret)
        self.session = requests.Session()
        self.max_retries = max(1, int(max_retries))
        self.backoff_base_seconds = max(0.0, float(backoff_base_seconds))
        self.timeout = max(1, int(timeout))

    @staticmethod
    def _is_retryable_status(status_code: Optional[int]) -> bool:
        """Retry on rate limits and transient upstream failures."""
        if not isinstance(status_code, int):
            return False
        return status_code == 429 or 500 <= status_code < 600

    def _sleep_before_retry(self, attempt_index: int):
        """Apply exponential backoff between retry attempts."""
        delay = self.backoff_base_seconds * (2 ** attempt_index)
        if delay > 0:
            time.sleep(delay)
    
    def _make_request(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make API request"""
        url = f"{self.BASE_URL}/{endpoint}"
        
        payload = {
            "apikey": self.api_key,
            "secretapikey": self.api_secret
        }
        
        if data:
            payload.update(data)
        
        last_error = "Unknown API error"
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(url, json=payload, timeout=self.timeout)
                raw_status = getattr(response, "status_code", 200)
                status_code = raw_status if isinstance(raw_status, int) else 200

                if self._is_retryable_status(status_code):
                    raise requests.HTTPError(
                        f"Porkbun API returned retryable status {status_code}",
                        response=response
                    )

                response.raise_for_status()
                result = response.json()

                # Some API-level errors are transient. Retry before returning.
                if result.get("status") == "ERROR" and attempt < self.max_retries - 1:
                    logger.warning(
                        "Porkbun API error on %s (attempt %s/%s): %s",
                        endpoint,
                        attempt + 1,
                        self.max_retries,
                        result.get("message", "Unknown API error")
                    )
                    self._sleep_before_retry(attempt)
                    continue

                return result
            except requests.HTTPError as e:
                status_code = getattr(getattr(e, "response", None), "status_code", None)
                last_error = str(e)
                if self._is_retryable_status(status_code) and attempt < self.max_retries - 1:
                    logger.warning(
                        "Retryable HTTP error on %s (attempt %s/%s): %s",
                        endpoint,
                        attempt + 1,
                        self.max_retries,
                        e
                    )
                    self._sleep_before_retry(attempt)
                    continue
                break
            except (requests.ConnectionError, requests.Timeout) as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    logger.warning(
                        "Network error on %s (attempt %s/%s): %s",
                        endpoint,
                        attempt + 1,
                        self.max_retries,
                        e
                    )
                    self._sleep_before_retry(attempt)
                    continue
                break
            except ValueError as e:
                # JSON parsing failed; retry in case of transient upstream issues.
                last_error = f"Invalid JSON response: {e}"
                if attempt < self.max_retries - 1:
                    logger.warning(
                        "JSON parse error on %s (attempt %s/%s): %s",
                        endpoint,
                        attempt + 1,
                        self.max_retries,
                        e
                    )
                    self._sleep_before_retry(attempt)
                    continue
                break
            except Exception as e:
                last_error = str(e)
                break

        logger.error("Porkbun API request failed after retries: %s", last_error)
        return {"status": "ERROR", "message": last_error}
    
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
        self.monthly_budget = monthly_budget
        self.current_spending = 0.0
        self.owned_domains: List[Dict] = []
        self.active_domain: Optional[str] = None
        self.registrar: Optional[str] = None
        self.api_key_masked: Optional[str] = None
        self.retry_attempts = 3
        self.backoff_base_seconds = 0.5
    
    def set_api_client(self, api_client: DomainAPIClient):
        """Set the domain API client"""
        self.api_client = api_client

    @staticmethod
    def _mask_secret(secret: str) -> str:
        """Mask credentials while still allowing operators to identify keys."""
        if not secret:
            return ""
        if len(secret) <= 4:
            return "*" * len(secret)
        return f"{'*' * (len(secret) - 4)}{secret[-4:]}"

    @staticmethod
    def _normalize_price(price_value) -> Optional[float]:
        """Normalize API price fields into a float value."""
        if price_value is None:
            return None
        if isinstance(price_value, (int, float)):
            return float(price_value)
        if isinstance(price_value, str):
            cleaned = (
                price_value.strip()
                .replace("$", "")
                .replace("€", "")
                .replace("£", "")
                .replace(",", "")
            )
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def configure(
        self,
        api_key: str,
        secret_key: str,
        monthly_budget: float = 10.0,
        retry_attempts: int = 3,
        backoff_base_seconds: float = 0.5,
    ) -> Dict:
        """Configure registrar API credentials and retry behavior."""
        api_key = (api_key or "").strip()
        secret_key = (secret_key or "").strip()
        if not api_key or not secret_key:
            raise ValueError("Both api_key and secret_key are required")

        budget_value = float(monthly_budget)
        if budget_value <= 0:
            raise ValueError("monthly_budget must be greater than 0")

        retry_value = max(1, int(retry_attempts))
        backoff_value = max(0.0, float(backoff_base_seconds))

        self.api_client = PorkbunAPIClient(
            api_key=api_key,
            api_secret=secret_key,
            max_retries=retry_value,
            backoff_base_seconds=backoff_value,
        )
        self.monthly_budget = budget_value
        self.registrar = "porkbun"
        self.api_key_masked = self._mask_secret(api_key)
        self.retry_attempts = retry_value
        self.backoff_base_seconds = backoff_value

        return self.get_config()

    def get_config(self) -> Dict:
        """Return current domain rotation configuration metadata."""
        return {
            "configured": self.api_client is not None,
            "registrar": self.registrar,
            "api_key_masked": self.api_key_masked,
            "monthly_budget": self.monthly_budget,
            "current_spending": self.current_spending,
            "remaining_budget": self.monthly_budget - self.current_spending,
            "active_domain": self.active_domain,
            "domains_owned": len(self.owned_domains),
            "retry_attempts": self.retry_attempts,
            "backoff_base_seconds": self.backoff_base_seconds,
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
                price = self._normalize_price(result.get("price"))

                if price is None:
                    logger.warning("Skipping domain %s: missing/invalid price", domain)
                    continue

                if price <= max_price:
                    return {
                        "domain": domain,
                        "price": price,
                        "tld": tld,
                        "currency": result.get("currency", "USD"),
                    }
        
        return None

    def search_cheap_domains(
        self,
        tlds: Optional[List[str]] = None,
        max_price: float = 5.0,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Search for multiple available low-cost domains without purchasing them.
        """
        if not self.api_client:
            logger.error("No API client configured")
            return []

        if limit <= 0:
            return []

        candidate_tlds = tlds or ["xyz", "club", "online", "site", "website"]
        if not candidate_tlds:
            return []
        seen_domains = set()
        matches: List[Dict] = []
        max_attempts = max(limit * 6, 10)

        for _ in range(max_attempts):
            if len(matches) >= limit:
                break

            tld = random.choice(candidate_tlds)
            domain = self.generate_random_domain(tld)
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            result = self.api_client.search_domain(domain)
            if not result.get("available"):
                continue

            price = self._normalize_price(result.get("price"))
            if price is None or price > max_price:
                continue

            matches.append({
                "domain": domain,
                "price": price,
                "tld": tld,
                "currency": result.get("currency", "USD"),
            })

        return matches
    
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
        result = self.rotate_to_new_domain()
        if result.get("success"):
            return result.get("domain")
        return None

    def rotate_to_new_domain(self, max_price: float = 5.0) -> Dict:
        """
        Rotate to a new domain and return structured result metadata.
        """
        domain_info = self.find_cheap_available_domain(max_price=max_price)

        if not domain_info:
            logger.error("Could not find available cheap domain")
            return {
                "success": False,
                "domain": None,
                "price": None,
                "error": "Could not find available cheap domain within budget",
            }

        success = self.purchase_domain_if_budget_allows(
            domain_info["domain"],
            domain_info["price"]
        )

        if not success:
            return {
                "success": False,
                "domain": domain_info["domain"],
                "price": domain_info["price"],
                "error": "Purchase failed or budget exceeded",
            }

        self.active_domain = domain_info["domain"]
        return {
            "success": True,
            "domain": self.active_domain,
            "price": domain_info["price"],
            "currency": domain_info.get("currency", "USD"),
            "remaining_budget": self.monthly_budget - self.current_spending,
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


# Global domain rotation manager
domain_rotation_manager = DomainRotationManager()
