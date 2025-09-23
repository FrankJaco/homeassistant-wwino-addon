import logging
from .config import COUNTRY_ABBREVIATIONS

logger = logging.getLogger(__name__)

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

def calculate_b4b_score(wine: dict):
    """
    Calculates the Best-for-Budget (B4B) score based on rating and cost tier.
    """
    display_rating = _get_display_rating(wine)
    cost_tier = wine.get('cost_tier')
    
    if not (display_rating is not None and cost_tier is not None and isinstance(cost_tier, int) and cost_tier > 0):
        return None

    try:
        raw_score = (23.76 * float(display_rating)) - (19.8 * cost_tier)
        return round(raw_score)
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to calculate B4b score for wine {wine.get('name')}: {e}")
        return None

def format_wine_for_todo(wine: dict) -> str:
    """
    Formats the wine name and vintage for the HA To-Do list item summary.
    Truncates the wine name if the total string would exceed 255 characters.
    """
    name = wine.get("name") or "n/a"
    vintage = wine.get("vintage")

    # FIX: Implement truncation logic to respect Home Assistant's 255 character limit.
    if vintage:
        # The suffix " (YYYY)" takes 7 characters. Max name length is 255 - 7 = 248.
        max_name_length = 248
        suffix = f" ({vintage})"
    else:
        # If there's no vintage, the name can take the full space.
        max_name_length = 255
        suffix = ""
    
    # Truncate if necessary, leaving room for an ellipsis.
    if len(name) > max_name_length:
        name = name[:max_name_length - 3] + "..."
    
    return f"{name}{suffix}"


def build_markdown_description(wine: dict, current_quantity: int) -> str:
    """
    Builds a Markdown-formatted description for the wine, used in the To-Do list item's description.
    """
    description_parts = []
    
    # This complex truncation logic for the description is fine as-is.
    varietal_str = wine.get("varietal")
    rendered_varietal_line_markdown = []
    current_visual_length = 0
    MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL = 32
    TRUNCATION_THRESHOLD_PERCENT = 0.60
    ELLIPSIS_LENGTH = 0

    if varietal_str and varietal_str != "Unknown Varietal":
        individual_varietals = [v.strip() for v in varietal_str.split(',')]
        if individual_varietals:
            first_grape = individual_varietals[0]
            visual_len_first_grape = len(first_grape)
            if visual_len_first_grape <= MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL:
                rendered_varietal_line_markdown.append(f"**{first_grape}**")
                current_visual_length += visual_len_first_grape
            else:
                chars_for_truncated_grape = MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL - ELLIPSIS_LENGTH
                if chars_for_truncated_grape > 0:
                    truncated_grape = first_grape[:chars_for_truncated_grape]
                    rendered_varietal_line_markdown.append(f"**{truncated_grape}**")
                    current_visual_length += len(truncated_grape)

            for i, grape in enumerate(individual_varietals[1:]):
                if not rendered_varietal_line_markdown and i > 0:
                    break
                separator_text = " " if i == 0 else ", "
                visual_len_grape = len(grape)
                remaining_line_space = MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL - current_visual_length
                if remaining_line_space >= (len(separator_text) + visual_len_grape):
                    rendered_varietal_line_markdown.append(f"{separator_text}{grape}")
                    current_visual_length += len(separator_text) + visual_len_grape
                else:
                    space_for_grape_body = remaining_line_space - len(separator_text)
                    if space_for_grape_body > 0:
                        if (space_for_grape_body / visual_len_grape) >= TRUNCATION_THRESHOLD_PERCENT:
                            truncated_grape = grape[:space_for_grape_body]
                            rendered_varietal_line_markdown.append(f"{separator_text}{truncated_grape}")
                            current_visual_length += len(separator_text) + len(truncated_grape)
                    break

    description_parts.append("".join(rendered_varietal_line_markdown) if rendered_varietal_line_markdown else "Unknown Varietal")

    region_str = wine.get("region")
    country_str = wine.get("country")
    region_country_display = []
    current_rc_visual_length = 0

    if region_str and region_str != "Unknown Region":
        visual_len_region = len(region_str)
        if visual_len_region <= MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL:
            region_country_display.append(f"**{region_str}**")
            current_rc_visual_length += visual_len_region
        else:
            chars_for_truncated_region = MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL - ELLIPSIS_LENGTH
            if chars_for_truncated_region > 0:
                truncated_region = region_str[:chars_for_truncated_region]
                region_country_display.append(f"**{truncated_region}**")
                current_rc_visual_length += len(truncated_region)

    if country_str and country_str != "Unknown Country":
        separator_rc = " " if region_country_display else ""
        remaining_space_rc = MAX_VISUAL_LINE_LENGTH_FOR_VARIETAL - current_rc_visual_length
        visual_len_country = len(country_str)
        if remaining_space_rc >= (len(separator_rc) + visual_len_country):
            region_country_display.append(f"{separator_rc}{country_str}")
            current_rc_visual_length += len(separator_rc) + visual_len_country
        else:
            space_for_country_body = remaining_space_rc - len(separator_rc)
            if space_for_country_body > 0 and (space_for_country_body / visual_len_country) >= TRUNCATION_THRESHOLD_PERCENT:
                truncated_country = country_str[:space_for_country_body]
                region_country_display.append(f"{separator_rc}{truncated_country}")

    if region_country_display:
        description_parts.append("".join(region_country_display))
    else:
        description_parts.append("Unknown Region/Country")

    cost_tier = wine.get('cost_tier')
    line3 = f"Qty: [ **{current_quantity}** ]"
    
    display_rating = _get_display_rating(wine)
        
    if display_rating is not None:
        line3 += f"&emsp;⭐**{display_rating:.1f}**"
        
    b4b_score = calculate_b4b_score(wine)
    if b4b_score is not None:
        score_str = f"+{b4b_score}" if b4b_score > 0 else str(b4b_score)
        if score_str.startswith("-") or score_str.startswith("+"):
             score_str = f"\u200B{score_str}"
        line3 += f" | 🎯&nbsp;**{score_str}**"

    if cost_tier and isinstance(cost_tier, int) and cost_tier > 0:
        cost_display = ''.join(['$'] * cost_tier)
        line3 += f" | **{cost_display}**"
    
    description_parts.append(line3)

    return "  \n".join(description_parts)