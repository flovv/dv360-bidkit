# Canonical DV360 Custom Bidding Script: Floodlight Multi-Objective
# Uses sum_aggregate with conversion count bonuses and high-intent actions
return sum_aggregate([
    ([total_conversion_count(101, 0) > 0], 50.0),
    ([total_conversion_count(102, 0) > 0], 15.0),
    ([total_conversion_count(103, 0) > 0], 5.0),
    ([domain in ["trustedpartner.com", "premiumpublisher.org"]], 2.0),
])
