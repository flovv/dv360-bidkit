# DV360 BidKit MCP Server (Cloudflare Worker)

Zero-infrastructure, global edge Model Context Protocol (MCP) server for Google Display & Video 360 (DV360) custom bidding and attention optimization.

## Features

* **Zero Python Required for End-Users:** Media buyers and agency traders connect directly from **Claude Desktop**, **Cursor**, or web agents via Server-Sent Events (SSE).
* **Zero Hosting Cost:** Runs on Cloudflare Workers Free Tier (100,000 requests/day at $0/month).
* **3 Native Tools Exposed:**
  1. `validate_custom_bidding_script`: AST syntax, Google 2026 DSL compliance, 65k character limit.
  2. `get_attention_benchmarks`: Normative APM (Attentive Seconds Per Mille) and dwell multipliers from Simonov & Valletti (2024) and Lumen Research.
  3. `compile_custom_bidding_script`: Structured RuleSet to production Python script compilation.

---

## 1-Command Deployment to Cloudflare

From this directory (`dv360-bidkit/cloudflare-worker`):

```bash
# 1. Log in to your Cloudflare account (opens browser):
npx wrangler login

# 2. Deploy to Cloudflare Workers:
npx wrangler deploy
```

Wrangler will output your live URL:
`https://dv360-bidkit-mcp.<your-subdomain>.workers.dev`

---

## Connecting to Claude Desktop

Add this snippet to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dv360-bidkit": {
      "url": "https://dv360-bidkit-mcp.<your-subdomain>.workers.dev/sse"
    }
  }
}
```

Now open Claude Desktop: the `validate_custom_bidding_script`, `get_attention_benchmarks`, and `compile_custom_bidding_script` tools will be available directly in your conversations.

---

## Submitting to Directories

* **Smithery.ai:** Link the GitHub repository containing `smithery.yaml`.
* **Glama.co:** Submit your live `https://<your-subdomain>.workers.dev/sse` URL.
