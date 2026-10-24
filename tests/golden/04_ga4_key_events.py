# Canonical DV360 Custom Bidding Script: GA4 Key Events
# Rewards GA4 purchase and lead key events
purchases = ga4_conversions_count("G-XXXXXXXX", "purchase")
leads = ga4_conversions_count("G-XXXXXXXX", "generate_lead")
return (purchases * 100.0) + (leads * 20.0)
