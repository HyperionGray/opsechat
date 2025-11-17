"""
Email spoofing testing and detection module
For authorized security research and testing only
"""
import re
from typing import Dict, List, Optional
from datetime import datetime


class SpoofingTester:
    """
    Test email spoofing scenarios for security research
    WARNING: Use only on authorized systems with explicit permission
    """
    
    def __init__(self):
        self.test_results: List[Dict] = []
        self.test_domains: List[str] = []
    
    def add_test_domain(self, domain: str) -> None:
        """Add domain to test for spoofing vulnerabilities"""
        if domain not in self.test_domains:
            self.test_domains.append(domain)
    
    def generate_spoof_variants(self, target_domain: str) -> List[Dict]:
        """
        Generate various spoofing variants of a domain
        Returns list of variants with descriptions
        """
        variants = []
        
        # Direct spoofing (no modification)
        variants.append({
            'type': 'direct',
            'domain': target_domain,
            'email': f'admin@{target_domain}',
            'description': 'Direct domain spoofing',
            'risk_level': 'high',
            'technique': 'Exact domain match'
        })
        
        # Subdomain spoofing
        variants.append({
            'type': 'subdomain',
            'domain': f'legitimate.{target_domain}',
            'email': f'admin@legitimate.{target_domain}',
            'description': 'Subdomain spoofing',
            'risk_level': 'medium',
            'technique': 'Using subdomain to appear legitimate'
        })
        
        # Lookalike domain with typo
        typo_domain = self._generate_typo_domain(target_domain)
        variants.append({
            'type': 'typo',
            'domain': typo_domain,
            'email': f'admin@{typo_domain}',
            'description': 'Typosquatting domain',
            'risk_level': 'medium',
            'technique': 'Common typo variation'
        })
        
        # Unicode lookalike characters
        unicode_domain = self._generate_unicode_lookalike(target_domain)
        if unicode_domain != target_domain:
            variants.append({
                'type': 'unicode',
                'domain': unicode_domain,
                'email': f'admin@{unicode_domain}',
                'description': 'Unicode lookalike spoofing',
                'risk_level': 'high',
                'technique': 'Visually identical unicode characters'
            })
        
        # Homograph attack
        homograph = self._generate_homograph(target_domain)
        if homograph != target_domain:
            variants.append({
                'type': 'homograph',
                'domain': homograph,
                'email': f'admin@{homograph}',
                'description': 'Homograph attack',
                'risk_level': 'high',
                'technique': 'Different characters that look identical'
            })
        
        return variants
    
    def test_spoofing_detection(self, email: str, legitimate_domain: str) -> Dict:
        """
        Test if an email could be spoofing a legitimate domain
        Returns detection results and risk assessment
        """
        email_domain = self._extract_domain(email)
        
        result = {
            'email': email,
            'domain': email_domain,
            'legitimate_domain': legitimate_domain,
            'timestamp': datetime.now(),
            'is_suspicious': False,
            'warnings': [],
            'risk_score': 0
        }
        
        # Check for exact match (could be legitimate or spoofed)
        if email_domain == legitimate_domain:
            result['warnings'].append('Exact domain match - verify sender authenticity')
            result['risk_score'] += 2
        
        # Check for subdomain spoofing
        if email_domain.endswith(f'.{legitimate_domain}'):
            result['is_suspicious'] = True
            result['warnings'].append('Subdomain of legitimate domain - potential spoofing')
            result['risk_score'] += 5
        
        # Check for typosquatting
        if self._is_typosquat(email_domain, legitimate_domain):
            result['is_suspicious'] = True
            result['warnings'].append('Possible typosquatting - domain is very similar')
            result['risk_score'] += 7
        
        # Check for unicode lookalikes
        if self._contains_unicode_lookalikes(email_domain):
            result['is_suspicious'] = True
            result['warnings'].append('Contains unicode lookalike characters')
            result['risk_score'] += 9
        
        # Check for homograph attack
        if self._is_homograph(email_domain, legitimate_domain):
            result['is_suspicious'] = True
            result['warnings'].append('Potential homograph attack detected')
            result['risk_score'] += 10
        
        return result
    
    def _extract_domain(self, email: str) -> str:
        """Extract domain from email address"""
        if '@' in email:
            return email.split('@')[1]
        return email
    
    def _generate_typo_domain(self, domain: str) -> str:
        """Generate typosquatting variant"""
        # Common typo: swap adjacent characters
        if len(domain) > 3:
            chars = list(domain)
            # Swap first two characters of domain name
            chars[0], chars[1] = chars[1], chars[0]
            return ''.join(chars)
        return domain
    
    def _generate_unicode_lookalike(self, domain: str) -> str:
        """Generate unicode lookalike variant"""
        # Common replacements (ASCII -> Unicode lookalike)
        replacements = {
            'a': 'а',  # Cyrillic 'a' (U+0430)
            'e': 'е',  # Cyrillic 'e' (U+0435)
            'o': 'о',  # Cyrillic 'o' (U+043E)
            'p': 'р',  # Cyrillic 'p' (U+0440)
            'c': 'с',  # Cyrillic 'c' (U+0441)
        }
        
        result = domain
        for ascii_char, unicode_char in replacements.items():
            if ascii_char in result:
                result = result.replace(ascii_char, unicode_char, 1)
                break
        
        return result
    
    def _generate_homograph(self, domain: str) -> str:
        """Generate homograph attack variant"""
        # Replace 'l' with '1', 'o' with '0', etc.
        replacements = {
            'l': '1',
            'o': '0',
            'i': '1',
        }
        
        result = domain
        for orig, replacement in replacements.items():
            if orig in result:
                result = result.replace(orig, replacement, 1)
                break
        
        return result
    
    def _is_typosquat(self, test_domain: str, target_domain: str) -> bool:
        """Check if test_domain is a typosquatting variant"""
        if test_domain == target_domain:
            return False
        
        # Calculate Levenshtein distance
        distance = self._levenshtein_distance(test_domain, target_domain)
        # Consider it typosquatting if distance is 1-2 characters
        return 1 <= distance <= 2
    
    def _contains_unicode_lookalikes(self, domain: str) -> bool:
        """Check if domain contains unicode lookalike characters"""
        # Check for non-ASCII characters
        return not all(ord(char) < 128 for char in domain)
    
    def _is_homograph(self, test_domain: str, target_domain: str) -> bool:
        """Check for homograph attack"""
        # Simple check: domains look similar but have different characters
        if test_domain == target_domain:
            return False
        
        # Check if they're visually similar (same length, similar appearance)
        if len(test_domain) != len(target_domain):
            return False
        
        # Count differences
        differences = sum(1 for a, b in zip(test_domain, target_domain) if a != b)
        # Homograph if 1-2 character substitutions with visual lookalikes
        return 1 <= differences <= 2
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]


class PhishingSimulator:
    """
    Simulate phishing attacks for security awareness training
    Creates a gamified environment for learning to detect phishing
    """
    
    def __init__(self):
        self.active_simulations: Dict[str, Dict] = {}
        self.user_scores: Dict[str, Dict] = {}
    
    def enable_persist_mode(self, user_id: str) -> None:
        """
        Enable persistent phishing simulation for a user
        User will receive simulated phishing emails
        """
        self.active_simulations[user_id] = {
            'enabled': True,
            'start_time': datetime.now(),
            'emails_sent': 0,
            'detected': 0,
            'missed': 0
        }
        
        if user_id not in self.user_scores:
            self.user_scores[user_id] = {
                'total_score': 0,
                'level': 1,
                'achievements': []
            }
    
    def disable_persist_mode(self, user_id: str) -> None:
        """Disable persistent phishing simulation"""
        if user_id in self.active_simulations:
            del self.active_simulations[user_id]
    
    def create_phishing_email(self, user_id: str, template: str = 'generic') -> Dict:
        """
        Create a simulated phishing email
        Returns email dict with phishing indicators
        """
        templates = {
            'generic': {
                'from': 'security@yourbаnk.com',  # Note: Cyrillic 'а'
                'subject': 'Urgent: Account Verification Required',
                'body': 'Your account will be suspended. Click here to verify: http://verify-account.com',
                'indicators': ['unicode_lookalike', 'urgency', 'suspicious_link']
            },
            'ceo_fraud': {
                'from': 'ceo@company-mail.com',
                'subject': 'URGENT: Wire Transfer Needed',
                'body': 'Need immediate wire transfer. Please process ASAP.',
                'indicators': ['urgency', 'authority_impersonation', 'unusual_request']
            },
            'tech_support': {
                'from': 'support@micros0ft.com',  # Zero instead of 'o'
                'subject': 'Security Alert: Unusual Activity',
                'body': 'We detected unusual activity. Call our support line immediately.',
                'indicators': ['typosquat', 'urgency', 'phone_scam']
            }
        }
        
        email_template = templates.get(template, templates['generic'])
        
        email = {
            'from': email_template['from'],
            'to': f'{user_id}@internal',
            'subject': email_template['subject'],
            'body': email_template['body'],
            'is_phishing_sim': True,
            'template': template,
            'indicators': email_template['indicators'],
            'timestamp': datetime.now()
        }
        
        if user_id in self.active_simulations:
            self.active_simulations[user_id]['emails_sent'] += 1
        
        return email
    
    def record_user_action(self, user_id: str, email_id: str, action: str) -> Dict:
        """
        Record user action on phishing email
        Returns result with "got owned" warning if applicable
        """
        result = {
            'user_id': user_id,
            'action': action,
            'timestamp': datetime.now(),
            'warning': None,
            'score_change': 0
        }
        
        # Actions: 'opened', 'clicked', 'reported', 'ignored', 'deleted'
        if action in ['clicked', 'replied']:
            result['warning'] = '🚨 YOU JUST GOT OWNED! 🚨'
            result['message'] = 'You fell for a phishing simulation. This was a test!'
            result['score_change'] = -10
            
            if user_id in self.active_simulations:
                self.active_simulations[user_id]['missed'] += 1
        
        elif action in ['reported', 'deleted']:
            result['warning'] = '✅ GOOD CATCH!'
            result['message'] = 'You correctly identified this as a phishing email!'
            result['score_change'] = 20
            
            if user_id in self.active_simulations:
                self.active_simulations[user_id]['detected'] += 1
        
        # Update user score
        if user_id in self.user_scores:
            self.user_scores[user_id]['total_score'] += result['score_change']
            self._check_achievements(user_id)
        
        return result
    
    def get_user_stats(self, user_id: str) -> Dict:
        """Get phishing awareness statistics for user"""
        stats = {
            'user_id': user_id,
            'score': 0,
            'level': 1,
            'simulations': {},
            'achievements': []
        }
        
        if user_id in self.user_scores:
            stats.update(self.user_scores[user_id])
        
        if user_id in self.active_simulations:
            stats['simulations'] = self.active_simulations[user_id]
        
        return stats
    
    def _check_achievements(self, user_id: str) -> None:
        """Check and award achievements"""
        if user_id not in self.user_scores:
            return
        
        score = self.user_scores[user_id]['total_score']
        achievements = self.user_scores[user_id]['achievements']
        
        # Achievement: First Detection
        if score >= 20 and 'first_detection' not in achievements:
            achievements.append('first_detection')
        
        # Achievement: Phishing Expert (100 points)
        if score >= 100 and 'phishing_expert' not in achievements:
            achievements.append('phishing_expert')
            self.user_scores[user_id]['level'] = 2
        
        # Achievement: Security Master (500 points)
        if score >= 500 and 'security_master' not in achievements:
            achievements.append('security_master')
            self.user_scores[user_id]['level'] = 3


# Global instances
spoofing_tester = SpoofingTester()
phishing_simulator = PhishingSimulator()
