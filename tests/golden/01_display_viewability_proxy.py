# Canonical DV360 Custom Bidding Script: Display Viewability Proxy
# Uses first_match_aggregate over domain tiers with a fallback
return first_match_aggregate([
    ([domain in ["nyt.com", "wsj.com", "ft.com"]], 1.5),
    ([domain in ["techcrunch.com", "theverge.com"]], 1.2),
    ([domain in ["forbes.com", "bloomberg.com"]], 1.1),
    ([True], 0.8),
])
