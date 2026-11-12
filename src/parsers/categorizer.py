import re
from typing import Dict, Tuple, Optional, Any, List

CATEGORY_METADATA = {
    "Food & Dining": {
        "icon": "silverware-fork-knife",
        "color": "#FF5722",  # Deep Orange
        "keywords": [
            "swiggy", "zomato", "mcdonald", "starbucks", "domino", "kfc", "burger king",
            "subway", "pizza", "biryani", "chai", "cafe", "restaurant", "hotel", "dhaba",
            "baker", "sweet", "barbeque", "haldiram", "haldirams", "food", "kitchen", "dine"
        ]
    },
    "Groceries": {
        "icon": "cart",
        "color": "#4CAF50",  # Green
        "keywords": [
            "blinkit", "zepto", "bigbasket", "instamart", "dmart", "d-mart", "spencer",
            "natures basket", "supermarket", "hypermarket", "grocery", "groceries", "kirana",
            "milk", "milkman", "doodh", "dairy", "sundar", "jain mandir", "vegetable", "fruits", "provision", "fresh", "mandi"
        ]
    },
    "Shopping": {
        "icon": "shopping",
        "color": "#9C27B0",  # Purple
        "keywords": [
            "amazon", "flipkart", "myntra", "meesho", "ajio", "nykaa", "tata cliq",
            "zara", "h&m", "uniqlo", "marks & spencer", "decathlon", "croma", "reliance digital",
            "vijay sales", "apple", "clothing", "apparel", "footwear", "mall"
        ]
    },
    "Travel & Commute": {
        "icon": "car",
        "color": "#2196F3",  # Blue
        "keywords": [
            "uber", "ola", "rapido", "metro", "irctc", "railway", "makemytrip", "goibibo",
            "cleartrip", "yatra", "indigo", "air india", "petrol", "diesel", "fuel", "cng",
            "shell", "indian oil", "iocl", "hpcl", "bpcl", "toll", "fastag", "parking", "auto"
        ]
    },
    "Bills & Utilities": {
        "icon": "flash",
        "color": "#FF9800",  # Amber/Orange
        "keywords": [
            "airtel", "jio", "vi", "vodafone", "bsnl", "electricity", "power", "bescom",
            "cesc", "tata power", "torrent", "adani", "gas", "igl", "mgl", "mahanagar gas",
            "water", "broadband", "act fibernet", "wifi", "bill", "recharge", "dth", "tata play"
        ]
    },
    "Entertainment": {
        "icon": "movie-open",
        "color": "#E91E63",  # Pink
        "keywords": [
            "netflix", "spotify", "prime video", "hotstar", "disney", "sonyliv", "zee5",
            "bookmyshow", "pvr", "inox", "cinema", "theatre", "movie", "gaming", "steam",
            "playstation", "apple.com/bill", "youtube"
        ]
    },
    "Health & Medical": {
        "icon": "hospital-box",
        "color": "#009688",  # Teal
        "keywords": [
            "apollo", "pharmeasy", "1mg", "tata 1mg", "netmeds", "medplus", "hospital",
            "clinic", "pharmacy", "medical", "chemist", "dr.", "doctor", "diagnostic",
            "lal pathlabs", "pathology", "dentist", "healthcare"
        ]
    },
    "Investments & Savings": {
        "icon": "chart-line",
        "color": "#3F51B5",  # Indigo
        "keywords": [
            "zerodha", "groww", "angelone", "angel one", "upstox", "indmoney", "smallcase",
            "mutual fund", "sip", "kuvera", "coin", "shares", "stock", "insurance", "lic",
            "hdfc life", "max life"
        ]
    },
    "Transfers & Rent": {
        "icon": "bank-transfer",
        "color": "#795548",  # Brown
        "keywords": [
            "rent", "house rent", "maintenance", "landlord", "salary", "maid", "cook", "helper",
            "house help", "househelper", "driver", "sweeper", "advance", "wages"
        ]
    },
    "Others": {
        "icon": "dots-horizontal-circle",
        "color": "#607D8B",  # Blue Grey
        "keywords": []
    }
}


def categorize_transaction(
    merchant: str,
    notes: str = "",
    raw_text: str = "",
    custom_rules: Optional[Dict[str, str]] = None
) -> str:
    """
    Intelligently determines the category of an expense based on merchant name,
    notes, raw transaction SMS text, and any learned user custom category rules.
    """
    search_corpus = f"{merchant} {notes} {raw_text}".lower().strip()

    # 1. First check user-defined custom merchant learning rules
    if custom_rules:
        # Exact match or substring match against custom rules
        for pattern, cat in custom_rules.items():
            if pattern and (pattern in merchant.lower() or pattern in search_corpus):
                return cat

    # 2. Check standard built-in categories and keywords
    for category, meta in CATEGORY_METADATA.items():
        if category == "Others":
            continue
        for kw in meta["keywords"]:
            # Word boundary matching where appropriate or substring for unique brand names
            pattern = r'\b' + re.escape(kw) + r'\b' if len(kw) <= 4 else re.escape(kw)
            if re.search(pattern, search_corpus):
                return category

    return "Others"


def get_category_icon(category: str) -> str:
    """Returns Material Design icon name for standard or custom categories."""
    if category in CATEGORY_METADATA:
        return CATEGORY_METADATA[category]["icon"]

    # Intelligent icons for common custom category names
    low = (category or "").lower()
    if any(k in low for k in ["gym", "fit", "workout", "sport", "yoga"]):
        return "dumbbell"
    if any(k in low for k in ["pet", "dog", "cat", "vet", "animal"]):
        return "paw"
    if any(k in low for k in ["book", "study", "tuition", "school", "college", "course", "exam"]):
        return "book-open-page-variant"
    if any(k in low for k in ["car", "bike", "vehicle", "mechanic", "repair", "service", "garage"]):
        return "wrench"
    if any(k in low for k in ["gift", "present", "donation", "charity", "temple", "puja", "mandir"]):
        return "gift"
    if any(k in low for k in ["salon", "beauty", "spa", "parlour", "haircut"]):
        return "content-cut"
    if any(k in low for k in ["loan", "emi", "borrow", "lend", "debt"]):
        return "cash-multiple"
    if any(k in low for k in ["house", "home", "flat", "rent", "furniture"]):
        return "home"
    return "tag-outline"


def get_category_color(category: str) -> str:
    """Returns Hex color string for standard or custom categories."""
    if category in CATEGORY_METADATA:
        return CATEGORY_METADATA[category]["color"]

    # Aesthetic rotating color palette for user-created custom categories
    custom_palette = [
        "#00BCD4",  # Cyan
        "#8BC34A",  # Light Green
        "#E91E63",  # Pink
        "#673AB7",  # Deep Purple
        "#FF9800",  # Orange
        "#009688",  # Teal
        "#3F51B5",  # Indigo
        "#03A9F4"   # Light Blue
    ]
    hash_val = sum(ord(c) for c in (category or ""))
    return custom_palette[hash_val % len(custom_palette)]
