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

# Find one available cheap domain candidate
candidate = domain_rotation_manager.find_cheap_available_domain(
    max_price=5.0,
    max_attempts=5,
)
print(candidate)

# Rotate (find + purchase + activate)
result = domain_rotation_manager.rotate_domain()
if result["success"]:
    print(f"New domain: {result['active_domain']}")
    print(f"Cost: ${result['price']}")
else:
    print(f"Error: {result['message']}")
```

### CLI Commands

```bash
# Interactive CLI commands
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
```

### Automated Rotation

Set up a cron job for weekly rotation:

```bash
# Edit crontab
crontab -e

# Add rotation job (runs every Sunday at 2 AM)
0 2 * * 0 cd /path/to/opsechat && python -c "from domain_manager import domain_rotation_manager; print(domain_rotation_manager.rotate_domain())"
```

## Persistent State Management

The CLI persists `current_spending`, `owned_domains`, and `active_domain` in
`~/.opsechat/domain_config.json`.

- Datetime fields are saved as ISO 8601 strings.
- On startup, the CLI normalizes persisted state back into runtime-safe values.
- This prevents crashes when listing domains after restarting the CLI.

Programmatic usage:

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=20.0)

# Restore persisted state
manager.load_state({
    "current_spending": "4.5",
    "owned_domains": [{
        "domain": "example.xyz",
        "price": "4.5",
        "purchased_at": "2026-01-01T00:00:00",
        "expires_at": "2027-01-01T00:00:00",
    }],
    "active_domain": "example.xyz",
})

# Export JSON-safe state for persistence
state_to_save = manager.export_state()
print(state_to_save)
```

## Budget Management

### Set Budget Limits

```python
from domain_manager import domain_rotation_manager

# Configure credentials + budget
domain_rotation_manager.configure(
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=20.0,
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
from domain_manager import domain_rotation_manager

# Search repeatedly for low-cost available candidates
for _ in range(10):
    candidate = domain_rotation_manager.find_cheap_available_domain(
        max_price=3.00,
        max_attempts=1,
    )
    if candidate:
        print(f"{candidate['domain']}: ${candidate['price']}")
```

### Random Domain Generation

The system can generate random domain names:

```python
# Generate random domain
domain = domain_rotation_manager.generate_random_domain(
    length=8,
    tld='xyz'
)
# Example: "k3s9mx2r.xyz"
```

## Domain Configuration

### DNS Setup

DNS management is handled at your registrar. `domain_manager.py` currently covers:

- availability checks
- purchases
- budget enforcement
- active-domain tracking

Use your registrar dashboard/API to set MX/A/TXT records after purchase.

### Email Integration

Link domain to burner email system:

```python
from domain_manager import domain_rotation_manager
from email_system import burner_manager

# Rotate domain and update burner email generation
result = domain_rotation_manager.rotate_domain()
if result["success"]:
    burner_manager.set_custom_domain(result["active_domain"])
```

## Testing Domain Rotation

### Test Mode

Use test mode to verify setup without spending money:

```python
from domain_manager import DomainRotationManager
from unittest.mock import Mock

# Use a mocked API client to test without live purchases.
mock_client = Mock()
mock_client.search_domain.return_value = {
    "available": True,
    "domain": "testdomain.xyz",
    "price": 2.0,
}
mock_client.purchase_domain.return_value = {"success": True}

manager = DomainRotationManager(api_client=mock_client, monthly_budget=10.0)
result = manager.rotate_domain()
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

# Increase monthly budget
domain_rotation_manager.monthly_budget = 50.0
```

### Domain Not Available

**Problem:** Desired domain already taken

**Solution:**
```python
from domain_manager import domain_rotation_manager

# Retry search several times for an available candidate
for _ in range(20):
    candidate = domain_rotation_manager.find_cheap_available_domain(max_attempts=1)
    if candidate:
        print(f"{candidate['domain']}: ${candidate['price']}")
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

# Use a different client implementation
domain_rotation_manager.set_api_client(NamecheapAPIClient(api_key))
```

### Custom Domain Generation

```python
from domain_manager import domain_rotation_manager

domain = domain_rotation_manager.generate_random_domain(tld="xyz", length=10)
print(domain)
```

## CLI Reference

All domain rotation commands:

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
