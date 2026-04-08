# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems. This allows you to quickly purchase and rotate domains to enhance privacy and avoid domain-based blocking.

## Supported Registrars

Currently supported:
- **Porkbun** (recommended for simple low-cost setup)
- **Namecheap** (supported via XML API client)
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

# Configure a registrar (Porkbun example)
domain_rotation_manager.configure(
    registrar="porkbun",
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=20.0,
)

# Find an available cheap domain
domain_info = domain_rotation_manager.find_cheap_available_domain(max_price=3.0)
print(domain_info)

# Rotate to a newly purchased domain
new_domain = domain_rotation_manager.rotate_domain(max_price=3.0)
print(new_domain)
```

### CLI Commands

```bash
# Configure and use the registrar-aware CLI
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
0 2 * * 0 cd /path/to/opsechat && python domain_rotation_cli.py rotate
```

## Budget Management

### Set Budget Limits

```python
from domain_manager import domain_rotation_manager

# Configure budget and registrar
domain_rotation_manager.configure(
    registrar="porkbun",
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=20.0,
)

# Check spending/budget status
status = domain_rotation_manager.get_budget_status()
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
# Search for available domains with specific TLDs
domain_info = domain_rotation_manager.find_cheap_available_domain(
    tlds=["xyz", "club"],
    max_price=3.00,
    max_attempts=20,
)
print(domain_info)
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

DNS management is registrar-specific and is not yet automated through `DomainRotationManager`.
Use your registrar dashboard/API for MX/A/TXT records after purchase.

### Email Integration

Link domain to burner email system:

```python
from domain_manager import domain_rotation_manager
from email_system import burner_manager

new_domain = domain_rotation_manager.rotate_domain()
if new_domain:
    burner_manager.default_domain = new_domain
```

## Testing Domain Rotation

### Safe Validation

Use direct registrar "search only" calls before enabling purchases:

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    registrar="porkbun",
    api_key="pk1_...",
    secret_key="sk1_...",
    monthly_budget=10.0,
)

print(domain_rotation_manager.find_cheap_available_domain(max_price=2.0, max_attempts=3))
```

### Validation Checklist

- [ ] API credentials configured
- [ ] Budget limits set
- [ ] Search-only validation completed
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

status = domain_rotation_manager.get_budget_status()
print(status["remaining"])
```

### Domain Not Available

**Problem:** Desired domain already taken

**Solution:**
```python
# Try more attempts / alternate TLDs
result = domain_rotation_manager.find_cheap_available_domain(
    tlds=["xyz", "club", "online"],
    max_price=5.0,
    max_attempts=20,
)
print(result)
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

`DomainRotationManager` supports multiple configured registrars and active registrar switching:

```python
from domain_manager import (
    DomainRotationManager,
    PorkbunAPIClient,
    NamecheapAPIClient,
)

manager = DomainRotationManager(monthly_budget=25.0)
manager.add_api_client("porkbun", PorkbunAPIClient("pk1_...", "sk1_..."), set_active=True)
manager.add_api_client(
    "namecheap",
    NamecheapAPIClient(
        api_user="api_user",
        api_key="api_key",
        client_ip="127.0.0.1",
        sandbox=True,
    ),
)
manager.set_active_registrar("namecheap")
```

## CLI Reference

Use the dedicated CLI:

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
