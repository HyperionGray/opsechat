# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems. This allows you to quickly purchase and rotate domains to enhance privacy and avoid domain-based blocking.

## Supported Registrars

Currently supported:
- **Porkbun** (recommended default - cheap .xyz, .club domains)
- **Namecheap** (supported as primary or fallback registrar)
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

#### Namecheap Setup

1. Sign up at [namecheap.com](https://namecheap.com)
2. Enable API access in your Namecheap account
3. Allowlist your public client IP for API requests
4. Save your:
   - API User
   - API Key
   - Optional Username (defaults to API User)

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
export DOMAIN_REGISTRAR="porkbun"  # or "namecheap" or "both"
export DOMAIN_BUDGET="10"  # Monthly budget in USD

# Optional Namecheap credentials
export NAMECHEAP_API_USER="your-api-user"
export NAMECHEAP_API_KEY="your-api-key"
export NAMECHEAP_USERNAME="your-username"  # optional
export NAMECHEAP_CLIENT_IP="203.0.113.10"  # must be allowlisted in Namecheap
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
    status = domain_rotation_manager.get_budget_status(); \
    print(f'Budget: ${status[\"monthly_budget\"]}'); \
    print(f'Spent: ${status[\"current_spending\"]}'); \
    print(f'Remaining: ${status[\"remaining\"]}')"

# Rotate to new domain
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

# Set monthly budget to $20
domain_rotation_manager.set_monthly_budget(20.0)

# Check spending/remaining
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
domain = domain_rotation_manager.generate_domain_name(
    length=8,
    tld='xyz'
)
# Example: "k3s9mx2r.xyz"
```

## Registrar Strategy

You can run with one registrar or fail over automatically:

```python
from domain_manager import domain_rotation_manager

domain_rotation_manager.configure(
    api_key="porkbun_api_key",
    secret_key="porkbun_secret",
    registrar="both",                  # primary porkbun + namecheap fallback
    namecheap_api_user="nc_user",
    namecheap_api_key="nc_key",
    namecheap_client_ip="203.0.113.10",
    monthly_budget=25.0,
)
```

When a purchase succeeds, metadata includes the registrar used.

### Email Integration

Link domain to burner email system:

```python
from domain_manager import domain_rotation_manager
from email_system import burner_manager

# Rotate domain and update burner emails
new_domain = domain_rotation_manager.rotate_to_new_domain()
if new_domain['success']:
    # Update all burner emails to use new domain
    burner_manager.update_domain(new_domain['domain'])
```

## Testing Domain Rotation

### Test Safely

Use unit tests and dry checks first:

```bash
python -m pytest tests/test_domain_manager.py -q
```

### Validation Checklist

- [ ] API credentials configured
- [ ] Budget limits set
- [ ] Test mode verified
- [ ] Registrar credentials configured (Porkbun and/or Namecheap)
- [ ] Namecheap client IP allowlisted (if using Namecheap)
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

For Namecheap, confirm:
- API access is enabled in your account
- `ClientIp` exactly matches an allowlisted public IP
- `ApiUser` and `ApiKey` are valid

### Budget Exceeded

**Problem:** Purchase denied due to budget limits

**Solution:**
```python
from domain_manager import domain_rotation_manager

# Check current budget
print(domain_rotation_manager.get_budget_status()["remaining"])

# Increase monthly budget
domain_rotation_manager.set_monthly_budget(50.0)
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

### Additional Registrars

Additional registrars can be added by subclassing `DomainAPIClient` and
registering them with `DomainRotationManager.add_api_client(...)`.

### Custom Search Lists

```python
domains = domain_rotation_manager.search_cheap_domains(
    tlds=["xyz", "club", "online"],
    max_price=3.00,
    limit=5,
)
print(domains)
```

## CLI Reference

Use `domain_rotation_cli.py`:

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
