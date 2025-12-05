# Domain API Setup Guide

This guide explains how to set up domain registrar API access for automated burner email domain rotation in opsechat.

## Supported Registrars

### Porkbun (Recommended)

Porkbun offers cheap domains and a simple API, making it ideal for burner email rotation.

#### Why Porkbun?
- **Cheap domains**: .xyz domains starting at $0.99/year
- **Simple API**: Easy to integrate and use
- **No minimum spend**: Perfect for small-scale operations
- **Fast registration**: Domains available within minutes
- **Good selection**: .xyz, .club, .online, .site, and more

#### Getting API Credentials

1. **Create Account**
   - Go to [porkbun.com](https://porkbun.com)
   - Sign up for a new account
   - Verify your email address

2. **Enable API Access**
   - Log into your Porkbun account
   - Go to Account → API Access
   - Click "Create API Key"
   - Note down your API Key and Secret Key

3. **Add Funds (Optional)**
   - Go to Account → Billing
   - Add funds to your account for automatic domain purchases
   - Minimum recommended: $20 (covers 20+ .xyz domains)

#### API Configuration in Opsechat

1. **Access Configuration Page**
   ```
   http://your-onion-address.onion/your-path/email/config
   ```

2. **Enter API Credentials**
   - API Key: Your Porkbun API key
   - API Secret: Your Porkbun secret key
   - Monthly Budget: Set spending limit (e.g., $50/month)

3. **Test Configuration**
   - Click "Configure Domain API"
   - System will validate credentials
   - Check budget status display

#### Recommended Domain Extensions

**Cheapest Options:**
- `.xyz` - $0.99-$1.99/year
- `.club` - $1.99-$2.99/year  
- `.online` - $2.99-$3.99/year
- `.site` - $2.99-$3.99/year

**Slightly More Expensive but Professional:**
- `.com` - $8.99-$9.99/year
- `.net` - $9.99-$10.99/year
- `.org` - $9.99-$10.99/year

#### Budget Planning

**Conservative Usage (1-2 domains/month):**
- Budget: $10-20/month
- Covers: 10-20 .xyz domains or 3-6 .com domains

**Moderate Usage (5-10 domains/month):**
- Budget: $30-50/month  
- Covers: 30-50 .xyz domains or 5-10 .com domains

**Heavy Usage (20+ domains/month):**
- Budget: $100+/month
- Covers: 100+ .xyz domains or 20+ .com domains

## Alternative Registrars

### Namecheap

While not directly integrated, Namecheap offers competitive pricing and API access.

#### Getting Started
- Website: [namecheap.com](https://namecheap.com)
- API Documentation: [namecheap.com/support/api](https://www.namecheap.com/support/api/)
- Pricing: .com domains ~$8.88/year, .xyz ~$1.98/year

#### Integration Notes
- Requires custom API client implementation
- More complex API than Porkbun
- Good for high-volume usage

### GoDaddy

Enterprise-focused with comprehensive API.

#### Getting Started
- Website: [godaddy.com](https://godaddy.com)
- Developer Portal: [developer.godaddy.com](https://developer.godaddy.com)
- Pricing: Higher than alternatives but reliable

#### Integration Notes
- Requires OAuth authentication
- More expensive than Porkbun
- Better for production/enterprise use

## Security Considerations

### API Key Security

**Storage:**
- API keys are stored in memory only
- Never written to disk or logs
- Cleared when application restarts

**Access:**
- Keys only accessible to authenticated users
- No API key exposure in web interface
- Secure transmission over Tor

**Rotation:**
- Regularly rotate API keys (monthly recommended)
- Monitor API usage in registrar dashboard
- Set up spending alerts

### Domain Security

**Registration:**
- Use random domain names to avoid patterns
- Avoid personally identifiable information
- Consider using privacy protection services

**DNS:**
- Domains are used for email only (no web hosting)
- MX records point to your email infrastructure
- No A/AAAA records needed for web services

**Cleanup:**
- Expired domains are automatically released
- No persistent data stored on domains
- Regular cleanup prevents accumulation

## Usage Workflow

### Initial Setup

1. **Choose Registrar**
   - Porkbun recommended for beginners
   - Consider volume and budget requirements

2. **Create Account and Get API Keys**
   - Follow registrar-specific instructions above
   - Add initial funds to account

3. **Configure in Opsechat**
   - Access email configuration page
   - Enter API credentials and budget
   - Test configuration

### Daily Operations

1. **Generate Burner Email**
   - Go to burner email page
   - Click "Generate New Burner"
   - System automatically creates domain if needed

2. **Monitor Usage**
   - Check budget status in configuration
   - Monitor domain expiration times
   - Review spending in registrar dashboard

3. **Rotate Domains**
   - Click "Rotate Domain" for new domain
   - Old domains expire automatically
   - Budget tracking prevents overspending

### Maintenance

1. **Monthly Review**
   - Check spending against budget
   - Review domain usage patterns
   - Adjust budget if needed

2. **API Key Rotation**
   - Generate new API keys monthly
   - Update configuration in opsechat
   - Revoke old keys in registrar dashboard

3. **Cleanup**
   - Let expired domains lapse naturally
   - No manual cleanup required
   - Monitor for any stuck domains

## Troubleshooting

### API Connection Issues

**"API configuration failed"**
- Verify API key and secret are correct
- Check registrar account has sufficient funds
- Ensure API access is enabled in registrar account

**"Domain purchase failed"**
- Check account balance in registrar
- Verify monthly budget not exceeded
- Try different domain extension (.xyz vs .com)

**"Budget exceeded"**
- Increase monthly budget in configuration
- Wait for next month's budget reset
- Check actual spending in registrar dashboard

### Domain Issues

**"Domain not available"**
- System will try alternative names automatically
- Check if domain extension is supported
- Try different TLD (.xyz, .club, etc.)

**"Email not working with new domain"**
- Allow 15-30 minutes for DNS propagation
- Check MX record configuration
- Verify email server settings

### Cost Management

**Unexpected charges**
- Review domain purchase history
- Check for premium domain pricing
- Monitor auto-renewal settings

**Budget tracking inaccurate**
- Budget resets monthly, not rolling
- Check registrar account for actual spending
- Consider API rate limits affecting purchases

## Best Practices

### Cost Optimization

1. **Use Cheap TLDs**
   - Prefer .xyz, .club over .com
   - Check current pricing before bulk operations
   - Consider renewal costs for longer-term domains

2. **Set Reasonable Budgets**
   - Start with $20-30/month
   - Monitor actual usage patterns
   - Adjust based on real needs

3. **Avoid Premium Domains**
   - System filters out premium pricing
   - Stick to standard registration fees
   - Use random names to avoid premium conflicts

### Security Best Practices

1. **Regular Key Rotation**
   - Rotate API keys monthly
   - Use strong, unique passwords for registrar accounts
   - Enable 2FA on registrar accounts

2. **Monitor Usage**
   - Review domain purchases weekly
   - Set up spending alerts in registrar
   - Check for unauthorized API usage

3. **Limit Exposure**
   - Only configure API access when needed
   - Clear configuration when not in use
   - Use separate registrar account for opsechat

### Operational Best Practices

1. **Plan Capacity**
   - Estimate domain needs based on usage
   - Account for peak usage periods
   - Maintain buffer in budget for spikes

2. **Test Regularly**
   - Verify API connectivity monthly
   - Test domain registration process
   - Confirm email delivery with new domains

3. **Document Configuration**
   - Keep record of API credentials (securely)
   - Document budget and usage patterns
   - Maintain registrar account recovery information

## Support and Resources

### Porkbun Support
- Documentation: [kb.porkbun.com](https://kb.porkbun.com)
- API Docs: [porkbun.com/api/json/v3/documentation](https://porkbun.com/api/json/v3/documentation)
- Support: support@porkbun.com

### Opsechat Integration
- Configuration issues: Check application logs
- API errors: Review registrar account status
- Budget problems: Verify monthly limits and spending

### Community Resources
- Domain pricing comparison sites
- Registrar review forums
- API integration examples and tutorials

This guide should provide everything needed to set up automated domain rotation for burner emails in opsechat. Start with Porkbun for the easiest setup and lowest costs.