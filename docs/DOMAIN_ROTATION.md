# Domain Rotation Guide

## Overview

OpSecChat supports automated domain rotation for burner email systems. This allows you to quickly purchase and rotate domains to enhance privacy and avoid domain-based blocking.

## Supported Registrars

Currently supported:
- **Porkbun** (Recommended - cheap .xyz, .club domains)
- **Namecheap** (Supported via XML API; requires approved client IP)
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

1. Sign up at [namecheap.com](https://www.namecheap.com)
2. Go to Profile → Tools → Namecheap API Access
3. Enable API access and whitelist your client IP
4. Save your:
   - API Key
   - Username
   - Approved Client IP

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
    print(f'Budget: ${domain_rotation_manager.budget_manager.monthly_budget}'); \
    print(f'Spent: ${domain_rotation_manager.budget_manager.get_month_spending()}'); \
    print(f'Remaining: ${domain_rotation_manager.budget_manager.get_remaining_budget()}')"

# Rotate to new domain
python -c "from domain_manager import domain_rotation_manager; \
    result = domain_rotation_manager.rotate_to_new_domain(); \
    print(result)"

# Configure Namecheap as primary provider
python -c "from domain_manager import domain_rotation_manager; \
    domain_rotation_manager.configure(api_key='nc_key', provider='namecheap', \
    username='your_username', client_ip='203.0.113.10'); \
    print(domain_rotation_manager.get_config())"
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
domain_rotation_manager.budget_manager.set_monthly_budget(20.0)

# Check spending
spending = domain_rotation_manager.budget_manager.get_month_spending()
print(f"Spent this month: ${spending}")

# Check remaining budget
remaining = domain_rotation_manager.budget_manager.get_remaining_budget()
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

After purchasing a domain, configure DNS:

```python
from domain_manager import domain_rotation_manager

# Add MX record for email
domain_rotation_manager.configure_domain_dns(
    domain="example.xyz",
    mx_records=[
        {"priority": 10, "host": "mail.example.xyz"}
    ]
)

# Add A record
domain_rotation_manager.configure_domain_dns(
    domain="example.xyz",
    a_records=[
        {"host": "@", "ip": "1.2.3.4"}
    ]
)
```

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
print(domain_rotation_manager.budget_manager.get_remaining_budget())

# Increase monthly budget
domain_rotation_manager.budget_manager.set_monthly_budget(50.0)
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
from domain_manager import domain_rotation_manager

# Register providers and switch defaults at runtime
domain_rotation_manager.configure(
    api_key="pk_live_xxx",
    secret_key="sk_live_xxx",
    provider="porkbun",
    monthly_budget=20.0
)
domain_rotation_manager.configure(
    api_key="nc_live_xxx",
    provider="namecheap",
    username="mynamecheapuser",
    client_ip="203.0.113.10"
)
domain_rotation_manager.set_primary_provider("namecheap")
```

### Custom Domain Patterns

```python
# Use specific naming pattern
pattern = "burner-{timestamp}-{random}"
domain = domain_rotation_manager.generate_domain_from_pattern(pattern, tld='xyz')
# Example: burner-20260302-k3s9.xyz
```

## CLI Reference

All domain rotation commands:

```bash
# Check available domains
python -m domain_manager search --tld xyz --max-price 2.00

# Purchase specific domain
python -m domain_manager purchase --domain example.xyz

# Rotate to new random domain
python -m domain_manager rotate

# Check budget status
python -m domain_manager budget status

# Set monthly budget
python -m domain_manager budget set --amount 20.00

# List all active domains
python -m domain_manager list

# Configure DNS
python -m domain_manager dns --domain example.xyz --mx "mail.example.xyz"
```

## Summary

Domain rotation is:
- ✅ **Easy**: Simple CLI commands
- ✅ **Cheap**: $1-2 per domain
- ✅ **Automated**: Set and forget with cron
- ✅ **Secure**: Budget controls and API key management
- ✅ **Flexible**: Support for multiple registrars

Start with monthly rotation and adjust based on your needs!
