import logging
from .config import COUNTRY_ABBREVIATIONS # Import constants from config

logger = logging.getLogger(__name__)

def format_wine_for_todo(wine: dict) -> str:
    """
    Formats the wine name and vintage for the HA To-Do list item summary.
    Example: "Wine Name (2020)"
    """
    name = wine.get("name", "n/a")
    vintage = wine.get("vintage")

    return f"{name} ({vintage})" if vintage else name

def build_markdown_description(wine: dict, current_quantity: int) -> str:
    """
    Builds a Markdown-formatted description for the wine, used in the To-Do list.
    Includes varietal, region, country, quantity, and ratings with truncation logic.
    """
    description_parts = []

    # Line 1: Varietals
    varietal_str = wine.get("varietal", "Unknown Varietal")
    description_parts.append(_format_varietal_line(varietal_str))

    # Line 2: Region & Country
    region_str = wine.get("region", "Unknown Region")
    country_str = wine.get("country", "Unknown Country")
    description_parts.append(_format_region_country_line(region_str, country_str))

    # Line 3: Quantity, Ratings, and Cost
    description_parts.append(_format_stats_line(wine, current_quantity))

    # Join with Markdown line breaks
    return "  \n".join(description_parts)

def _format_varietal_line(varietal_str: str) -> str:
    """Helper to format the varietal line with truncation."""
    MAX_VISUAL_LENGTH = 32
    TRUNCATION_PERCENT = 0.60
    
    if not varietal_str or varietal_str == "Unknown Varietal":
        return "Unknown Varietal"

    varietals = [v.strip() for v in varietal_str.split(',')]
    if not varietals:
        return "Unknown Varietal"

    # Bold the first grape
    first_grape = varietals[0]
    if len(first_grape) > MAX_VISUAL_LENGTH:
        first_grape = first_grape[:MAX_VISUAL_LENGTH]
    
    formatted_line = [f"**{first_grape}**"]
    current_length = len(first_grape)

    # Add subsequent grapes if they fit
    for grape in varietals[1:]:
        separator = ", "
        remaining_space = MAX_VISUAL_LENGTH - current_length - len(separator)
        
        if remaining_space <= 0:
            break

        if len(grape) <= remaining_space:
            formatted_line.append(f"{separator}{grape}")
            current_length += len(separator) + len(grape)
        elif (remaining_space / len(grape)) >= TRUNCATION_PERCENT:
            truncated_grape = grape[:remaining_space]
            formatted_line.append(f"{separator}{truncated_grape}")
            current_length += len(separator) + len(truncated_grape)
            break # Stop after one truncated grape

    return "".join(formatted_line)

def _format_region_country_line(region_str: str, country_str: str) -> str:
    """Helper to format the region and country line with truncation."""
    if (not region_str or region_str == "Unknown Region") and \
       (not country_str or country_str == "Unknown Country"):
        return "Unknown Region/Country"

    # Use abbreviation for country if available
    display_country = COUNTRY_ABBREVIATIONS.get(country_str, country_str)
    
    # Simple concatenation for now, can be expanded with same logic as varietals if needed
    line_parts = []
    if region_str and region_str != "Unknown Region":
        line_parts.append(f"**{region_str}**")
    if display_country and display_country != "Unknown Country":
        line_parts.append(display_country)
        
    return " ".join(line_parts)


def _format_stats_line(wine: dict, current_quantity: int) -> str:
    """Helper to format the line with quantity, ratings, B4B score, and cost."""
    vivino_rating = wine.get('vivino_rating')
    personal_rating = wine.get('personal_rating')
    cost_tier = wine.get('cost_tier')

    # Determine display rating (average of personal and Vivino if both exist)
    display_rating = vivino_rating
    if personal_rating is not None:
        display_rating = (personal_rating + vivino_rating) / 2 if vivino_rating else personal_rating

    # Calculate B4B score
    b4b_score = None
    if display_rating and cost_tier and isinstance(cost_tier, int) and cost_tier > 0:
        raw_score = (23.76 * display_rating) - (19.8 * cost_tier)
        b4b_score = round(raw_score, 1)

    # Build the markdown line
    stats_parts = [f"Qty: [ **{current_quantity}** ]"]
    if display_rating:
        stats_parts.append(f"⭐**{display_rating:.1f}**")
    
    if b4b_score is not None:
        score_str = f"+{b4b_score}" if b4b_score > 0 else str(b4b_score)
        # Using zero-width spaces to help with markdown rendering of +/-
        score_str = score_str.replace("+", "\u200B+").replace("-", "\u200B-")
        stats_parts.append(f"| 🎯&nbsp;**{score_str}**")
        
    if cost_tier and isinstance(cost_tier, int) and cost_tier > 0:
        stats_parts.append(f"| **{'$' * cost_tier}**")

    return "&emsp;".join(stats_parts)

def calculate_b4b_score(wine: dict):
    """Calculates the B4B score for display in the main UI (not To-Do list)."""
    vivino_rating = wine.get('vivino_rating')
    personal_rating = wine.get('personal_rating')
    cost_tier = wine.get('cost_tier')

    display_rating = vivino_rating
    if personal_rating is not None:
        display_rating = (personal_rating + vivino_rating) / 2 if vivino_rating else personal_rating

    if not all([display_rating, cost_tier, isinstance(cost_tier, int), cost_tier > 0]):
        return None
        
    try:
        raw_score = (23.76 * float(display_rating)) - (19.8 * int(cost_tier))
        return round(raw_score) # Return as whole number
    except (ValueError, TypeError):
        return None
