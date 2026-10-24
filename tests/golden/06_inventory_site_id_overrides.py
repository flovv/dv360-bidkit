# Canonical DV360 Custom Bidding Script: Inventory Site ID Overrides
# App / Exchange site_id direct score overrides
if site_id in ["11223344", "55667788"]:
    return 2.5

if domain in ["partnerapp.io"]:
    return 1.8

return 0.5
