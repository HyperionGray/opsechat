# Domain Registrar API Guide

This guide explains how to set up domain registrar APIs for the burner email domain rotation feature in opsechat.

## Overview

Opsechat supports automated domain purchasing for rotating burner email addresses. This provides guerrillamail-style functionality with your own domains, enhancing anonymity and avoiding shared-domain blocklists.

## Supported Registrars

### Porkbun (Recommended for Simplicity)

**Why Porkbun?**
- Competitive pricing on cheap TLDs (.xyz from $1.99/yr)
- Simple, well-documented API
- API access included with all accounts (no extra fee)
- Privacy protection included free
- Accepts cryptocurrency payments

**Cheap TLDs Available:**
| TLD | Registration Price | Renewal Price |
|-----|-------------------|---------------|
| .xyz | ~$1.99/yr | ~$10.99/yr |
| .club | ~$2.99/yr | ~$14.99/yr |
| .online | ~$2.99/yr | ~$34.99/yr |
| .site | ~$2.99/yr | ~$29.99/yr |
| .website | ~$2.99/yr | ~$24.99/yr |

*Prices subject to change. First-year registrations are often discounted.*

#### Getting Porkbun API Keys

1. **Create Account**: Sign up at [porkbun.com](https://porkbun.com/)

2. **Enable API Access**:
   - Log into your Porkbun dashboard
   - Go to **Account** → **API Access**
   - Click **Create API Key**
   - Save both the **API Key** and **Secret Key** securely

3. **Add Funds** (Optional):
   - For auto-purchase, add funds to your account
   - Porkbun accepts credit cards and cryptocurrency

4. **Configure in Opsechat**:
   ```
   Access: http://yourservice.onion/{path}/email/config
   Enter your API Key and Secret Key
   Set monthly budget limit
   ```

#### API Documentation

Full Porkbun API docs: [porkbun.com/api/json/v3/documentation](https://porkbun.com/api/json/v3/documentation)

Key endpoints used by opsechat:
- `domain/check` - Check domain availability
- `domain/create` - Purchase domain
- `pricing/get` - Get TLD pricing
- `domain/listAll` - List owned domains

### Namecheap (Supported)

Namecheap support is now available in the domain manager and CLI.

**Best for:**
- Teams that already operate on Namecheap
- Environments where Namecheap API is already approved
- Testing with Namecheap sandbox before production cutover

**Requirements:**
- API access enabled on your Namecheap account
- Whitelisted client IP in Namecheap API settings
- API key and account username

**Current implementation notes:**
- Domain availability checks are supported
- Price lookups are supported (register + renew)
- Domain purchase uses the Namecheap `domains.create` API with default contact payloads

#### Getting Namecheap API Access

1. Sign in at [namecheap.com](https://www.namecheap.com/)
2. Open API settings and enable API access
3. Add your client IP to the whitelist
4. Save your API key and username
5. Optionally test first in sandbox mode

#### Namecheap API Documentation

Full docs: [Namecheap API Intro](https://www.namecheap.com/support/api/intro/)

Key endpoints used by opsechat:
- `namecheap.domains.check`
- `namecheap.users.getPricing`
- `namecheap.domains.create`
- `namecheap.domains.getList`

## Additional Registrars (Planned)

The opsechat domain manager is designed to be extensible. Additional registrar support may include:

### Namesilo
- API key from: [Namesilo API](https://www.namesilo.com/api-reference)
- No spending requirement
- Very competitive bulk pricing

### Dynadot
- API key from: [Dynadot API](https://www.dynadot.com/domain/api.html)
- Good for bulk operations

### Cloudflare Registrar
- API key from: [Cloudflare Dashboard](https://dash.cloudflare.com/profile/api-tokens)
- At-cost pricing (no markup)
- Limited TLD support

## Configuration in Opsechat

### Via CLI

```bash
python domain_rotation_cli.py config
```

The CLI now prompts for registrar selection and registrar-specific fields:
- Porkbun: `api_key`, `api_secret`
- Namecheap: `api_key`, `username`, `client_ip`, optional `api_user`, optional `sandbox`

CLI state persists to `~/.opsechat/domain_config.json` and safely serializes domain timestamps.

### Via Web Interface

1. Start opsechat and access the email config page:
   ```
   http://yourservice.onion/{path}/email/config
   ```

2. Under "Domain API Configuration":
   - Select registrar (`porkbun` or `namecheap`)
   - Enter provider credentials
   - Set monthly budget limit (recommended: start with $20-50)

3. Click "Configure"

### Via Environment Variables (Advanced)

For container deployments, you can set:

```bash
# In docker-compose.yml or quadlet
Environment=DOMAIN_REGISTRAR=porkbun
Environment=PORKBUN_API_KEY=pk1_xxxxx
Environment=PORKBUN_API_SECRET=sk1_xxxxx
Environment=DOMAIN_MONTHLY_BUDGET=50.0

# or Namecheap
Environment=DOMAIN_REGISTRAR=namecheap
Environment=NAMECHEAP_API_KEY=nc_xxxxx
Environment=NAMECHEAP_USERNAME=your-namecheap-username
Environment=NAMECHEAP_CLIENT_IP=203.0.113.10
Environment=NAMECHEAP_SANDBOX=false
Environment=DOMAIN_MONTHLY_BUDGET=50.0
```

Then modify the runserver.py to read these on startup.

## Budget Management

Opsechat includes budget controls to prevent accidental overspending:

- **Monthly Budget**: Maximum amount to spend per month
- **Domain Price Limit**: Maximum price per domain (default: $5)
- **Current Spending**: Tracked in-memory (resets on restart)

View budget status:
```
http://yourservice.onion/{path}/email/config
```

## Domain Rotation Workflow

1. **Initial Setup**: Configure API and budget
2. **Generate Burner**: Creates email with current domain
3. **Auto-Rotate**: When domain is flagged/old, rotate to new domain
4. **Manual Rotate**: Force rotation via email config page

## Security Considerations

### API Key Storage

⚠️ **Important**: API keys are stored in-memory only. They are NOT persisted to disk. After restart, you must reconfigure.

For persistent configuration:
- Use environment variables in your deployment
- Store encrypted credentials separately
- Never commit API keys to version control

### Domain Privacy

All domains purchased through the API will use registrar privacy protection (Porkbun includes this free). Your personal information is not exposed in WHOIS.

### Spending Controls

- Always set a monthly budget
- Start with a low budget for testing ($10-20)
- Monitor spending in the config page
- Budget resets on application restart (intentional for ephemeral deployments)

## Troubleshooting

### "No API client configured"

Solution: Configure the domain API in email config page

### "Budget exceeded"

Solution: 
1. Wait for budget reset (restart application)
2. Increase monthly budget
3. Check current spending in config page

### "Could not find available cheap domain"

Possible causes:
- All randomly generated domains are taken (rare)
- API rate limiting
- Network connectivity issues

Solution: Try again after a few minutes

### API Authentication Failed

Possible causes:
- Incorrect API key or secret
- API access not enabled on registrar account
- Account suspended

Solution: Verify credentials in registrar dashboard

## Example: Complete Setup

```bash
# 1. Start opsechat
./compose-up.sh

# 2. Get the onion address from logs
podman-compose logs opsechat | grep "Your service is available"

# 3. Open in Tor Browser
# Navigate to: http://xxxxx.onion/randompath/email/config

# 4. Configure Porkbun API
# - API Key: pk1_your_api_key_here
# - API Secret: sk1_your_secret_here
# - Monthly Budget: 20.00

# 5. Generate burner email
# Navigate to: http://xxxxx.onion/randompath/email/burner
# Click "Generate Burner Email"

# 6. Rotate to new domain (if needed)
# Click "Rotate Domain" in email config
```

## Cost Optimization Tips

1. **Use cheap TLDs**: .xyz and .club are cheapest
2. **Register for 1 year only**: Burner domains don't need long registration
3. **Set low price limit**: Default $5 is good
4. **Monitor spending**: Check config page regularly
5. **Reuse domains**: Multiple burners can use same domain
6. **Time purchases**: First-year prices are often discounted

## See Also

- [EMAIL_SYSTEM.md](EMAIL_SYSTEM.md) - Full email system documentation
- [DOCKER.md](DOCKER.md) - Container deployment
- [QUADLETS.md](QUADLETS.md) - Podman Quadlet deployment
