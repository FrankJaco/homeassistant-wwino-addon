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
logger.setLevel(logging.INFO) # Set default logging level

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
    """
    (Placeholder) Extracts a region hint from the Vivino URL path segments.
    Used to focus the region matching when scraped data is ambiguous.
    """
    try:
        parsed = urlparse(vivino_url)
        path_segments = parsed.path.strip('/').split('/')
        if len(path_segments) >= 2 and path_segments[0] == 'wines':
            # This logic is complex and environment-specific, stubbing for now.
            return None
    except Exception:
        logger.debug("Failed to parse URL for region hint.")
    return None

def _parse_url_for_fallback_data(url: str):
    """
    (Placeholder) Parses the URL path segments to extract minimal wine data 
    (name, region, vintage) for extreme fallback cases where the full scrape fails.
    """
    try:
        parsed_url = urlparse(url)
        path = parsed_url.path
        if '/wines/' in path:
            parts = path.split('/')
            # Filter out empty strings and 'wines'
            clean_parts = [p for p in parts if p and p != 'wines']
            
            if clean_parts:
                slug = clean_parts[-1]
                
                # Attempt to extract vintage (four digits at the end)
                vintage_match = re.search(r'-(\d{4})(?:-\d+)?$', slug)
                vintage = vintage_match.group(1) if vintage_match else None
                
                # Assume second-to-last part is region (e.g., bordeaux)
                region = clean_parts[-2].replace('-', ' ').title() if len(clean_parts) >= 2 else 'Unknown Region'
                
                # Clean up slug for name
                name = slug.rsplit('-', 1)[0]
                name = name.replace('-', ' ').title()
                
                return {
                    'name': name,
                    'vintage': vintage,
                    'region': region,
                    'country': 'Unknown Country', # Cannot reliably determine country from URL path alone
                }
    except Exception as e:
        logger.debug(f"Error during URL fallback parsing: {e}")
        return None
    return None

def _perform_scrape_attempt_selenium(url: str):
    """
    Performs a single, complete scrape attempt using a headless Chrome browser.
    """
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    options.add_argument('--blink-settings=imagesEnabled=false') # Speed up page load
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = None
    wine_data = {
        'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal',
        'region': 'Unknown Region', 'country': 'Unknown Country',
        'vivino_rating': None, 'image_url': None,
        'alcohol_percent': None, 'wine_type': None,
        'needs_review': False # Default to false, set to true on failure or ambiguity
    }
    final_url_after_scrape = url
    
    try:
        driver = webdriver.Chrome(options=options)
        logger.debug(f"Starting Selenium for URL: {url}")
        driver.get(url)
        
        # Wait for the main wine name element to load, or timeout after 15 seconds
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.winePageHeader__wineryAndWineNameContainer--2wK4O, .wine-page-header__winery-and-wine-name-container'))
        )
        
        final_url_after_scrape = driver.current_url
        
        # Parse the page source with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # --- Basic Wine Name and Vintage ---
        name_tag = soup.find('h1', class_=re.compile(r'winePageHeader__wineName|wine-page-header__wine-name'))
        vintage_tag = soup.find('div', class_=re.compile(r'winePageHeader__vintage|wine-page-header__vintage'))

        if name_tag:
            wine_name = " ".join(name_tag.text.strip().split())
            wine_data['name'] = wine_name
        
        if vintage_tag:
            vintage = vintage_tag.text.strip()
            # Clean up the vintage string, often just a 4-digit year
            vintage_match = re.search(r'(\d{4})', vintage)
            wine_data['vintage'] = vintage_match.group(1) if vintage_match else None
        
        if wine_data['name'] == 'Unknown Wine':
            logger.warning(f"Could not find primary wine name tag for {url}")
            return None, final_url_after_scrape

        # --- Region and Country ---
        # Find the breadcrumbs or the region link
        region_link = soup.find('a', class_=re.compile(r'winePageHeader__wineInfoLink|wine-page-header__wine-info-link'), href=re.compile(r'/regions/'))
        
        if region_link:
            path_parts = region_link['href'].strip('/').split('/')
            if len(path_parts) > 1 and path_parts[0] == 'regions':
                # The last part is usually the region name slug, or the second to last is the country
                # We'll use the link text for a clean name and the link structure for hints
                wine_data['region'] = region_link.text.strip()
                
                # Try to infer country from the URL structure or a separate element
                # Vivino often has a separate country link or is embedded in breadcrumbs
                country_tag = soup.find('a', class_=re.compile(r'winePageHeader__country|wine-page-header__country-link'))
                if country_tag:
                    wine_data['country'] = country_tag.text.strip()
                else:
                    # Fallback to path if no country tag is found (e.g., /regions/france)
                    if len(path_parts) > 1:
                        country_slug = path_parts[1].replace('-', ' ').title()
                        wine_data['country'] = country_slug

        # --- Image URL ---
        img_tag = soup.find('img', class_=re.compile(r'image-placeholder|winePageHeader__bottle|wine-image__image'))
        if img_tag and img_tag.get('src'):
            wine_data['image_url'] = img_tag['src'].strip()

        # --- Extract Varietals and Type from JSON/Script Data ---
        script_tags = soup.find_all('script', type='application/ld+json')
        all_grape_names_collected = []
        is_wine = False
        found_grapes_in_json = False

        for script in script_tags:
            try:
                data = json.loads(script.string)
                
                if isinstance(data, dict):
                    if data.get('@type') == 'Product' and data.get('name') == wine_data['name']:
                        is_wine = True
                        # Try to get type (e.g., "Red Wine")
                        description = data.get('description', '')
                        for wine_type in WINE_TYPES:
                            if wine_type in description:
                                wine_data['wine_type'] = wine_type
                                break

                        # Try to get varietals from product data (often nested)
                        grape_source = data.get('recipeIngredient') or data.get('aggregateRating', {}).get('reviewAspect')
                        if grape_source:
                            found_grapes_in_json = True
                            if isinstance(grape_source, list): all_grape_names_collected.extend([g['name'] for g in grape_source if g and 'name' in g])
                        
                    elif isinstance(data, list):
                        # Sometimes the main product data is an array
                        for item in data:
                            if item.get('@type') == 'Product' and item.get('name') == wine_data['name']:
                                is_wine = True
                                grape_source = item.get('recipeIngredient') or item.get('aggregateRating', {}).get('reviewAspect')
                                if grape_source:
                                    found_grapes_in_json = True
                                    if isinstance(grape_source, list): all_grape_names_collected.extend([g['name'] for g in grape_source if g and 'name' in g])
                                elif isinstance(grape_source, dict) and 'name' in grape_source: all_grape_names_collected.append(grape_source['name'].strip())

                if is_wine:
                    # Also check microdata for other attributes
                    # This section is highly dependent on Vivino's ever-changing structure
                    pass # Placeholder for further JSON scraping

            except json.JSONDecodeError:
                continue # Skip non-JSON or malformed script tags
            except Exception as e:
                logger.debug(f"Error processing JSON-LD script tag: {e}")

        # --- Fallback Varietals from Links ---
        # Search for links that look like varietal links
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '').lower()
            text = a_tag.text.strip()
            if text and '/grapes/' in href and not found_grapes_in_json and 'blend' not in text.lower():
                 all_grape_names_collected.append(text)
        
        # If the image URL is schema-relative, make it absolute
        if wine_data['image_url'] and wine_data['image_url'].startswith('//'):
            wine_data['image_url'] = 'https:' + wine_data['image_url']
            
        # Fallback for Wine Type from breadcrumbs
        if not wine_data['wine_type']:
            try:
                type_tag = soup.find('a', class_=re.compile(r'winePageHeader__wineInfoLink|wine-page-header__wine-info-link'), href=re.compile(r'/wines/\w+$'))
                if type_tag:
                    type_text = type_tag.text.strip()
                    for w_type in WINE_TYPES:
                        if w_type.lower() in type_text.lower():
                            wine_data['wine_type'] = w_type
                            break
            except Exception as e:
                logger.debug(f"Could not parse wine type from breadcrumbs (non-critical): {e}")

        # Fallback for Alcohol Percentage
        if not wine_data['alcohol_percent']:
            try:
                facts_container = soup.find('div', class_=re.compile(r'wineFacts__factsList|wine-facts__facts-list'))
                if facts_container:
                    # Look for alcohol/alc within the facts table
                    alcohol_tag = facts_container.find('div', text=re.compile(r'Alcohol|Alc\.', re.IGNORECASE))
                    if alcohol_tag:
                        # Value is often in the sibling/next element
                        value_tag = alcohol_tag.find_next_sibling()
                        if value_tag:
                            alcohol_text = value_tag.text.strip()
                            percent_match = re.search(r'(\d{1,2}(?:[.,]\d{1,2})?)\s*%', alcohol_text)
                            if percent_match:
                                wine_data['alcohol_percent'] = float(percent_match.group(1).replace(',', '.'))
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

        # Fallback for Vivino Rating
        if wine_data['vivino_rating'] is None:
            rating_tag = soup.find('div', class_=re.compile(r'vivinoRating_averageValue|community-score__score'))
            if rating_tag:
                try:
                    rating = float(rating_tag.text.strip().replace(',', '.'))
                    wine_data['vivino_rating'] = rating
                except ValueError:
                    logger.debug("Could not convert rating text to float.")

    except TimeoutException:
        logger.warning(f"Selenium Timeout (15s) for {url}. Page did not load completely.")
        wine_data['needs_review'] = True
    except WebDriverException as e:
        logger.error(f"WebDriver error for {url}: {e}")
        wine_data['needs_review'] = True
    except Exception as e:
        logger.error(f"An unexpected error occurred during Selenium scrape for {url}: {e}")
        wine_data['needs_review'] = True
    finally:
        if driver:
            driver.quit()

    return wine_data, final_url_after_scrape

def _collect_hints(data_dict: dict, collected: dict):
    """Helper to recursively merge hints, with deeper hints overwriting."""
    if isinstance(data_dict, dict):
        if "hints" in data_dict and isinstance(data_dict["hints"], dict):
            # Merge/overwrite hints from this level
            for key, value in data_dict["hints"].items():
                if key not in collected:
                    collected[key] = value
                # For dict hints like varietal_name_override, we need to merge the dicts
                elif isinstance(value, dict) and isinstance(collected.get(key), dict):
                    collected[key].update(value)
                else:
                    # Deeper hint overwrites shallower one
                    collected[key] = value
    return collected


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
            # Level 1: region
            if region_clean == region_name.lower():
                match.update({"country": country, "region": region_name})
                # --- HINT LOGIC: Collect hints from Region level ---
                _collect_hints(region_data, match["hints"])
                return match

            subregions = region_data.get("subregions", {})
            for subregion_name, subregion_data in subregions.items():
                # Level 2: subregion
                if region_clean == subregion_name.lower():
                    match.update({
                        "country": country,
                        "region": region_name,
                        "subregion": subregion_name
                    })
                    # --- HINT LOGIC: Collect hints from Region AND Subregion level ---
                    _collect_hints(region_data, match["hints"]) # Region level
                    _collect_hints(subregion_data, match["hints"]) # Subregion level
                    return match

                subsubs = subregion_data.get("subsubregions", [])
                for subsub in subsubs:
                    # Level 3: subsubregion
                    if region_clean == subsub.lower():
                        match.update({
                            "country": country,
                            "region": region_name,
                            "subregion": subregion_name,
                            "subsubregion": subsub
                        })
                        # --- HINT LOGIC: Collect hints from all levels ---
                        _collect_hints(region_data, match["hints"]) # Region
                        _collect_hints(subregion_data, match["hints"]) # Subregion
                        # (subsubregions are a list, so no hints)
                        return match

    logger.debug(f"No region match for '{region_clean}' in nested YAML under countries: {list(countries_to_search.keys())[:5]}")
    # Return match with only country-level hints if no region was found
    if match["country"] is None and scraped_country and scraped_country in REGION_DATA:
        # Re-collect country hints, as the previous loop iterations might have overwritten them 
        # based on failed region matches (though _collect_hints handles overwrites from deeper levels)
        country_data = REGION_DATA[scraped_country]
        country_hints = {}
        _collect_hints(country_data, country_hints)
        match["hints"] = country_hints # Overwrite hints with just country hints
        match["country"] = scraped_country
    
    return match if match.get("region") or match.get("country") else None


def scrape_vivino_url(vivino_url):
    """
    Main function to scrape a single Vivino URL using Selenium and apply
    post-processing (region and varietal normalization).
    """
    
    wine_data, final_url = _perform_scrape_attempt_selenium(vivino_url)
    
    if not wine_data:
        logger.warning("All scrape attempts failed. Attempting to parse URL for final fallback data.")
        fallback_data = _parse_url_for_fallback_data(vivino_url)

        # --- Phase 1: Fallback region normalization ---
        if fallback_data and fallback_data.get("region"):
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
            return minimal_data
        
        # Final failure
        return {
            'name': 'Vivino Wine ID not found or unreachable', 'vintage': None, 'varietal': 'Unknown Varietal',
            'region': 'Unknown Region', 'country': 'Unknown Country',
            'vivino_rating': None, 'image_url': None,
            'alcohol_percent': None, 'wine_type': None,
            'needs_review': True
        }

    # --- Phase 2: Region normalization (if scraped data is available) ---
    region_hints = {}
    if wine_data and wine_data.get("region"):
        region = wine_data.get("region")
        country = wine_data.get("country")
        region_info = match_region(region, country)
        
        # --- NEW: Store hints for varietal processing ---
        if region_info:
            region_hints = region_info.get("hints", {})
            display_region = (
                region_info.get("subsubregion")
                or region_info.get("subregion")
                or region_info.get("region")
                or region
            )
            region_full = (
                region_info.get("subsubregion")
                or region_info.get("subregion")
                or region_info.get("region")
            )
            wine_data["region"] = display_region
            wine_data["country"] = region_info.get("country")
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


    # --- Phase 3: Varietal processing (Moved from scrape attempt) ---
    raw_grapes = wine_data.pop('raw_grapes', []) # Get raw grapes from scrape attempt
    if raw_grapes or 'Unknown Wine' not in wine_data['name']:
        unique_grapes_ordered = raw_grapes # Start with the raw list
        name_lower = wine_data['name'].lower()
        current_grapes_lower = {g.lower() for g in unique_grapes_ordered}
        
        # 1. Augment from wine name using GLOBAL_GRAPE_VARIETALS
        for grape_lower in GLOBAL_GRAPE_VARIETALS: 
            if grape_lower not in current_grapes_lower:
                # Use word boundary to prevent partial matches (e.g., 'pinot' matching 'pinot noir')
                if re.search(r'\b' + re.escape(grape_lower) + r'\b', name_lower):
                    capitalized_grape = grape_lower.title() 
                    unique_grapes_ordered.append(capitalized_grape)
                    current_grapes_lower.add(grape_lower)
                    logger.debug(f"Augmented grape list with '{capitalized_grape}' from wine name.")
        
        # 2. Sort by position in name
        grapes_in_name = []
        for grape in unique_grapes_ordered:
            match = re.search(r'\b' + re.escape(grape.lower()) + r'\b', name_lower)
            if match:
                grapes_in_name.append({'name': grape, 'pos': match.start()})
        
        if grapes_in_name:
            grapes_in_name.sort(key=lambda x: x['pos'])
            prioritized_grapes = [g['name'] for g in grapes_in_name]
            # Ensure we don't lose grapes that weren't found in the name (e.g., found in HTML but not name)
            remaining_grapes = [g for g in unique_grapes_ordered if g not in prioritized_grapes]
            unique_grapes_ordered = prioritized_grapes + remaining_grapes
        
        # 3. Determine the correct term for Syrah/Shiraz
        preferred_syrah_term = None
        
        # A. Check name first (most specific)
        if 'shiraz' in name_lower:
            preferred_syrah_term = 'Shiraz'
        elif 'syrah' in name_lower:
            preferred_syrah_term = 'Syrah'
        
        # B. If not in name, check region.yaml hints
        if not preferred_syrah_term:
            override_hints = region_hints.get('varietal_name_override', {})
            # Check for a specific override instruction
            if 'Syrah' in override_hints and override_hints['Syrah'].lower() == 'shiraz':
                preferred_syrah_term = 'Shiraz'
            elif 'Shiraz' in override_hints and override_hints['Shiraz'].lower() == 'syrah':
                preferred_syrah_term = 'Syrah'
            # Fallback check (less specific, used if the hint is just one of them)
            elif 'Syrah' in override_hints: 
                 preferred_syrah_term = override_hints['Syrah']
            elif 'Shiraz' in override_hints: 
                 preferred_syrah_term = override_hints['Shiraz']


        # C. If no hint, default to 'Syrah'
        if not preferred_syrah_term:
            preferred_syrah_term = 'Syrah' 
            
        # 4. Apply the final term
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

    # --- Handle final cleanup/failure check ---
    if wine_data['name'] == 'Unknown Wine' and not final_url.endswith('/wines'):
        logger.warning(f"Returning partial data due to 'Unknown Wine' name after scrape: {final_url}")
        wine_data['needs_review'] = True
    elif 'Unknown Varietal' in wine_data.get('varietal', '') and 'Unknown Wine' not in wine_data['name']:
        logger.warning(f"Wine scraped successfully but varietal is missing or ambiguous: {wine_data['name']}")
        wine_data['needs_review'] = True # Mark for review if key data is missing but scrape succeeded

    return wine_data
