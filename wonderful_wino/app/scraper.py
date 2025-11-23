import requests
from bs4 import BeautifulSoup
import re
import json
import logging
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
import time 
import random 

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Set up a logger specific to this module
logger = logging.getLogger(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0'
]

WINE_TYPES = {'Red', 'White', 'Sparkling', 'Rosé', 'Fortified', 'Dessert'}

# Placeholder for the list loaded from main.py
GLOBAL_GRAPE_VARIETALS = []

def initialize_varietals(varietals_list):
    """
    Initializes the global grape varietals list from the list loaded in main.py.
    The list received from main.py is already lowercased.
    We sort it by length descending for better heuristic matching.
    """
    global GLOBAL_GRAPE_VARIETALS
    # The list is already lowercased by main.py
    GLOBAL_GRAPE_VARIETALS = sorted(varietals_list, key=len, reverse=True)
    logger.info(f"Scraper initialized with {len(GLOBAL_GRAPE_VARIETALS)} grape varietals.")

# Optional region data storage
REGION_DATA = {}

def initialize_regions(data: dict):
    """
    Receives region/country hierarchy from main.py at startup.
    This doesn't alter existing scraper behavior but allows
    region matching or validation in future updates.
    """
    global REGION_DATA
    if isinstance(data, dict):
        REGION_DATA = data
        logger.info(f"Initialized region data with {len(data)} countries.")
    else:
        logger.warning("initialize_regions called with invalid data type.")

def _region_hint_from_url(vivino_url):
    """Try to infer country/region/subregion directly from the URL path before scraping."""
    path = urlparse(vivino_url).path.lower().replace("_", "-")
    for country, cdata in REGION_DATA.items():
        for region_name, region_data in cdata.get("regions", {}).items():
            region_key = region_name.lower().replace(" ", "-")
            if region_key in path:
                return {"country": country, "region": region_name}
            for subregion_name, subregion_data in region_data.get("subregions", {}).items():
                sub_key = subregion_name.lower().replace(" ", "-")
                if sub_key in path:
                    return {"country": country, "region": region_name, "subregion": subregion_name}
                for subsub in subregion_data.get("subsubregions", []):
                    subsub_key = subsub.lower().replace(" ", "-")
                    if subsub_key in path:
                        return {
                            "country": country,
                            "region": region_name,
                            "subregion": subregion_name,
                            "subsubregion": subsub
                        }
    return None

def _parse_url_for_fallback_data(url: str):
    """
    Parses a Vivino URL to get a fallback name and vintage.
    """
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        vintage = int(query_params['year'][0]) if 'year' in query_params else None

        match = re.search(r'/(?:[a-zA-Z]{2}/)?([^/]+)/w/', parsed_url.path)
        if match:
            path_name = match.group(1).replace('-', ' ').title()
            logger.debug(f"Fallback parser matched long URL format for name: {path_name}")
            return {'name': path_name, 'vintage': vintage}
        
        match = re.search(r'/wines/(\d+)', parsed_url.path)
        if match:
            wine_id = match.group(1)
            path_name = f"Vivino Wine ID {wine_id}"
            logger.debug(f"Fallback parser matched short URL format, created placeholder name: {path_name}")
            return {'name': path_name, 'vintage': vintage}

    except (ValueError, IndexError, TypeError) as e:
        logger.error(f"Could not parse fallback data from URL {url}: {e}")
    
    return None

def _perform_scrape_attempt_selenium(url: str):
    """
    Performs a single, complete scrape attempt using a headless Chrome browser.
    """
    logger.debug(f"Executing Selenium scrape attempt for URL: {url}")
    
    options = Options()
    options.page_load_strategy = 'eager'
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    options.add_argument("window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=en-US")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get(url)

        # --- FIX: INCREASED TIMEOUT FROM 25 TO 40 SECONDS ---
        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1[class*='wine-page-header__name'], h1[class*='VintageTitle__wine'], h1"))
        )
        
        final_url_after_scrape = driver.current_url
        page_source = driver.page_source
        logger.debug(f"Selenium successfully loaded page. Final URL: {final_url_after_scrape}")

    except TimeoutException:
        logger.error(f"Selenium timed out waiting for page content to load for URL: {url}")
        if driver: driver.quit()
        return None, url
    except WebDriverException as e:
        logger.error(f"WebDriverException during Selenium execution for {url}: {e}", exc_info=True)
        if driver: driver.quit()
        return None, url
    except Exception as e:
        logger.error(f"An unexpected error occurred during Selenium execution: {e}", exc_info=True)
        if driver: driver.quit()
        return None, url
    finally:
        if driver:
            driver.quit()

    soup = BeautifulSoup(page_source, 'lxml')
    
    wine_data = {
        'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal',
        'region': 'Unknown Region', 'country': 'Unknown Country',
        'vivino_rating': None, 'image_url': None,
        'alcohol_percent': None, 'wine_type': None
    }

    name_tag = soup.find('h1', class_=re.compile(r'wine-page-header__name|VintageTitle_wine')) or soup.find('h1')
    if name_tag:
        wine_name = " ".join(name_tag.text.strip().split())
        if "404" in wine_name or "not found" in wine_name.lower():
            logger.warning(f"Scrape failed for {final_url_after_scrape}: Page content indicates a 404 or error page.")
            return None, final_url_after_scrape
        wine_data['name'] = wine_name
    
    if wine_data['name'] == 'Unknown Wine':
        logger.warning(f"Scrape failed for {final_url_after_scrape}: No h1 tag found on the page.")
        return None, final_url_after_scrape

    all_grape_names_collected = []
    found_grapes_in_json = False
    
    # Primary Method: Parse the __PRELOADED_STATE__ JSON blob.
    preloaded_state_script = soup.find('script', string=re.compile(r'window\.__PRELOADED_STATE__\.vintagePageInformation'))
    if preloaded_state_script:
        logger.debug("Found __PRELOADED_STATE__ script tag. Parsing for detailed wine info.")
        script_content = preloaded_state_script.string
        json_str_match = re.search(r'window\.__PRELOADED_STATE__\.vintagePageInformation\s*=\s*(\{.*?\});', script_content, re.DOTALL)
        if json_str_match:
            try:
                page_info = json.loads(json_str_match.group(1))
                vintage_info = page_info.get('vintage', {})
                wine_info = vintage_info.get('wine', {})
                
                # Try to get region and country from the JSON
                if wine_info.get('region'):
                    region_data = wine_info.get('region', {})
                    if region_data.get('name'):
                        wine_data['region'] = region_data['name']
                        logger.debug(f"Found Region from __PRELOADED_STATE__: {wine_data['region']}")
                    
                    if region_data.get('country'):
                        country_data = region_data.get('country', {})
                        if country_data.get('name'):
                             wine_data['country'] = country_data['name']
                             logger.debug(f"Found Country from __PRELOADED_STATE__: {wine_data['country']}")

                if wine_data['image_url'] is None:
                    image_variations = vintage_info.get('image', {}).get('variations', {})
                    image_url = image_variations.get('bottle_large') or image_variations.get('bottle_medium')
                    if image_url:
                        wine_data['image_url'] = 'https:' + image_url if image_url.startswith('//') else image_url
                        logger.debug(f"Found Image URL from __PRELOADED_STATE__: {image_url}")

                if wine_data['wine_type'] is None:
                    wine_type_id = wine_info.get('type_id')
                    if wine_type_id == 1: wine_data['wine_type'] = 'Red'
                    elif wine_type_id == 2: wine_data['wine_type'] = 'White'
                    elif wine_type_id == 3: wine_data['wine_type'] = 'Sparkling'
                    elif wine_type_id == 4: wine_data['wine_type'] = 'Rosé'
                    elif wine_type_id == 7: wine_data['wine_type'] = 'Dessert'
                    elif wine_type_id == 24: wine_data['wine_type'] = 'Fortified'
                    if wine_data['wine_type']:
                         logger.debug(f"Found Wine Type from __PRELOADED_STATE__: {wine_data['wine_type']}")

                if wine_data['alcohol_percent'] is None:
                    alcohol = vintage_info.get('wine_facts', {}).get('alcohol') or vintage_info.get('alcohol')
                    if alcohol:
                        try:
                            wine_data['alcohol_percent'] = float(alcohol)
                            logger.debug(f"Found Alcohol Percentage from __PRELOADED_STATE__: {wine_data['alcohol_percent']}%")
                        except (ValueError, TypeError):
                            logger.debug("Could not parse alcohol percentage from __PRELOADED_STATE__.")

            except json.JSONDecodeError:
                logger.warning("Failed to decode __PRELOADED_STATE__ JSON.")
    
    script_tags = soup.find_all('script', type='application/ld+json')
    for script in script_tags:
        try:
            json_ld = json.loads(script.string)
            if isinstance(json_ld, dict):
                is_product = json_ld.get('@type') == 'Product'
                is_wine = json_ld.get('@type') == 'Wine'
                if is_product:
                    if 'aggregateRating' in json_ld and wine_data['vivino_rating'] is None:
                        try: wine_data['vivino_rating'] = float(str(json_ld['aggregateRating'].get('ratingValue')).replace(',', '.'))
                        except (ValueError, TypeError, AttributeError): pass
                
                grape_source = None
                if is_product and 'containsWine' in json_ld and isinstance(json_ld['containsWine'], dict) and 'grape' in json_ld['containsWine']:
                    grape_source = json_ld['containsWine']['grape']
                elif is_wine and 'grape' in json_ld:
                    grape_source = json_ld['grape']

                if grape_source:
                    found_grapes_in_json = True
                    if isinstance(grape_source, list): all_grape_names_collected.extend([g['name'] for g in grape_source if g and 'name' in g])
                    elif isinstance(grape_source, dict) and 'name' in grape_source: all_grape_names_collected.append(grape_source['name'].strip())

                if is_wine:
                    if wine_data['vintage'] is None and 'vintage' in json_ld:
                        try: wine_data['vintage'] = int(json_ld['vintage'])
                        except (ValueError, TypeError): pass
        except (json.JSONDecodeError, KeyError, TypeError) as json_err:
            logger.debug(f"Vivino JSON-LD parsing error (may be benign): {json_err}")
            pass

    # Fallback 1: Preload link
    if wine_data['image_url'] is None:
        preload_link = soup.find('link', rel='preload', attrs={'as': 'image'})
        if preload_link and preload_link.has_attr('href'):
            wine_data['image_url'] = preload_link['href']
            logger.debug(f"Found Image URL from preload link: {wine_data['image_url']}")


    # Fallback 2: Regular img tag
    if wine_data['image_url'] is None:
        image_tag = soup.find('img', class_=re.compile(r'wine-page-image__image|vivinoImage_image|image-preview__image'))
        if image_tag:
            wine_data['image_url'] = image_tag.get('src') or image_tag.get('data-src')
            logger.debug(f"Found Image URL from img tag: {wine_data['image_url']}")


    if wine_data['image_url'] and wine_data['image_url'].startswith('//'):
        wine_data['image_url'] = 'https:' + wine_data['image_url']
            
    if wine_data['vintage'] is None:
        match = re.search(r'\b(19\d{2}|20\d{2})\b', wine_data['name'])
        if match:
            try:
                wine_data['vintage'] = int(match.group(0))
                wine_data['name'] = " ".join(wine_data['name'].replace(match.group(0), '').strip().split())
            except ValueError: pass

    if wine_data['vintage'] is None:
        vintage_span = soup.find('span', class_='vintage')
        if vintage_span:
            match = re.search(r'\b(19\d{2}|20\d{2})\b', vintage_span.text)
            if match:
                try: wine_data['vintage'] = int(match.group(0))
                except ValueError: pass
    
    # This is the old, less reliable fallback. We keep it just in case JSON fails.
    for link in soup.find_all('a', href=re.compile(r'/(wine-countries|wine-regions|grapes)/')):
        href = link.get('href', '')
        text = link.get_text(strip=True).strip()
        if '/wine-countries/' in href and wine_data['country'] == 'Unknown Country': 
            wine_data['country'] = text
            logger.debug(f"Found Country from fallback <a> tag: {text}")
        elif '/wine-regions/' in href and wine_data['region'] == 'Unknown Region': 
            wine_data['region'] = text
            logger.debug(f"Found Region from fallback <a> tag: {text}")
        elif not found_grapes_in_json and '/grapes/' in href and text and 'blend' not in text.lower(): all_grape_names_collected.append(text)
    
    # Fallback for Wine Type from breadcrumbs
    if wine_data['wine_type'] is None:
        try:
            # Try to find breadcrumbs
            breadcrumbs = soup.find('div', class_=re.compile(r'breadCrumbs'))
            if breadcrumbs:
                breadcrumb_links = breadcrumbs.find_all('a')
                for link in breadcrumb_links:
                    link_text = link.get_text(strip=True)
                    # Check for wine types
                    if any(wt in link_text for wt in WINE_TYPES):
                         for wt in WINE_TYPES:
                             if wt in link_text:
                                 wine_data['wine_type'] = wt
                                 logger.debug(f"Found Wine Type from breadcrumbs: {wt}")
                                 break
                    if wine_data['wine_type']:
                        break
        except Exception as e:
            logger.debug(f"Could not parse wine type from breadcrumbs (non-critical): {e}")

    # Fallback for Alcohol Percentage
    if wine_data['alcohol_percent'] is None:
        try:
            label_header = soup.find(['th', 'div'], string=re.compile(r'Alcohol content', re.I))
            if label_header:
                value_cell = label_header.find_next_sibling(['td', 'div'])
                if value_cell:
                    match = re.search(r'(\d{1,2}(\.\d{1,2})?)\s*%', value_cell.get_text())
                    if match:
                        wine_data['alcohol_percent'] = float(match.group(1))
                        logger.debug(f"Found Alcohol Percentage from facts table: {wine_data['alcohol_percent']}%")
        except Exception as e:
            logger.debug(f"Could not parse alcohol percentage from facts table (non-critical): {e}")

    # --- START REFACTOR ---
    # Varietal processing is MOVED to scrape_vivino_url() so it can access region.yaml hints.
    # We will just collect and store the raw grape list here.
    
    raw_grapes = []
    if all_grape_names_collected or 'Unknown Wine' not in wine_data['name']:
        cleaned_grapes = [g.strip() for g in all_grape_names_collected if g.strip().lower() not in ['wine']]
        raw_grapes = list(dict.fromkeys(cleaned_grapes))
    
    wine_data['raw_grapes'] = raw_grapes
    # --- END REFACTOR ---

    if wine_data['vivino_rating'] is None:
        rating_tag = soup.find('div', class_=re.compile(r'vivinoRating_averageValue|community-score__score'))
        if rating_tag:
            try: wine_data['vivino_rating'] = float(rating_tag.text.strip().replace(',', '.'))
            except (ValueError, TypeError): pass

    return wine_data, final_url_after_scrape

def _collect_hints(data_dict: dict, collected: dict):
    """Helper to recursively merge hints, with deeper hints overwriting."""
    if isinstance(data_dict, dict):
        if "hints" in data_dict and isinstance(data_dict["hints"], dict):
            # Merge/overwrite hints from this level
            for key, value in data_dict["hints"].items():
                if key not in collected:
                    collected[key] = value
                # This simple merge works for bank_type, etc.
                # For dict hints like varietal_name_override, we need to merge the dicts
                elif isinstance(value, dict) and isinstance(collected[key], dict):
                    collected[key].update(value)
                else:
                    # Deeper hint overwrites shallower one
                    collected[key] = value
    return collected

def _normalize_name(name: str):
    """
    Cleans a string by removing spaces and hyphens for a robust comparison.
    Converts to lowercase.
    """
    if not name:
        return ""
    # Remove spaces and hyphens, then convert to lowercase
    return name.lower().replace(" ", "").replace("-", "")

def normalize_region_name(region_name):
    """
    Normalizes a region name by stripping common, redundant
    AVA/appellation suffixes from the end of the string.
    """
    if not region_name:
        return region_name

    normalized_name = region_name.strip()
    
    # Regex to match common suffixes (with optional preceding hyphen or space)
    suffixes_pattern = (
        r'\s*The Rocks District of Milton-Freewater'
        r'|\s*District—Lake County'
        r'|\s*District'
        r'|\s*AVA'
        r'|\s*Appellation'
        r'|\s*Zone'
        r'|\s*County'
        r'|\s*I\.G\.T\.'  # Italy: Indicazione Geografica Tipica
        r'|\s*D\.O\.C\.'  # Italy: Denominazione di Origine Controllata
        r'|\s*D\.O\.C\.G\.' # Italy: Denominazione di Origine Controllata e Garantita
        r'|\s*Classico' 
        r'|\s*Superiore'
    )
    
    # Use re.sub to remove the pattern from the end of the string, ignoring case
    # The $ anchor ensures we only match at the end.
    normalized_name = re.sub(
        f'({suffixes_pattern})$',
        '',
        normalized_name,
        flags=re.IGNORECASE
    ).strip()
    
    return normalized_name

def _check_pipe_match(scraped_normalized_name, region_name_from_yaml, _normalize_name_func):
    """
    Checks if a normalized scraped name matches a YAML entry, 
    supporting the 'Base |Suffix' syntax for optional suffixes.
    
    Args:
        scraped_normalized_name (str): The hyphen/space-stripped scraped name (e.g., 'napa').
        region_name_from_yaml (str): The name read from YAML (e.g., 'Napa |Valley').
        _normalize_name_func (function): Reference to your existing _normalize_name function.
        
    Returns:
        tuple: (bool: True if matched, str: the full canonical name if matched)
    """
    if '|' in region_name_from_yaml:
        # Handle 'Base |Suffix' logic (e.g., 'Napa |Valley')
        parts = region_name_from_yaml.split('|', 1)
        base_name = parts[0].strip()
        suffix = parts[1].strip()
        
        # 1. Full Canonical Name (Napa Valley)
        full_canonical_name = f"{base_name} {suffix}".strip()
        full_normalized = _normalize_name_func(full_canonical_name)

        # 2. Base Name Only (Napa)
        base_normalized = _normalize_name_func(base_name)

        if scraped_normalized_name == full_normalized:
            return True, full_canonical_name
        
        if scraped_normalized_name == base_normalized:
            # Match found via short-form, but return the full canonical name
            return True, full_canonical_name
            
        return False, None
    else:
        # Handle standard name with no pipe (e.g., 'Stags Leap' or existing 'Napa Valley')
        yaml_normalized = _normalize_name_func(region_name_from_yaml)
        if scraped_normalized_name == yaml_normalized:
            # For non-pipe entries, the canonical name is the YAML entry itself
            return True, region_name_from_yaml
            
        return False, None

def match_region(scraped_region: str, scraped_country: str = None):
    """
    Attempts to find the best matching region/subregion/country
    for a scraped Vivino region name using REGION_DATA.
    
    Supports nested YAML format:
    Country → regions → subregions → subsubregions

    Returns a dict:
      {"country": ..., "region": ..., "subregion": ..., "subsubregion": ..., "hints": {...}}
    """
    if not scraped_region:
        return None
        
    # NOTE: You must ensure _normalize_name is defined and accessible here.
    region_clean_norm = _normalize_name(scraped_region)
    region_clean = scraped_region.strip().lower()
    
    # Default match object now includes a hints dictionary
    match = {"country": None, "region": None, "subregion": None, "subsubregion": None, "hints": {}}

    # Step 1: Focus search if country hint provided
    if scraped_country and scraped_country in REGION_DATA:
        countries_to_search = {scraped_country: REGION_DATA[scraped_country]}
    else:
        countries_to_search = REGION_DATA

    # Step 2: Traverse nested structure
    for country, country_data in countries_to_search.items():
        # --- HINT LOGIC: Collect hints from Country level ---
        _collect_hints(country_data, match["hints"])

        regions = country_data.get("regions", {})
        for region_name, region_data in regions.items():
            
            # ------------------------------------------------------------------
            # Level 1: region (e.g., California, Bordeaux)
            # Use pipe match logic for robustness, though rare at this level.
            is_match, canonical_region_name = _check_pipe_match(
                region_clean_norm, region_name, _normalize_name
            )
            
            if is_match:
                match.update({"country": country, "region": canonical_region_name})
                # --- HINT LOGIC: Collect hints from Region level ---
                _collect_hints(region_data, match["hints"])
                return match
            # ------------------------------------------------------------------

            subregions = region_data.get("subregions", {})
            for subregion_name, subregion_data in subregions.items():
                
                # ------------------------------------------------------------------
                # Level 2: subregion (e.g., Napa |Valley, Barossa |Valley)
                is_match, canonical_subregion_name = _check_pipe_match(
                    region_clean_norm, subregion_name, _normalize_name
                )
                
                if is_match:
                    match.update({
                        "country": country,
                        "region": region_name,
                        "subregion": canonical_subregion_name # Use canonical name
                    })
                    # --- HINT LOGIC: Collect hints from Region AND Subregion level ---
                    _collect_hints(region_data, match["hints"])
                    _collect_hints(subregion_data, match["hints"])
                    return match
                # ------------------------------------------------------------------

                subsubs = subregion_data.get("subsubregions", [])
                for subsub_name in subsubs:
                    
                    # ------------------------------------------------------------------
                    # Level 3: subsubregion (list items, e.g., Russian River |Valley)
                    is_match, canonical_subsub_name = _check_pipe_match(
                        region_clean_norm, subsub_name, _normalize_name
                    )

                    if is_match:
                        match.update({
                            "country": country,
                            "region": region_name,
                            "subregion": subregion_name,
                            "subsubregion": canonical_subsub_name # Use canonical name
                        })
                        # --- HINT LOGIC: Collect hints from all levels ---
                        _collect_hints(region_data, match["hints"])
                        _collect_hints(subregion_data, match["hints"])
                        # (subsubregions are a list, so no hints)
                        return match
                    # ------------------------------------------------------------------

    logger.debug(f"No region match for '{region_clean}' in nested YAML under countries: {list(countries_to_search.keys())[:5]}")
    # Return match with only country-level hints if no region was found
    if match["country"] is None and scraped_country and scraped_country in REGION_DATA:
        match["country"] = scraped_country
    
    return match if match.get("region") else None

def strip_pipe_suffix(region_name: str) -> str:
    """Removes the '|Suffix' used for region matching aliases."""
    if not region_name:
        return ""
    # Find the pipe, and take everything before it.
    if '|' in region_name:
        return region_name.split('|')[0].strip()
    return region_name.strip()

def scrape_vivino_url(vivino_url):
    """
    Orchestrates scraping using a headless browser to be resilient to anti-bot measures.
    """
    logger.info(f"Starting Selenium-based scrape for: {vivino_url}")

    # --- Phase 1: Pre-scrape region hint from URL ---
    region_hint = _region_hint_from_url(vivino_url)
    if region_hint:
        logger.debug(f"URL region hint detected: {region_hint}")

    wine_data, canonical_url = _perform_scrape_attempt_selenium(vivino_url)
    if not canonical_url:
        canonical_url = vivino_url

    # --- Apply URL hint if scrape has no region/country ---
    if wine_data and region_hint:
        if not wine_data.get("region"):
            wine_data["region"] = (
                region_hint.get("subsubregion")
                or region_hint.get("subregion")
                or region_hint.get("region")
            )
        if not wine_data.get("country"):
            wine_data["country"] = region_hint.get("country")

    # --- Region normalization using region.yaml ---
    region_hints = {} # Initialize hints dict

    if wine_data and wine_data.get("region"):
        # NEW: Apply suffix-stripping normalization first
        raw_region = wine_data.get("region")
        wine_data["region"] = normalize_region_name(raw_region)
        logger.debug(f"Suffix-stripped region name from '{raw_region}' to '{wine_data['region']}'")
        
        region = wine_data.get("region")
        country = wine_data.get("country")
        region_info = match_region(region, country)
        
        # --- Store hints for varietal processing ---
        if region_info:
            region_hints = region_info.get("hints", {})
            display_region = (
                region_info.get("subsubregion")
                or region_info.get("subregion")
                or region_info.get("region")
            )
            display_country = region_info.get("country")

            parts = [
                region_info.get("subsubregion"),
                region_info.get("subregion"),
                strip_pipe_suffix(region_info.get("region")),
            ]
            region_full = " – ".join([p for p in parts if p])

            if display_country:
                country_obj = REGION_DATA.get(display_country, {})
                country_code = country_obj.get("code", display_country[:2].upper())
                region_full = f"{region_full} – {country_code}"

            wine_data["region"] = display_region
            wine_data["country"] = display_country
            wine_data["region_full"] = region_full

            logger.debug(f"Region normalized via region.yaml: {region_info}")
            logger.debug(f"Derived display_region='{display_region}', region_full='{region_full}'")
        else:
            logger.debug(f"No region match found for '{region}' — using raw scraped values.")
            # --- NEW: Fallback to get country hints even if region fails ---
            if country and country in REGION_DATA:
                country_data = REGION_DATA[country]
                _collect_hints(country_data, region_hints)
                logger.debug(f"Collected fallback country hints for {country}: {region_hints}")

    # --- Varietal processing logic moved here ---
    raw_grapes = wine_data.pop('raw_grapes', [])
    if raw_grapes or 'Unknown Wine' not in wine_data['name']:
        unique_grapes_ordered = raw_grapes # Start with the raw list
        name_lower = wine_data['name'].lower()
        found_grapes_lower = {g.lower() for g in unique_grapes_ordered}
        for grape_lower in GLOBAL_GRAPE_VARIETALS: 
            if grape_lower not in found_grapes_lower:
                if re.search(r'\b' + re.escape(grape_lower) + r'\b', name_lower):
                    capitalized_grape = grape_lower.title() 
                    unique_grapes_ordered.append(capitalized_grape)
                    found_grapes_lower.add(grape_lower)                
                    logger.debug(f"Augmented grape list with '{capitalized_grape}' from wine name.")
        
        # --- Apply Regional Blend Order Heuristics ---
        bordeaux_bank = region_hints.get('bank_type')
        rhone_style = region_hints.get('rhone_style')
        blend_style = region_hints.get('blend_style') # <-- 1. ADD THIS

        if bordeaux_bank:
            logger.debug(f"Applying Bordeaux blend override for {bordeaux_bank}.")
            
            # Define the dominant varietals for the region
            if bordeaux_bank == 'Left Bank':
                priority_list = ['Cabernet Sauvignon', 'Merlot', 'Cabernet Franc', 'Petit Verdot']
            elif bordeaux_bank == 'Right Bank':
                priority_list = ['Merlot', 'Cabernet Franc', 'Cabernet Sauvignon']
            else:
                priority_list = []
        
        elif rhone_style:
            logger.debug(f"Applying Rhône blend override for {rhone_style}.")
            if rhone_style == 'North':
                # Northern Rhône is Syrah-dominant (sometimes with Viognier)
                priority_list = ['Syrah', 'Viognier', 'Marsanne', 'Roussanne']
            elif rhone_style == 'South':
                # Southern Rhône is Grenache-dominant (GSM blends)
                priority_list = ['Grenache', 'Syrah', 'Mourvèdre', 'Cinsault', 'Counoise']
            else:
                priority_list = []
        
        elif blend_style: # <-- 2. ADD THIS BLOCK
            logger.debug(f"Applying regional blend_style override for {blend_style}.")
            if blend_style == 'Valpolicella':
                priority_list = ['Corvina', 'Corvinone', 'Rondinella', 'Molinara']
            elif blend_style == 'Rioja Red':
                priority_list = ['Tempranillo', 'Garnacha', 'Graciano', 'Mazuelo']
            else:
                priority_list = []

        else:
            priority_list = []

        if priority_list:
            new_order = []
            # 2a. Iterate through the regional priority list and place them first
            for grape in priority_list:
                grape_in_list = next((g for g in unique_grapes_ordered if g.lower() == grape.lower()), None)
                if grape_in_list and grape_in_list not in new_order:
                    new_order.append(grape_in_list)
            
            # 2b. Add all remaining grapes (preserving their original relative order)
            for grape in unique_grapes_ordered:
                if grape not in new_order:
                    new_order.append(grape)
                    
            unique_grapes_ordered = new_order
        
        # 3. Sort by position in name (was step 2)
        grapes_in_name = []
        for grape in unique_grapes_ordered:
            match = re.search(r'\b' + re.escape(grape.lower()) + r'\b', name_lower)
            if match:
                grapes_in_name.append({'name': grape, 'pos': match.start()})
        
        if grapes_in_name:
            grapes_in_name.sort(key=lambda x: x['pos'])
            prioritized_grapes = [g['name'] for g in grapes_in_name]
            remaining_grapes = [g for g in unique_grapes_ordered if g not in prioritized_grapes]
            unique_grapes_ordered = prioritized_grapes + remaining_grapes
        
        # --- NEW HINT-BASED SYRAH/SHIRAZ LOGIC ---
        
        # 4. Determine the correct term for Syrah/Shiraz (was step 3)
        preferred_syrah_term = None
        
        # A. Check name first (most specific)
        if 'shiraz' in name_lower:
            preferred_syrah_term = 'Shiraz'
        elif 'syrah' in name_lower:
            preferred_syrah_term = 'Syrah'
        
        # B. If not in name, check region.yaml hints
        if not preferred_syrah_term:
            override_hints = region_hints.get('varietal_name_override', {})
            if 'Syrah' in override_hints: # e.g., {'Syrah': 'Shiraz'}
                preferred_syrah_term = override_hints['Syrah']
            elif 'Shiraz' in override_hints: # e.g., {'Shiraz': 'Syrah'}
                preferred_syrah_term = override_hints['Shiraz']

        # C. If no hint, default to 'Syrah'
        if not preferred_syrah_term:
            preferred_syrah_term = 'Syrah' # This is our new default
            
        # 5. Apply the final term (was step 4)
        final_grapes = []
        for grape in unique_grapes_ordered:
            is_syrah_family = 'syrah' in grape.lower() or 'shiraz' in grape.lower()
            if not is_syrah_family:
                final_grapes.append(grape)
                continue
            
            # Add the correct term, but only once
            if preferred_syrah_term not in final_grapes:
                final_grapes.append(preferred_syrah_term)

        if final_grapes:
             wine_data['varietal'] = ", ".join(final_grapes)
        elif not raw_grapes:
             # If no grapes were found, keep the default
             wine_data['varietal'] = 'Unknown Varietal'

    # --- END REFACTOR ---

    # --- Handle fallback or failure ---
    if wine_data:
        logger.info(f"Success on initial Selenium scrape for {canonical_url}")
        return wine_data, canonical_url

    logger.warning(f"Initial Selenium scrape failed for {canonical_url}. Cooling down before checking nearby vintages.")
    time.sleep(random.uniform(3.0, 5.0))

    # --- (rest of your vintage and fallback logic unchanged) ---

    logger.warning("All scrape attempts failed. Attempting to parse URL for final fallback data.")
    fallback_data = _parse_url_for_fallback_data(vivino_url)

    # --- Phase 1: Fallback region normalization ---
    if fallback_data and fallback_data.get("region"):
        # NEW: Apply suffix-stripping normalization first
        raw_region = fallback_data.get("region")
        fallback_data["region"] = normalize_region_name(raw_region)
        logger.debug(f"Fallback suffix-stripped region name from '{raw_region}' to '{fallback_data['region']}'")

        region_hint = match_region(fallback_data.get("region"), fallback_data.get("country"))
        if region_hint:
            fallback_data["country"] = region_hint.get("country")
            fallback_data["region"] = (
                region_hint.get("subsubregion")
                or region_hint.get("subregion")
                or region_hint.get("region")
            )
            logger.debug(f"Fallback region normalized via region.yaml: {region_hint}")

    if fallback_data and 'Vivino Wine ID' not in fallback_data.get('name', ''):
        minimal_data = {
            'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal',
            'region': 'Unknown Region', 'country': 'Unknown Country',
            'vivino_rating': None, 'image_url': None,
            'alcohol_percent': None, 'wine_type': None,
            'needs_review': True
        }
        minimal_data.update(fallback_data)
        logger.warning(f"Full scrape failed, returning partial data from URL for review: {fallback_data.get('name')}")
        return minimal_data, vivino_url

    logger.error(f"All scrape and fallback attempts failed for {vivino_url}.")
    return None, None

