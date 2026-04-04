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
from domain_manager import DomainRotationManager, PorkbunAPIClient

client = PorkbunAPIClient(api_key="pk...", api_secret="sk...")
manager = DomainRotationManager(api_client=client, monthly_budget=10.0)

# Check for a cheap domain first
domain_info = manager.find_cheap_available_domain(max_price=5.0, max_attempts=10)
if domain_info:
    print(f"Found {domain_info['domain']} for ${domain_info['price']}")
    purchased = manager.purchase_domain_if_budget_allows(
        domain_info["domain"], domain_info["price"]
    )
    print(f"Purchased: {purchased}")
```

### CLI Commands

```bash
# Configure credentials and budget (interactive)
python3 domain_rotation_cli.py config

# Show current budget/domain status
python3 domain_rotation_cli.py status

# Search for low-cost domains
python3 domain_rotation_cli.py search

# Purchase and rotate to a new domain
python3 domain_rotation_cli.py rotate

# List domains previously purchased by the CLI
python3 domain_rotation_cli.py list
```

### Automated Rotation

Set up a cron job for weekly rotation:

```bash
# Edit crontab
crontab -e

# Add rotation job (runs every Sunday at 2 AM)
0 2 * * 0 cd /path/to/opsechat && python3 domain_rotation_cli.py rotate
```

## Budget Management

### Set Budget Limits

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager(monthly_budget=20.0)
print(manager.get_budget_status())
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
from domain_manager import DomainRotationManager

manager = DomainRotationManager()
domain = manager.generate_random_domain(tld='xyz', length=8)
print(domain)  # Example: k3s9mx2r.xyz
```

### Random Domain Generation

The system can generate random domain names:

```python
from domain_manager import DomainRotationManager

manager = DomainRotationManager()
domain = manager.generate_random_domain(length=8, tld='xyz')
# Example: "k3s9mx2r.xyz"
```

## Domain Configuration

DNS record management is handled at the registrar and is not currently automated in `domain_manager.py`.
Use your registrar dashboard/API to configure MX/A/AAAA/TXT records after purchase.

### Email Integration

Link domain to burner email system:

```python
from domain_manager import DomainRotationManager, PorkbunAPIClient
from email_system import burner_manager

client = PorkbunAPIClient("pk...", "sk...")
manager = DomainRotationManager(api_client=client)

new_domain = manager.rotate_domain()
if new_domain:
    burner_manager.update_domain(new_domain)
```

## Testing Domain Rotation

### Test Mode

There is no built-in purchase simulation mode in `domain_manager.py`.
To test safely, mock `DomainAPIClient` in unit tests (see `tests/test_domain_manager.py`) and avoid running `domain_rotation_cli.py rotate` against live credentials.

### Validation Checklist

- [ ] API credentials configured
- [ ] Budget limits set
- [ ] Safe test approach verified (mock API client)
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

manager = DomainRotationManager()
for _ in range(5):
    print(manager.generate_random_domain("xyz"))
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

Add support for additional registrars by subclassing `DomainAPIClient` and passing your client to `DomainRotationManager`.

```python
from domain_manager import DomainAPIClient, DomainRotationManager

class NamecheapAPIClient(DomainAPIClient):
    def search_domain(self, domain: str):
        return {"domain": domain, "available": False}

    def purchase_domain(self, domain: str, years: int = 1):
        return {"success": False, "domain": domain}

    def get_pricing(self, tld: str):
        return {"tld": tld}

manager = DomainRotationManager(api_client=NamecheapAPIClient("api-key"))
```

## CLI Reference

All domain rotation commands:

```bash
# Configure API credentials and budget
python3 domain_rotation_cli.py config

# View status
python3 domain_rotation_cli.py status

# Search / rotate / list
python3 domain_rotation_cli.py search
python3 domain_rotation_cli.py rotate
python3 domain_rotation_cli.py list
```

## Summary

Domain rotation is:
- ✅ **Easy**: Simple CLI commands
- ✅ **Cheap**: $1-2 per domain
- ✅ **Automated**: Set and forget with cron
- ✅ **Secure**: Budget controls and API key management
- ✅ **Flexible**: Support for multiple registrars

Start with monthly rotation and adjust based on your needs!
