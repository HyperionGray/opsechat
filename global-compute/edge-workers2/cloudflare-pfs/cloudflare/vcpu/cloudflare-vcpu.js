name = "pfs-vcpu"
main = "cloudflare-vcpu.js"
compatibility_date = "2025-10-06"
workers_dev = true

# If you prefer explicit rather than login prompts:
# account_id = "YOUR_ACCOUNT_ID"

[env.production]
vars = { ENVIRONMENT = "production" }

# Optional KV, R2, or other bindings go here when you wire them:
# [[kv_namespaces]]
# binding = "PACKET_STATE"
# id = "YOUR_KV_NAMESPACE_ID"

# Optional: custom domain route (uncomment and fill when ready)
# routes = [
#   { pattern = "vcpu.example.com/*", zone_id = "YOUR_ZONE_ID" }
# ]
