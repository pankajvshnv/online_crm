"""
utils/recommendation_parser.py
==============================
🎯 RESEARCH CALL TYPE CLASSIFIER & BADGE RULES
==============================================
Is file me aap call text ke keywords aur unke corresponding badges/colors
ko bohot asani se edit, add ya modify kar sakte hain!

Jab bhi aapko koi naya keyword match karwana ho, bas niche di gayi
CALL_TYPE_RULES list me ek naya dictionary entry add kar dijiye.
Rules top-to-bottom order me check hote hain.
"""

# ==============================================================================
# 📋 CALL TYPE KEYWORD RULES (Top to Bottom Priority)
# ==============================================================================
CALL_TYPE_RULES = [
    # 1. Target Achieved Badges (Green / Success)
    {
        "name": "All Targets Achieved",
        "keywords": ["ALL TGT ACHIEVED", "ALL TARGET ACHIEVED", "ALL TARGETS ACHIEVED", "ALL TGT", "FULL TARGET"],
        "badge": "ALL TGT",
        "color": "success",
        "css_class": "bg-success-subtle text-success border border-success-subtle fw-semibold fs-11 px-2 py-1"
    },
    {
        "name": "Target 3 Achieved",
        "keywords": ["TGT3 ACHIEVED", "TARGET 3 ACHIEVED", "TGT 3 ACHIEVED", "TGT3"],
        "badge": "TGT 3",
        "color": "success",
        "css_class": "bg-success-subtle text-success border border-success-subtle fw-semibold fs-11 px-2 py-1"
    },
    {
        "name": "Target 2 Achieved",
        "keywords": ["TGT2 ACHIEVED", "TARGET 2 ACHIEVED", "TGT 2 ACHIEVED", "TGT2"],
        "badge": "TGT 2",
        "color": "success",
        "css_class": "bg-success-subtle text-success border border-success-subtle fw-semibold fs-11 px-2 py-1"
    },
    {
        "name": "Target 1 Achieved",
        "keywords": ["TGT1 ACHIEVED", "TARGET 1 ACHIEVED", "TGT 1 ACHIEVED", "TGT1 ALMOST ACHIEVED", "TGT1", "1ST TARGET"],
        "badge": "TGT 1",
        "color": "success",
        "css_class": "bg-success-subtle text-success border border-success-subtle fw-semibold fs-11 px-2 py-1"
    },
    {
        "name": "General Target Achieved",
        "keywords": ["TGT ACHIEVED", "TARGET ACHIEVED", "TARGET HIT", "TGT HIT"],
        "badge": "TGT ACHIEVED",
        "color": "success",
        "css_class": "bg-success-subtle text-success border border-success-subtle fw-semibold fs-11 px-2 py-1"
    },

    # 2. Stoploss / Exit Badges (Red / Danger)
    {
        "name": "Stop Loss Hit / Exit",
        "keywords": ["SL TRIGGERED", "SL HIT", "STOP LOSS HIT", "STOPLOSS HIT", "KINDLY EXIT", "EXIT CALL", "EXIT IN", "EXIT AT COST"],
        "badge": "SL HIT / EXIT",
        "color": "danger",
        "css_class": "bg-danger-subtle text-danger border border-danger-subtle fw-semibold fs-11 px-2 py-1"
    },

    # 3. Book Profit (Yellow / Warning)
    {
        "name": "Book Profit",
        "keywords": ["BOOK PROFIT", "BOOK FULL PROFIT", "BOOK PARTIAL PROFIT", "PROFIT BOOKED", "SAFE TRADERS BOOK"],
        "badge": "BOOK PROFIT",
        "color": "success",
        "css_class": "bg-warning-subtle text-warning-emphasis border border-warning-subtle fw-semibold fs-11 px-2 py-1"
    },

    # 4. Hold / Revise SL / Actions (Cyan / Info)
    {
        "name": "Revise / Trail SL",
        "keywords": ["REVISE SL", "TRAIL SL", "MODIFY SL", "SHIFT SL"],
        "badge": "REVISE SL",
        "color": "info",
        "css_class": "bg-info-subtle text-info border border-info-subtle fw-semibold fs-11 px-2 py-1"
    },
    {
        "name": "Hold Position",
        "keywords": ["KINDLY HOLD", "HOLD POSITION", "HOLD FOR NEXT", "HOLD CALL"],
        "badge": "HOLD",
        "color": "info",
        "css_class": "bg-info-subtle text-info border border-info-subtle fw-semibold fs-11 px-2 py-1"
    },
    {
        "name": "Ignore / Cancel",
        "keywords": ["KINDLY IGNORE", "NOT EXECUTED", "CANCEL CALL", "CALL CANCELLED"],
        "badge": "IGNORE / CANCEL",
        "color": "secondary",
        "css_class": "bg-secondary-subtle text-secondary border border-secondary-subtle fw-semibold fs-11 px-2 py-1"
    },

    # 5. New Buy / Sell Calls
    {
        "name": "Buy Call",
        "keywords": ["BUY", "BUY CALL", "LONG"],
        "badge": "BUY",
        "color": "primary",
        "css_class": "bg-primary-subtle text-primary border border-primary-subtle fw-semibold fs-11 px-2 py-1"
    },
    {
        "name": "Sell Call",
        "keywords": ["SELL", "SELL CALL", "SHORT"],
        "badge": "SELL",
        "color": "danger",
        "css_class": "bg-danger-subtle text-danger border border-danger-subtle fw-semibold fs-11 px-2 py-1"
    },

    # 6. Generic Update
    {
        "name": "Update",
        "keywords": ["UPDATE", "ALERT", "INFO"],
        "badge": "UPDATE",
        "color": "info",
        "css_class": "bg-info-subtle text-info border border-info-subtle fw-semibold fs-11 px-2 py-1"
    }
]


def parse_call_badge(rec_text):
    """
    Parses recommendation text against CALL_TYPE_RULES and returns the matching badge.
    
    Returns:
    {
        "badge": "ALL TGT" | "TGT 1" | "BUY" | "SL HIT / EXIT" | ...,
        "color": "success" | "danger" | "primary" | "warning" | "info" | ...,
        "css_class": "badge class..."
    }
    """
    if not rec_text:
        return {
            "badge": "CALL",
            "color": "primary",
            "css_class": "bg-primary-subtle text-primary border border-primary-subtle fw-semibold fs-11 px-2 py-1"
        }

    text_upper = str(rec_text).upper()

    for rule in CALL_TYPE_RULES:
        for kw in rule["keywords"]:
            if kw in text_upper:
                return {
                    "badge": rule["badge"],
                    "color": rule["color"],
                    "css_class": rule["css_class"]
                }

    # Default fallback
    return {
        "badge": "CALL",
        "color": "primary",
        "css_class": "bg-primary-subtle text-primary border border-primary-subtle fw-semibold fs-11 px-2 py-1"
    }
