# Canonical DV360 Custom Bidding Script: Capped Revenue Ternary
# Capping high-value transactions to avoid whale distortion
raw_revenue = total_conversion_value(201, 0)
capped_revenue = 250.0 if raw_revenue > 250.0 else raw_revenue
return capped_revenue * 1.5
