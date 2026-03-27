# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems. This allows you to quickly purchase and rotate domains to enhance privacy and avoid domain-based blocking.

## Supported Registrars

Currently supported:
- **Porkbun** (Recommended default; simple API and low-cost TLDs)
- **Namecheap** (supported with XML API credentials and optional fallback mode)

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
from domain_manager import (
    domain_rotation_manager,
    PorkbunAPIClient,
    NamecheapAPIClient,
)

# Configure primary provider (Porkbun)
domain_rotation_manager.register_api_client(
    "porkbun",
    PorkbunAPIClient(api_key="pk...", api_secret="sk..."),
    set_primary=True,
)

# Optional fallback provider (Namecheap)
domain_rotation_manager.register_api_client(
    "namecheap",
    NamecheapAPIClient(
        api_key="nc_key",
        api_user="nc_user",
        client_ip="127.0.0.1",
        sandbox=True,
    ),
)
domain_rotation_manager.set_fallback_providers(["namecheap"])

# Find and purchase a cheap domain
domain_info = domain_rotation_manager.find_cheap_available_domain(max_price=5.0)
if domain_info:
    ok = domain_rotation_manager.purchase_domain_if_budget_allows(
        domain_info["domain"],
        domain_info["price"],
        provider=domain_info.get("provider"),
    )
    print("Purchased:", ok, domain_info)
else:
    print("No cheap domain found")
```

### CLI Commands

```bash
# Configure providers (Porkbun and optional Namecheap fallback)
python domain_rotation_cli.py config

# Search, rotate, list, and status
python domain_rotation_cli.py search
python domain_rotation_cli.py rotate
python domain_rotation_cli.py list
python domain_rotation_cli.py status
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

Use `domain_rotation_cli.py status` to inspect:
- Monthly budget
- Current spending
- Remaining amount
- Active domain and configured provider order

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
# Search for one available domain in cheap TLD set under max_price
domain = domain_rotation_manager.find_cheap_available_domain(
    max_price=3.00,
    max_attempts=20,
)
print(domain)
```

### Random Domain Generation

The system can generate random domain names:

```python
domain = domain_rotation_manager.generate_random_domain(length=8, tld='xyz')
# Example: "k3s9mx2r.xyz"
```

## Domain Configuration

### DNS Setup

DNS record management is registrar-specific and not yet automated in `domain_manager.py`.
After purchase, configure MX/A/TXT records in your registrar dashboard.

### Email Integration

Link domain to burner email system:

```python
from domain_manager import domain_rotation_manager
from email_system import burner_manager

new_domain = domain_rotation_manager.rotate_domain()
if new_domain:
    burner_manager.set_custom_domain(new_domain)
```

## Testing Domain Rotation

Use provider sandbox/test credentials and run search first:

```bash
python domain_rotation_cli.py status
python domain_rotation_cli.py search
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
Update budget via `python domain_rotation_cli.py config` and re-run `status`.

### Domain Not Available

**Problem:** Desired domain already taken

**Solution:**
Run `python domain_rotation_cli.py search` multiple times; it randomizes names/TLDs and checks all configured providers.

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

`DomainRotationManager` supports primary + fallback provider order.
It tries providers in this order for availability checks and records which provider was used for purchase.

### Custom Domain Patterns

Custom pattern generation is not built-in; use `generate_random_domain(...)` or wrap your own naming helper.

## CLI Reference

All supported CLI commands:

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
