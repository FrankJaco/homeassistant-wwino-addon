import logging

logger = logging.getLogger(__name__)

# NEW: Mapping of wine types to a single emoji character
WINE_TYPE_EMOJIS = {
    "Red": "🍷",
    "White": "🥂",
    "Rosé": "🌸",
    "Sparkling": "🍾",
    "Dessert": "🍰",
    "Fortified": "🍰",
}

# NEW: Region dataset (loaded once by main.py)
REGION_DATA = {}

def initialize_regions(data: dict):
    """
    Called from main.py at startup.
    Provides region/country map where each country includes a "code".
    """
    global REGION_DATA
    if isinstance(data, dict):
        REGION_DATA = data
        logger.info(f"Formatting module initialized with {len(data)} countries.")
    else:
        logger.warning("initialize_regions called with invalid data type.")

def _get_country_code(country_name: str):
    """
    Look up 2-letter code from REGION_DATA.
    Falls back to the full name if not found.
    """
    if not country_name or not REGION_DATA:
        return country_name

    record = REGION_DATA.get(country_name)
    if record and isinstance(record, dict):
        return record.get("code", country_name)

    return country_name


def _get_display_rating(wine: dict):
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
    Formats the wine name and vintage for the HA To-Do list summary.
    Only change: country code now comes from REGION_DATA.
    """
    name = wine.get("name") or "n/a"
    vintage = wine.get("vintage")

    if vintage:
        max_name_length = 248
        suffix = f" ({vintage})"
    else:
        max_name_length = 255
        suffix = ""

    if len(name) > max_name_length:
        name = name[:max_name_length - 3] + "..."

    return f"{name}{suffix}"


def build_markdown_description(wine: dict, current_quantity: int) -> str:
    description_parts = []
    
    # ---- Varietal Line (unchanged) ----
    varietal_str = wine.get("varietal")
    rendered_varietal_line_markdown = []
    current_visual_length = 0
    MAX_VISUAL_LINE_LENGTH = 32
    TRUNCATION_THRESHOLD_PERCENT = 0.60
    ELLIPSIS_LENGTH = 0

    if varietal_str and varietal_str != "Unknown Varietal":
        individual_varietals = [v.strip() for v in varietal_str.split(',')]
        if individual_varietals:
            first_grape = individual_varietals[0]
            visual_len_first_grape = len(first_grape)
            if visual_len_first_grape <= MAX_VISUAL_LINE_LENGTH:
                rendered_varietal_line_markdown.append(f"**{first_grape}**")
                current_visual_length += visual_len_first_grape
            else:
                chars_for_truncated_grape = MAX_VISUAL_LINE_LENGTH - ELLIPSIS_LENGTH
                if chars_for_truncated_grape > 0:
                    truncated_grape = first_grape[:chars_for_truncated_grape]
                    rendered_varietal_line_markdown.append(f"**{truncated_grape}**")
                    current_visual_length += len(truncated_grape)

            for i, grape in enumerate(individual_varietals[1:]):
                if not rendered_varietal_line_markdown and i > 0:
                    break
                separator_text = " " if i == 0 else ", "
                visual_len_grape = len(grape)
                remaining_line_space = MAX_VISUAL_LINE_LENGTH - current_visual_length
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

    # ---- Region/Country Line (only change: lookup country code) ----
    region_str = wine.get("region")
    country_name = wine.get("country")

    country_abbr = _get_country_code(country_name)

    region_country_display = []
    current_rc_visual_length = 0

    if region_str and region_str != "Unknown Region":
        visual_len_region = len(region_str)
        if visual_len_region <= MAX_VISUAL_LINE_LENGTH:
            region_country_display.append(f"**{region_str}**")
            current_rc_visual_length += visual_len_region
        else:
            chars_for_truncated_region = MAX_VISUAL_LINE_LENGTH - ELLIPSIS_LENGTH
            if chars_for_truncated_region > 0:
                truncated_region = region_str[:chars_for_truncated_region]
                region_country_display.append(f"**{truncated_region}**")
                current_rc_visual_length += len(truncated_region)

    if country_name and country_name != "Unknown Country":
        separator_rc = " " if region_country_display else ""
        remaining_space = MAX_VISUAL_LINE_LENGTH - current_rc_visual_length
        if (len(separator_rc) + len(country_name)) <= remaining_space:
            region_country_display.append(f"{separator_rc}{country_name}")
        elif country_abbr and (len(separator_rc) + len(country_abbr)) <= remaining_space:
            region_country_display.append(f"{separator_rc}{country_abbr}")

    if region_country_display:
        description_parts.append("".join(region_country_display))
    else:
        description_parts.append("Unknown Region/Country")

    # ---- Stats Line (unchanged) ----
    line3_parts = []

    qty_str = f"Qty: {current_quantity}"
    line3_parts.append(qty_str)

    wine_type = wine.get("wine_type")
    type_emoji = WINE_TYPE_EMOJIS.get(wine_type, "🍇")
    line3_parts.append(f" {type_emoji}")

    alcohol = wine.get("alcohol_percent")
    if alcohol is not None:
        abv_str = f"{alcohol:.1f}%"
        line3_parts.append(abv_str)

    display_rating = _get_display_rating(wine)
    if display_rating is not None:
        rating_str = f" ⭐{display_rating:.1f}"
        line3_parts.append(rating_str)
    
    b4b_score = calculate_b4b_score(wine)
    if b4b_score is not None:
        score_str = f"+{b4b_score}" if b4b_score > 0 else str(b4b_score)
        b4b_str = f" 🎯{score_str}"
        line3_parts.append(b4b_str)

    cost_tier = wine.get('cost_tier')
    if cost_tier and isinstance(cost_tier, int) and cost_tier > 0:
        cost_display = ''.join(['$'] * cost_tier)
        cost_str = f" {cost_display}"
        line3_parts.append(cost_str)

    description_parts.append("".join(line3_parts))

    return "  \n".join(description_parts)
