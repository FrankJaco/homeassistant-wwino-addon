import logging

logger = logging.getLogger(__name__)

# Note: This is a placeholder for a more robust data model if needed
def calculate_b4b_score(wine: dict):
    """
    Calculates the Best-for-Budget (B4B) score based on rating and cost tier.
    Formula: (23.76 * Rating) - (19.8 * Cost Tier)
    Returns a rounded integer score or None if data is missing.
    """
    # Prefer personal rating if available, then vivino, then fallback to None
    personal_rating = wine.get('personal_rating')
    vivino_rating = wine.get('vivino_rating')
    
    display_rating = None
    if personal_rating is not None:
        display_rating = personal_rating
    elif vivino_rating is not None:
        display_rating = vivino_rating
        
    cost_tier = wine.get('cost_tier')
    
    # Check if all required values are present and valid
    if not (display_rating is not None and cost_tier is not None and isinstance(cost_tier, int) and cost_tier > 0):
        return None

    try:
        raw_score = (23.76 * display_rating) - (19.8 * cost_tier)
        return round(raw_score)
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to calculate B4b score for wine {wine.get('name')}: {e}")
        return None


def format_wine_for_todo(wine: dict) -> str:
    """
    Formats the wine name and vintage for display in the Home Assistant To-Do list item summary.
    Example: "Wine Name (2020)"
    """
    name = wine.get("name") or "n/a"
    vintage = wine.get("vintage")

    if vintage:
        return f"{name} ({vintage})"
    else:
        return name

def build_markdown_description(wine: dict, current_quantity: int, is_for_todo: bool = True) -> str:
    """
    Builds a Markdown-formatted description for the wine, used in the To-Do list item's description
    or for full display in the frontend.
    """
    description_parts = []
    
    # Line 1: Varietals
    varietal_str = wine.get("varietal")
    if varietal_str and varietal_str != "Unknown Varietal":
        individual_varietals = [v.strip() for v in varietal_str.split(',')]
        if individual_varietals:
            first_grape = individual_varietals[0]
            rendered_varietal_line_markdown = [f"**{first_grape}**"]
            if len(individual_varietals) > 1:
                rendered_varietal_line_markdown.append(f", {', '.join(individual_varietals[1:])}")
            description_parts.append("".join(rendered_varietal_line_markdown))
    else:
        description_parts.append("Unknown Varietal")

    # Line 2: Region + Country
    region_str = wine.get("region")
    country_str = wine.get("country")
    
    region_country_display = []
    if region_str and region_str != "Unknown Region":
        region_country_display.append(f"**{region_str}**")
    if country_str and country_str != "Unknown Country":
        if region_country_display:
            region_country_display.append(f", {country_str}")
        else:
            region_country_display.append(country_str)
            
    if region_country_display:
        description_parts.append("".join(region_country_display))
    else:
        description_parts.append("Unknown Region/Country")

    # Line 3: Qty, Ratings, B4B, and Cost Tier
    vivino_rating = wine.get('vivino_rating')
    personal_rating = wine.get('personal_rating')
    cost_tier = wine.get('cost_tier')

    line3 = f"Qty: [ **{current_quantity}** ]"
    
    display_rating = None
    if personal_rating is not None:
        display_rating = personal_rating
    elif vivino_rating is not None:
        display_rating = vivino_rating
        
    if display_rating is not None:
        line3 += f"&emsp;⭐**{display_rating:.1f}**"
        
    b4b_score = calculate_b4b_score(wine)
    if b4b_score is not None:
        if b4b_score > 0:
            score_str = f"\u200B+{b4b_score}"
        else:
            score_str = str(b4b_score)
        if score_str.startswith("-"):
            score_str = "\u200B" + score_str
        line3 += f" | 🎯&nbsp;**{score_str}**"

    if cost_tier and isinstance(cost_tier, int) and cost_tier > 0:
        cost_display = ''.join(['$'] * cost_tier)
        line3 += f" | **{cost_display}**"
    
    description_parts.append(line3)

    return "  \n".join(description_parts)
