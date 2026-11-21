"""
Centralized Product & Plan Helper Utilities
============================================
Dynamically manages product plan column mappings, plan labels, 
and filters valid plans (price > 0) across all CRM modules.
"""

# Master Plan Definitions (DB column name -> Human-readable label)
PRODUCT_PLAN_DEFINITIONS = {
    "weekly": "Weekly (7 Days)",
    "two_weekly": "15 Days",
    "monthly": "1 Month",
    "two_monthly": "2 Months",
    "quarterly": "3 Months",
    "six_monthly": "6 Months",
    "nine_monthly": "9 Months",
    "yearly": "1 Year (12 Months)",
    "eighteen_monthly": "1.5 Years (18 Months)",
    "twenty_four_monthly": "2 Years (24 Months)",
}


def register_product_plan(plan_key, label):
    """
    Dynamically register a new plan key and label.
    Use this if new plan columns are added to the products table in the DB.
    """
    if plan_key:
        PRODUCT_PLAN_DEFINITIONS[plan_key.strip().lower()] = label.strip()


def get_plan_label(plan_key):
    """
    Returns the human-readable label for a plan key.
    If key is not registered, formats key dynamically (e.g. 'custom_plan' -> 'Custom Plan').
    """
    if not plan_key:
        return "N/A"
    clean_key = str(plan_key).strip().lower()
    return PRODUCT_PLAN_DEFINITIONS.get(clean_key, clean_key.replace("_", " ").title())


def extract_active_product_plans(product_row):
    """
    Takes a product dict or DB row, extracts all plan price columns, 
    and returns ONLY those plans where price > 0.
    
    Returns a list of dicts:
    [
        {
            "key": "monthly",
            "label": "1 Month",
            "price": 5000.0,
            "price_fmt": "₹5,000.00"
        }, ...
    ]
    """
    if not product_row or not isinstance(product_row, dict):
        return []

    active_plans = []
    
    # Iterate through registered plan definitions
    for key, label in PRODUCT_PLAN_DEFINITIONS.items():
        val = product_row.get(key)
        if val is not None:
            try:
                price = float(val)
                if price > 0:
                    active_plans.append({
                        "key": key,
                        "label": label,
                        "price": price,
                        "price_fmt": f"₹{price:,.2f}"
                    })
            except (ValueError, TypeError):
                continue

    # Also check if any additional columns in product_row are float prices > 0 not in registered definitions
    for k, v in product_row.items():
        if k not in PRODUCT_PLAN_DEFINITIONS and k not in ("id", "product_uuid", "product_name", "description", "status", "created_at", "updated_at", "active_plans"):
            try:
                price = float(v)
                if price > 0:
                    label = k.replace("_", " ").title()
                    active_plans.append({
                        "key": k,
                        "label": label,
                        "price": price,
                        "price_fmt": f"₹{price:,.2f}"
                    })
            except (ValueError, TypeError):
                continue

    return active_plans


def fetch_active_products_with_plans(cursor):
    """
    Fetches all active products from DB and attaches 'active_plans' list to each product.
    Only plans with price > 0 are included in 'active_plans'.
    """
    cursor.execute("SELECT * FROM products WHERE status = 1 ORDER BY product_name ASC")
    products = cursor.fetchall() or []

    for p in products:
        p["active_plans"] = extract_active_product_plans(p)
        
    return products
