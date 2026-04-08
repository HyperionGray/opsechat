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

Use the built-in CLI wrapper:

```bash
bin/rotate-domain status
bin/rotate-domain search
bin/rotate-domain rotate
bin/rotate-domain list
```

### CLI Commands

```bash
# Configure Porkbun API key/secret and monthly budget
bin/rotate-domain config

# Check budget and active domain status
bin/rotate-domain status

# Search for cheap available domains
bin/rotate-domain search

# Rotate to a new purchased domain (with confirmation)
bin/rotate-domain rotate

# List owned domains and expiration dates
bin/rotate-domain list
```

### Automated Rotation

Set up a cron job for weekly rotation:

```bash
# Edit crontab
crontab -e

# Add rotation job (runs every Sunday at 2 AM)
0 2 * * 0 cd /path/to/opsechat && bin/rotate-domain rotate
```

## Budget Management

### Set Budget Limits

Set budget during configuration:

```bash
bin/rotate-domain config
```

Then review spending and remaining budget:

```bash
bin/rotate-domain status
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
5. `.website` - Usually $1-2/year

### Search Parameters

Current CLI behavior searches multiple attempts using low-cost TLDs:

- `.xyz`
- `.club`
- `.online`
- `.site`
- `.website`

The tool filters for domains at or below a low-cost threshold and reports candidates.

### Random Domain Generation

The rotation manager generates random domain labels automatically (for example: `k3s9mx2r.xyz`) while searching.

## Domain Configuration

### DNS Setup

After purchasing a domain, configure DNS in your registrar account (for example, MX and A records) so email services can route properly.

### Email Integration

After rotating domains:

1. Run `bin/rotate-domain status` to see the active domain.
2. Update email settings/services to use addresses like `user@active-domain.tld`.
3. Keep old domains valid until existing burner addresses expire.

## Testing Domain Rotation

### Test Mode

No dedicated simulation mode is currently built in. To test safely:

- Use `bin/rotate-domain search` to verify API connectivity and availability checks.
- Run `bin/rotate-domain rotate` only when ready to confirm a real purchase.

### Validation Checklist

- [ ] API credentials configured
- [ ] Budget limits set
- [ ] Search command verified
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

```bash
# Check current budget/spending
bin/rotate-domain status

# Increase monthly budget
bin/rotate-domain config
```

### Domain Not Available

**Problem:** Desired/attempted domain already taken

**Solution:**

```bash
bin/rotate-domain search
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

`DomainAPIClient` can be extended for additional registrars. Any new registrar client must implement:

- `search_domain(domain)`
- `purchase_domain(domain, years=1)`
- `get_pricing(tld)`

## CLI Reference

Available commands:

```bash
bin/rotate-domain config
bin/rotate-domain status
bin/rotate-domain search
bin/rotate-domain rotate
bin/rotate-domain list
```

## Summary

Domain rotation is:
- ✅ **Easy**: Simple CLI commands
- ✅ **Cheap**: $1-2 per domain
- ✅ **Automated**: Set and forget with cron
- ✅ **Secure**: Budget controls and API key management
- ✅ **Flexible**: Support for multiple registrars

Start with monthly rotation and adjust based on your needs!
