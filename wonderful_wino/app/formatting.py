import logging
from decimal import Decimal, ROUND_HALF_UP

# Set up a logger specific to this module
logger = logging.getLogger(__name__)

# NEW: Mapping of wine types to a single emoji character
WINE_TYPE_EMOJIS = {
    "Red": "🍷",
    "White": "🥂",
    "Rosé": "🌸",
    "Sparkling": "🍾",
    "Dessert": "🍰",
    "Fortified": "🍰",  # Grouping with Dessert as they share characteristics
}

# --- NEW: Region data placeholder (REQUIRED FOR MIGRATION) ---
REGION_DATA = {}

def initialize_regions(data: dict):
    """
    Receives region/country hierarchy from main.py at startup,
    which will be used to look up country codes.
    """
    global REGION_DATA
    if isinstance(data, dict):
        REGION_DATA = data
        logger.info(f"Formatting module initialized with {len(data)} countries.")
    else:
        logger.warning("formatting.initialize_regions called with invalid data type.")

def _get_country_code(country_name: str):
    """
    Gets the country code (e.g., 'US') from the initialized REGION_DATA.
    Falls back to the full name if data is missing.
    """
    if not country_name or not REGION_DATA:
        return country_name # Return original name if no data is available
        
    # Look up the country object using the full name (e.g., 'United States')
    country_obj = REGION_DATA.get(country_name)
    if country_obj and isinstance(country_obj, dict):
        # Return the code (e.g., 'US'), or fallback to the full name
        return country_obj.get("code", country_name)
        
    return country_name # Fallback to original name

def _get_display_rating(wine: dict):
    """
    Helper to determine the display rating, averaging if both personal and vivino ratings exist.
    """
    personal_rating = wine.get('personal_rating')
    vivino_rating = wine.get('vivino_rating')
    
    display_rating = None
    if personal_rating is not None and vivino_rating is not None:
        try:
            display_rating = (float(personal_rating) + float(vivino_rating)) / 2
        except (ValueError, TypeError):
            display_rating = personal_rating or vivino_rating
    elif personal_rating is not None:
        display_rating = personal_rating
    elif vivino_rating is not None:
        display_rating = vivino_rating
        
    return display_rating

def format_wine_for_todo(wine: dict):
    """
    Creates the short, scannable title for the HA To-Do list item.
    e.g., "My Awesome Wine (US) - 2020"
    
    Uses the centralized region data for country codes (MANDATORY CHANGE).
    """
    name = wine.get('name', 'Unknown Wine')
    vintage = wine.get('vintage') or 'NV' # Handle None or empty string
    country = wine.get('country', 'Unknown')
    
    # Get the country code from our initialized REGION_DATA
    country_code = _get_country_code(country)
    
    return f"{name} ({country_code}) - {vintage}"

def build_markdown_description(wine: dict, current_quantity: int):
    """
    Builds a rich markdown description for the HA To-Do item.

    FIXED: Uses the most specific 'region' field followed by 'country' for conciseness.
    The 'region_full' field is ignored for this specific output.
    """
    lines = []
    
    # --- Line 1: Region and Varietal (FIXED for conciseness as requested) ---
    region = wine.get('region')
    country = wine.get('country')
    varietal = wine.get('varietal')

    # 1. Use Region, Country if both are specific and valid (e.g., "Napa Valley, United States")
    if region and region != 'Unknown Region' and country and country != 'Unknown Country':
        lines.append(f"**Region:** {region}, {country}")
    # 2. Fallback to Country only
    elif country and country != 'Unknown Country':
        lines.append(f"**Country:** {country}")

    if varietal and varietal != 'Unknown Varietal':
        lines.append(f"**Varietal:** {varietal}")

    # --- Horizontal Separator ---
    lines.append("---")
    
    # --- Line 3: Stats Line (Quantity, Type, ABV, Rating, B4B Score) ---
    line3_parts = []

    # 1. Add mandatory parts: Quantity, Type, and ABV
    qty_str = f"**Qty:** {current_quantity}"
    line3_parts.append(qty_str)

    wine_type = wine.get("wine_type")
    type_emoji = WINE_TYPE_EMOJIS.get(wine_type, "🍇")
    if wine_type:
        line3_parts.append(f"{type_emoji} {wine_type}")

    alcohol = wine.get("alcohol_percent")
    if alcohol is not None and isinstance(alcohol, (int, float)):
        abv_str = f"**ABV:** {alcohol:.1f}%"
        line3_parts.append(abv_str)

    # 2. Add Rating
    display_rating = _get_display_rating(wine)
    if display_rating is not None:
        rating_str = f"**Rating:** ⭐{display_rating:.1f}"
        line3_parts.append(rating_str)
    
    # 3. Add B4B Score
    b4b_score = calculate_b4b_score(wine)
    if b4b_score is not None:
        score_str = f"+{b4b_score}" if b4b_score >= 0 else str(b4b_score)
        b4b_str = f"**B4B:** 🎯{score_str}"
        line3_parts.append(b4b_str)

    if line3_parts:
        # Use pipe separators for the stats line
        lines.append(" | ".join(line3_parts))
    
    # --- Horizontal Separator ---
    lines.append("---")
    
    # --- Line 4: Personal Notes/Tasting Notes/Price ---
    notes = []
    if wine.get('personal_notes'):
        notes.append(f"**Notes:** {wine.get('personal_notes')}")

    if wine.get('price'):
        notes.append(f"**Price Paid:** ${wine.get('price')}")
        
    if notes:
        lines.extend(notes)
        
    # --- Line 5: Vivino Link ---
    vivino_url = wine.get('vivino_url')
    if vivino_url and 'manual:' not in vivino_url:
        # Add an empty line for spacing before the link
        lines.append("")
        lines.append(f"[View on Vivino]({vivino_url})")

    # --- Line 6: Needs Review Warning ---
    if wine.get('needs_review'):
        lines.append("")
        lines.append("**⚠️ NEEDS REVIEW:** This wine data was manually entered or partially scraped. Please review.")

    return "\n\n".join(lines)
    
def calculate_b4b_score(wine: dict):
    """
    Calculates a "Bang for Buck" (B4B) score based on rating and cost.
    """
    cost_tier = wine.get('cost_tier')
    # Prioritize personal rating, fall back to Vivino
    rating = wine.get('personal_rating') or wine.get('vivino_rating')
    
    if not cost_tier or not rating:
        return None
        
    try:
        # Use Decimal for precise math
        rating_f = Decimal(str(rating))
        cost_map = {"low": 1, "mid": 2, "high": 3, "premium": 4}
        cost_val = Decimal(cost_map.get(cost_tier, 2))
        
        # Simple score: (rating^2) / cost_tier_value
        score = (rating_f ** 2) / cost_val
        
        # Round to 2 decimal places
        return float(score.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not calculate B4B score for {wine.get('name')}: {e}")
        return None