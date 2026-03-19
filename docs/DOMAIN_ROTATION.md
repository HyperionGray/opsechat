# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems. This allows you to quickly purchase and rotate domains to enhance privacy and avoid domain-based blocking.

## Supported Registrars

Currently supported:
- **Porkbun** (Recommended - cheap .xyz, .club domains)
- Additional registrars can be added by extending `DomainAPIClient`

## Setup

### 1. Get API Credentials

#### Porkbun Setup

1. Sign up at [porkbun.com](https://porkbun.com)
2. Go to Account → API Access
3. Enable API access
4. Save your:
   - API Key
   - API Secret Key

### 2. Configure OpSecChat

Add your credentials to the email configuration:

```bash
# Via web interface
1. Access http://your-onion-url/<secret-path>/email/config
2. Scroll to "Domain Rotation Settings"
3. Enter Porkbun API Key
4. Enter Porkbun Secret Key
5. Set Monthly Budget (e.g., $10)
6. Save Configuration
```

Or via environment variables:

```bash
export PORKBUN_API_KEY="pk1_abc123..."
export PORKBUN_SECRET_KEY="sk1_xyz789..."
export DOMAIN_BUDGET="10"  # Monthly budget in USD
```

## Domain Rotation

### Manual Rotation

```python
from domain_manager import domain_rotation_manager

# Find an available cheap domain
candidate = domain_rotation_manager.find_cheap_available_domain(max_price=5.0)
print(candidate)

# Rotate to a new purchased domain
new_domain = domain_rotation_manager.rotate_domain()
if new_domain:
    print(f"New active domain: {new_domain}")
else:
    print("No domain could be purchased within budget")
```

### CLI Commands

```bash
# Configure local credentials and budget (one-time setup)
python domain_rotation_cli.py config

# Check whether a specific domain is available
python rotate-domain.py --search example.xyz

# Show current registrar pricing for a TLD
python rotate-domain.py --get-pricing xyz

# List domains currently owned in registrar account
python rotate-domain.py --list-owned

# Buy and activate a domain (interactive confirmation)
python rotate-domain.py --buy example.xyz --years 1

# Buy non-interactively (automation scripts)
python rotate-domain.py --buy example.xyz --years 1 --yes
```

### Automated Rotation

Set up a cron job for weekly rotation:

```bash
# Edit crontab
crontab -e

# Add rotation job (runs every Sunday at 2 AM)
# Use --yes for unattended automation.
0 2 * * 0 cd /path/to/opsechat && python rotate-domain.py --buy weekly-rotation-example.xyz --yes
```

## Budget Management

### Set Budget Limits

```python
from domain_manager import domain_rotation_manager

# Set monthly budget to $20
domain_rotation_manager.monthly_budget = 20.0

# Check spending
spending = domain_rotation_manager.current_spending
print(f"Spent this month: ${spending}")

# Check remaining budget
remaining = domain_rotation_manager.monthly_budget - domain_rotation_manager.current_spending
print(f"Remaining: ${remaining}")
```

### Budget Safety Features

- **Monthly limits**: Won't exceed configured budget
- **Spending tracking**: Tracks all domain purchases
- **Alert system**: Warns when approaching limit
- **Automatic denial**: Blocks purchases that exceed budget

## Domain Selection Strategy

### Cheap TLDs (Recommended)

The system prioritizes these cheap TLDs:

1. `.xyz` - Usually $1-2/year
2. `.club` - Usually $2-3/year
3. `.online` - Usually $1-2/year
4. `.site` - Usually $1-2/year
5. `.space` - Usually $1-2/year

### Search Parameters

```python
# Find a cheap available domain candidate
domain_info = domain_rotation_manager.find_cheap_available_domain(
    max_price=3.00,
    max_attempts=10
)
print(domain_info)
```

### Random Domain Generation

The system can generate random domain names:

```python
# Generate random domain
domain = domain_rotation_manager.generate_random_domain(tld='xyz', length=8)
# Example: "k3s9mx2r.xyz"
```

## Domain Configuration

### DNS Setup

DNS management should be performed in your registrar control panel after purchase.
The current `domain_manager.py` module focuses on availability checks, purchasing,
and budget tracking.

### Email Integration

Link domain to burner email system:

```python
from domain_manager import domain_rotation_manager
from email_system import burner_manager

# Rotate domain and update burner emails
new_domain = domain_rotation_manager.rotate_domain()
if new_domain:
    # Update all burner emails to use new domain
    burner_manager.update_domain(new_domain)
```

## Testing Domain Rotation

### Dry Run

Use availability checks to verify setup without purchasing:

```python
from domain_manager import domain_rotation_manager

# Verify API connectivity and pricing without purchase
candidate = domain_rotation_manager.find_cheap_available_domain(max_price=5.0, max_attempts=3)
print(f"Candidate domain: {candidate}")
```

### Validation Checklist

- [ ] API credentials configured
- [ ] Budget limits set
- [ ] Dry run availability check verified
- [ ] DNS configuration ready in registrar
- [ ] Email integration tested
- [ ] Rotation cron job set up

## Cost Optimization

### Tips for Cheap Domains

1. **Use promotional TLDs**: `.xyz`, `.club` often have $1 promos
2. **Buy for 1 year**: Don't commit to multi-year if rotating frequently
3. **Monitor pricing**: Prices change, check before purchasing
4. **Set alerts**: Get notified when budget is 80% used

### Estimated Costs

**Weekly rotation:**
- 4 domains/month × $1.50 average = $6/month

**Daily rotation (not recommended):**
- 30 domains/month × $1.50 average = $45/month

**Monthly rotation (recommended):**
- 1 domain/month × $1.50 average = $1.50/month

## Security Considerations

### API Key Security

- ✅ **DO**: Store API keys in environment variables
- ✅ **DO**: Use separate API keys for production and testing
- ✅ **DO**: Rotate API keys regularly
- ❌ **DON'T**: Commit API keys to git
- ❌ **DON'T**: Share API keys
- ❌ **DON'T**: Use root API keys if sub-keys available

### Domain Privacy

Most registrars offer WHOIS privacy:
- Enable WHOIS privacy on all domains
- Use privacy-focused registrars when possible
- Consider registering through privacy services

### Rotation Best Practices

- **Frequency**: Rotate monthly or when needed
- **Randomization**: Use random domain names
- **Diversity**: Use different TLDs
- **Monitoring**: Track which domains are active
- **Cleanup**: Delete old domains after rotation

## Troubleshooting

### API Connection Failed

**Problem:** Can't connect to domain registrar API

**Solution:**
```bash
# Test API connection
curl -X POST https://porkbun.com/api/json/v3/ping \
  -H "Content-Type: application/json" \
  -d '{"apikey":"your_api_key","secretapikey":"your_secret_key"}'
```

### Budget Exceeded

**Problem:** Purchase denied due to budget limits

**Solution:**
```python
from domain_manager import domain_rotation_manager

# Check current budget
print(domain_rotation_manager.get_budget_status())

# Increase monthly budget
domain_rotation_manager.monthly_budget = 50.0
```

### Domain Not Available

**Problem:** Desired domain already taken

**Solution:**
```python
# Generate and check alternative domains
for _ in range(5):
    candidate = domain_rotation_manager.generate_random_domain(tld="xyz", length=8)
    result = domain_rotation_manager.api_client.search_domain(candidate)
    if result.get("available"):
        print(f"{candidate}: ${result.get('price')}")
```

### DNS Not Updating

**Problem:** DNS changes not propagating

**Solution:**
```bash
# Check DNS propagation
dig @8.8.8.8 yourdomain.xyz MX

# Wait 24-48 hours for full propagation
# Use DNS checker: https://dnschecker.org
```

## Advanced Usage

### Multiple Registrars

Add support for additional registrars:

```python
from domain_manager import DomainAPIClient

class NamecheapAPIClient(DomainAPIClient):
    def __init__(self, api_key: str):
        super().__init__(api_key)

    def search_domain(self, domain: str):
        raise NotImplementedError("Implement Namecheap domain search here")

    def purchase_domain(self, domain: str, years: int = 1):
        raise NotImplementedError("Implement Namecheap domain purchase here")
```

### Custom Domain Patterns

```python
# Generate and filter random domains with your own pattern logic
candidate = domain_rotation_manager.generate_random_domain(tld="xyz", length=8)
if candidate.startswith("burn"):
    print(candidate)
```

## CLI Reference

All domain rotation commands:

```bash
# Search a domain
python rotate-domain.py --search example.xyz

# Buy domain (1-year default)
python rotate-domain.py --buy example.xyz

# Buy domain for multiple years
python rotate-domain.py --buy example.xyz --years 2

# Skip prompt for automation
python rotate-domain.py --buy example.xyz --yes

# List owned domains
python rotate-domain.py --list-owned

# Get pricing for TLD
python rotate-domain.py --get-pricing xyz
```

## Summary

Domain rotation is:
- ✅ **Easy**: Simple CLI commands
- ✅ **Cheap**: $1-2 per domain
- ✅ **Automated**: Set and forget with cron
- ✅ **Secure**: Budget controls and API key management
- ✅ **Flexible**: Support for multiple registrars

Start with monthly rotation and adjust based on your needs!
