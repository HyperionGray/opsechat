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

# Configure credentials/budget once
domain_rotation_manager.configure(
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=10.0,
)

# Search for a cheap available domain
domain_info = domain_rotation_manager.find_cheap_available_domain(max_price=5.0)
print(domain_info)

# Rotate to a newly purchased domain
result = domain_rotation_manager.rotate_domain()
if result["success"]:
    print(f"Active domain: {result['active_domain']}")
    print(f"Price: ${result['price']}")
else:
    print(f"Error: {result['message']}")
```

### CLI Commands

```bash
# Preferred maintained CLI
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list

# Backward-compatible alias
python rotate-domain.py status
```

### Automated Rotation

Set up a cron job for weekly rotation:

```bash
# Edit crontab
crontab -e

# Add rotation job (runs every Sunday at 2 AM)
0 2 * * 0 cd /path/to/opsechat && python domain_rotation_cli.py rotate
```

## Budget Management

### Set Budget Limits

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=20.0,
)
print(domain_rotation_manager.get_budget_status())
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
# Search for an available domain under a specific price
domain = domain_rotation_manager.find_cheap_available_domain(
    max_price=3.00,
    max_attempts=20,
)
print(domain)
```

### Random Domain Generation

The system can generate random domain names:

```python
# Generate random domain
domain = domain_rotation_manager.generate_random_domain(length=8, tld="xyz")
# Example: "k3s9mx2r.xyz"
```

## Domain Configuration

### DNS Setup

After purchasing a domain, configure DNS in your registrar dashboard
(or via registrar-specific APIs). DNS automation is registrar-specific and
not currently handled by `domain_manager.py`.

### Email Integration

Link domain to burner email system:

```python
from domain_manager import domain_rotation_manager
from email_system import burner_manager

# Rotate domain and update burner emails
new_domain = domain_rotation_manager.rotate_domain()
if new_domain["success"]:
    # Update all burner emails to use new domain
    burner_manager.set_custom_domain(new_domain["active_domain"])
```

## Testing Domain Rotation

### Test Mode

Use mocked API clients in tests to verify behavior without purchasing domains.
See `tests/test_domain_manager.py` for examples.

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
print(domain_rotation_manager.get_budget_status())
```

### Domain Not Available

**Problem:** Desired domain already taken

**Solution:**
```python
for _ in range(5):
    candidate = domain_rotation_manager.find_cheap_available_domain(max_price=5.0, max_attempts=1)
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

Add support for additional registrars by implementing `DomainAPIClient` and
injecting it into `DomainRotationManager(api_client=...)`.

### Custom Domain Patterns

Custom naming patterns are not currently built in; generate candidate labels in
your own logic and pass them through `search_domain`.

## CLI Reference

```bash
python domain_rotation_cli.py config
python domain_rotation_cli.py status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list

# Compatibility alias:
python rotate-domain.py <same-command>
```

## Summary

Domain rotation is:
- ✅ **Easy**: Simple CLI commands
- ✅ **Cheap**: $1-2 per domain
- ✅ **Automated**: Set and forget with cron
- ✅ **Secure**: Budget controls and API key management
- ✅ **Flexible**: Support for multiple registrars

Start with monthly rotation and adjust based on your needs!
