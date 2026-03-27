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

This document reflects the currently implemented interfaces in:
- `domain_manager.py`
- `domain_rotation_cli.py`

Some older examples in prior revisions referenced experimental helpers that are
not part of the current runtime API.

### Manual Rotation (Python API)

```python
from domain_manager import PorkbunAPIClient, DomainRotationManager

client = PorkbunAPIClient("your_api_key", "your_secret_key")
manager = DomainRotationManager(api_client=client, monthly_budget=20.0)

candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=5)
if candidate:
    ok = manager.purchase_domain_if_budget_allows(candidate["domain"], candidate["price"])
    if ok:
        print("Purchased:", manager.get_active_domain())
        print("Budget:", manager.get_budget_status())
```

### CLI Commands

```bash
# Configure credentials and budget
python domain_rotation_cli.py config

# Inspect current budget/domain state
python domain_rotation_cli.py status

# Search for cheap available domains
python domain_rotation_cli.py search

# Purchase and rotate to a newly found domain
python domain_rotation_cli.py rotate

# List locally tracked owned domains
python domain_rotation_cli.py list
```

### Automated Rotation

Set up a cron job for weekly status checks and optional rotation:

```bash
# Edit crontab
crontab -e

# Example status check (runs every Sunday at 2 AM)
0 2 * * 0 cd /path/to/opsechat && python domain_rotation_cli.py status
```

Note: `rotate` requires interactive confirmation (`yes`). For unattended
automation, use the Python API directly with explicit purchase logic.

## Budget Management

### Set Budget Limits

Set budget in the CLI config flow:

```bash
python domain_rotation_cli.py config
```

At runtime, inspect budget:

```bash
python domain_rotation_cli.py status
```

Programmatically:

```python
from domain_manager import DomainRotationManager
manager = DomainRotationManager(monthly_budget=20.0)
print(manager.get_budget_status())
```

### Budget Safety Features

- **Monthly limits**: Won't exceed configured budget
- **Spending tracking**: Tracks all domain purchases
- **Automatic denial**: Blocks purchases that exceed budget
- **Automatic monthly reset**: Spending is reset when entering a newer
  calendar month (tracked by `YYYY-MM` period)
- **Durable CLI state**: Domain ownership metadata and timestamps are persisted
  as JSON and reloaded safely

## Domain Selection Strategy

### Cheap TLDs (Recommended)

The system prioritizes these cheap TLDs:

1. `.xyz` - Usually $1-2/year
2. `.club` - Usually $2-3/year
3. `.online` - Usually $1-2/year
4. `.site` - Usually $1-2/year
5. `.website` - Usually $1-2/year

### Search Parameters

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(api_client=...)
candidate = manager.find_cheap_available_domain(max_price=3.00, max_attempts=10)
print(candidate)
```

### Random Domain Generation

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager()
domain = manager.generate_random_domain(tld="xyz", length=8)
print(domain)  # Example: "k3s9mx2r.xyz"
```

## Domain Configuration

### DNS Setup

DNS management helpers are not implemented in `domain_manager.py`.
Configure DNS through your registrar dashboard/API after purchase.

### Email Integration

The active domain can be read via CLI status and then configured in email
settings:

```bash
python domain_rotation_cli.py status
```

## Testing Domain Rotation

### Test Mode

Use mocked tests in `tests/test_domain_manager.py` and
`tests/test_domain_rotation_cli.py` to verify behavior without live purchases.

### Validation Checklist

- [ ] API credentials configured
- [ ] Budget limits set
- [ ] Mocked tests verified (`tests/test_domain_manager.py`, `tests/test_domain_rotation_cli.py`)
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
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=50.0)
print(manager.get_budget_status()["remaining"])
```

### Domain Not Available

**Problem:** Desired domain already taken

**Solution:**
```python
from domain_manager import DomainRotationManager
manager = DomainRotationManager(api_client=...)
for _ in range(5):
    print(manager.find_cheap_available_domain(max_price=5.0, max_attempts=1))
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
        pass
    
    def purchase_domain(self, domain: str, years: int = 1):
        # Implementation here
        pass

# Use the custom client with DomainRotationManager
manager = DomainRotationManager(api_client=NamecheapAPIClient(api_key))
```

### Custom Domain Names

`DomainRotationManager` supports custom random-name generation inputs:

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager()
print(manager.generate_random_domain(tld="club", length=10))
```

## CLI Reference

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
