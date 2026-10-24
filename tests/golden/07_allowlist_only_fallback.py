# Canonical DV360 Custom Bidding Script: Allowlist Only Fallback
# Strict allowlist policy: non-whitelisted domains receive None
if domain not in ["allowed-news.com", "verified-media.com", "premium-sports.com"]:
    return None

return 2.0
