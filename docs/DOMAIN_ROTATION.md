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

### Manual Rotation (Python API)

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient

manager = DomainRotationManager(
    api_client=PorkbunAPIClient("YOUR_API_KEY", "YOUR_SECRET_KEY"),
    monthly_budget=10.0,
)

# Find a cheap available candidate (if any)
candidate = manager.find_cheap_available_domain(max_price=5.0)
print(candidate)

# Purchase and activate a new domain in one step
new_domain = manager.rotate_domain()
if new_domain:
    print(f"Active domain: {new_domain}")
else:
    print("Rotation failed")
```

### CLI Commands

Use `domain_rotation_cli.py` for all routine operations:

```bash
# Configure credentials and budget
python domain_rotation_cli.py config

# Search for cheap available domains (does not purchase)
python domain_rotation_cli.py search

# Purchase and rotate to a new domain
python domain_rotation_cli.py rotate

# Show active domain and budget status
python domain_rotation_cli.py status

# List locally tracked purchased domains
python domain_rotation_cli.py list

# Manually switch active domain to an owned, non-expired domain
python domain_rotation_cli.py activate yourdomain.xyz

# Deactivate a domain (promotes fallback active domain when available)
python domain_rotation_cli.py deactivate yourdomain.xyz

# Remove expired domains from persisted local state
python domain_rotation_cli.py cleanup
```

### Local State Persistence

The CLI stores local state in `~/.opsechat/domain_config.json`:

- `current_spending`
- `owned_domains` (including purchase/expiry timestamps)
- `active_domain`

State is serialized using JSON-safe ISO8601 timestamps and automatically restored on next run.

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

Budget is configured when creating the manager or via CLI config:

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=20.0)
status = manager.get_budget_status()
print(status)
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
candidate = manager.find_cheap_available_domain(max_price=3.00, max_attempts=10)
print(candidate)
```

### Random Domain Generation

The system can generate random domain names:

```python
# Generate random domain
domain = manager.generate_random_domain(tld='xyz', length=8)
# Example: "k3s9mx2r.xyz"
```

## Domain Configuration

### DNS Setup

DNS helper methods are not implemented in `DomainRotationManager`.
Configure DNS records directly with your registrar tooling/API after purchase.

### Email Integration

Use `manager.get_active_domain()` (or CLI `status`) to retrieve the active domain,
then feed it to your burner email flow.

## Testing Domain Rotation

### Test Mode

A dedicated "test mode" flag is not implemented.
For non-billing validation, mock `DomainAPIClient` in tests (see `tests/test_domain_manager.py`).

### Validation Checklist

- [ ] API credentials configured
- [ ] Budget limits set
- [ ] Non-billing validation completed with mocked DomainAPIClient tests
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
status = manager.get_budget_status()
print(status["remaining"])
manager.monthly_budget = 50.0
```

### Domain Not Available

**Problem:** Desired domain already taken

**Solution:**
```python
for _ in range(5):
    candidate = manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
    print(candidate)
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
```
## CLI Reference

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py status
python domain_rotation_cli.py list
python domain_rotation_cli.py activate <domain>
python domain_rotation_cli.py deactivate <domain>
python domain_rotation_cli.py cleanup
```

## Summary

Domain rotation is:
- ✅ **Easy**: Simple CLI commands
- ✅ **Cheap**: $1-2 per domain
- ✅ **Automated**: Set and forget with cron
- ✅ **Secure**: Budget controls and API key management
- ✅ **Flexible**: Support for multiple registrars

Start with monthly rotation and adjust based on your needs!
