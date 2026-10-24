# Canonical DV360 Custom Bidding Script: Inventory Policy Exclusions
# Excludes non-performing/fraudulent domains by returning None
if domain in ["fraud-click.xyz", "bot-farm.net", "lowquality-mfa.biz"]:
    return None

return first_match_aggregate([
    ([domain in ["goodsite.org", "newssite.com"]], 1.4),
    ([True], 0.7),
])
