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

# Check available domains
available_domains = domain_rotation_manager.search_cheap_domains()
print(available_domains)

# Purchase a domain
result = domain_rotation_manager.rotate_to_new_domain()
if result['success']:
    print(f"New domain: {result['domain']}")
    print(f"Cost: ${result['cost']}")
else:
    print(f"Error: {result['error']}")
```

### CLI Commands

```bash
# Check available cheap domains
python -c "from domain_manager import domain_rotation_manager; \
    print(domain_rotation_manager.search_cheap_domains(tlds=['xyz', 'club', 'online']))"

# Get current budget status
python -c "from domain_manager import domain_rotation_manager; \
    print(domain_rotation_manager.get_budget_status())"

# Rotate to new domain (structured response)
python -c "from domain_manager import domain_rotation_manager; \
    result = domain_rotation_manager.rotate_to_new_domain(); \
    print(result)"
```

### Automated Rotation

Set up a cron job for weekly rotation:

```bash
# Edit crontab
crontab -e

# Add rotation job (runs every Sunday at 2 AM)
0 2 * * 0 cd /path/to/opsechat && python -c "from domain_manager import domain_rotation_manager; domain_rotation_manager.rotate_to_new_domain()"
```

## Budget Management

### Set Budget Limits

```python
from domain_manager import domain_rotation_manager

# Configure and set monthly budget to $20
domain_rotation_manager.configure(
    api_key="pk1_example",
    api_secret="sk1_example",
    monthly_budget=20.0
)

# Check spending and remaining budget
status = domain_rotation_manager.get_budget_status()
print(f"Spent this month: ${status['current_spending']}")
print(f"Remaining: ${status['remaining']}")
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
# Search for available domains with specific TLDs
domains = domain_rotation_manager.search_cheap_domains(
    tlds=['xyz', 'club'],
    max_price=3.00,
    limit=10
)
```

### Random Domain Generation

The system can generate random domain names:

```python
# Generate random domain
domain = domain_rotation_manager.generate_random_domain_name(
    length=8,
    tld='xyz'
)
# Example: "k3s9mx2r.xyz"
```

## Domain Configuration

### DNS Setup

DNS management is registrar-specific and not yet implemented in `DomainRotationManager`.
Use your registrar dashboard or provider API directly for MX/A records after purchase.

### Email Integration

Link domain to burner email system:

```python
from domain_manager import domain_rotation_manager
from email_system import burner_manager

# Rotate domain and update burner email default domain
result = domain_rotation_manager.rotate_to_new_domain()
if result['success']:
    burner_manager.set_custom_domain(result['domain'])
```

## Testing Domain Rotation

### Test Mode

Use test mode to verify setup without spending money:

```python
from domain_manager import domain_rotation_manager

# Enable test mode
domain_rotation_manager.set_test_mode(True)

# This will simulate rotation without actual purchase
result = domain_rotation_manager.rotate_to_new_domain()
print(f"Test result: {result}")
```

### Validation Checklist

- [ ] API credentials configured
- [ ] Budget limits set
- [ ] Test mode verified
- [ ] DNS configuration working
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
print(domain_rotation_manager.get_budget_status()["remaining"])

# Increase monthly budget by reconfiguring
domain_rotation_manager.configure(
    api_key="pk1_example",
    api_secret="sk1_example",
    monthly_budget=50.0
)
```

### Domain Not Available

**Problem:** Desired domain already taken

**Solution:**
```python
# Generate alternative domains
alternatives = domain_rotation_manager.search_cheap_domains(limit=20)
for domain in alternatives:
    print(f"{domain['name']}: ${domain['price']}")
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
        # Implementation here
        return {"domain": domain, "available": True, "price": 2.50}
    
    def purchase_domain(self, domain: str, years: int = 1):
        # Implementation here
        return {"success": True, "domain": domain}

    def get_pricing(self, tld: str):
        return {"tld": tld, "registration": 2.50}

# Register new client
domain_rotation_manager.add_api_client('namecheap', NamecheapAPIClient(api_key))
```

### Provider Fallback Rotation

```python
from domain_manager import domain_rotation_manager

# Primary provider first, then automatic fallback
domain_rotation_manager.add_api_client("namecheap", NamecheapAPIClient("api-key"))
domain_rotation_manager.set_primary_provider("porkbun")
result = domain_rotation_manager.rotate_to_new_domain(max_price=3.00)
print(result)
```

## CLI Reference

Use the dedicated CLI script:

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

## Summary

Domain rotation is:
- ✅ **Easy**: Simple CLI commands
- ✅ **Cheap**: $1-2 per domain
- ✅ **Automated**: Set and forget with cron
- ✅ **Secure**: Budget controls and API key management
- ✅ **Flexible**: Support for multiple registrars

Start with monthly rotation and adjust based on your needs!
