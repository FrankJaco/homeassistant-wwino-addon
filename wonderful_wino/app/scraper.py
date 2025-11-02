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
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
]

# --- Varietal Management ---
# The hardcoded list is REMOVED and replaced with this empty variable.
_LOADED_GRAPE_VARIETALS = []

def initialize_varietals(varietals_list):
    """
    NEW: Initializes the module's grape varietals list from an external source (main.py).
    
    Args:
        varietals_list (list): A list of grape varietal strings (expected to be lowercase).
    """
    global _LOADED_GRAPE_VARIETALS
    _LOADED_GRAPE_VARIETALS = varietals_list
    logger.info(f"Scraper initialized with {len(_LOADED_GRAPE_VARIETALS)} grape varietals from YAML.")


def _search_for_varietal_match(name, varietal_keywords):
    """
    Searches the wine name and keywords for a matching grape varietal from the loaded list.
    
    Args:
        name (str): The full wine name.
        varietal_keywords (list): A list of varietal names/keywords extracted from the page.

    Returns:
        str: The most likely matching varietal name, or 'Unknown Varietal'.
    """
    name_lower = name.lower()
    
    # NOTE: This function now uses the globally available _LOADED_GRAPE_VARIETALS
    # 1. Search varietal_keywords first (most reliable)
    for keyword in varietal_keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in _LOADED_GRAPE_VARIETALS:
            return keyword
            
    # 2. Search wine name (more prone to false positives, but a good fallback)
    # Tokenize the name and check for single-word matches first
    name_words = re.findall(r'\b\w+\b', name_lower)
    for word in name_words:
        if word in _LOADED_GRAPE_VARIETALS:
            return word.title() # Return title-cased for presentation

    # 3. Check for multi-word matches in the wine name (e.g., 'Pinot Noir', 'Cabernet Franc')
    # This is less efficient, but catches varietals with spaces.
    for varietal in _LOADED_GRAPE_VARIETALS:
        if ' ' in varietal and varietal in name_lower:
            # Found a match, return the original title-cased name for presentation
            return varietal.title()

    # If all searches fail, return the first varietal keyword as a best guess, 
    # otherwise return the default unknown.
    if varietal_keywords:
        return varietal_keywords[0]
        
    return 'Unknown Varietal'
    
# --- WebDriver Setup ---
def _initialize_webdriver():
    """Initializes and returns a Selenium WebDriver instance with necessary options."""
    # Ensure the driver is installed and accessible in the environment
    chrome_options = Options()
    # These options are critical for running headless in a restricted environment
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    # Reduce logging for cleaner output
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        # Assumes chromedriver is in the PATH or accessible
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except WebDriverException as e:
        logger.error(f"WebDriver initialization failed. Is Chrome/Chromedriver installed and accessible? Error: {e}")
        return None

# --- Vivino URL Normalization and Utility ---
def is_non_wine_product(vivino_url):
    """Checks if the URL path indicates a non-wine product (e.g., cider, beer)."""
    parsed = urlparse(vivino_url)
    path_segments = parsed.path.lower().split('/')
    non_wine_indicators = ['cider', 'beer', 'spirit']
    return any(segment in path_segments for segment in non_wine_indicators)

def _normalize_vivino_url(url):
    """
    Normalizes a Vivino URL to its canonical form, ensuring it points to a specific wine 
    and removing tracking/query parameters that may cause issues.
    """
    # 1. Extract the base URL and path
    parsed_url = urlparse(url)
    
    # 2. Extract the Vivino wine ID and slug from the path
    # Expected format: /w/<wine-name-slug>/<wine-id>
    path_parts = [part for part in parsed_url.path.split('/') if part]
    
    # Check if the path looks like a wine page
    if 'w' not in path_parts or len(path_parts) < 2:
        logger.warning(f"URL does not appear to be a standard Vivino wine page: {url}")
        # If it's not standard, just return the original URL clean of common query strings
        query_params = parse_qs(parsed_url.query)
        # Keep only the 'year' parameter if it exists
        keep_query = {'year': query_params.get('year')[0]} if 'year' in query_params else {}
        return urlunparse(parsed_url._replace(query=urlencode(keep_query), fragment=''))
        
    wine_id = path_parts[-1]
    wine_slug = path_parts[-2]
    
    # Construct the canonical URL: https://www.vivino.com/w/wine-slug/wine-id
    canonical_url = f"https://www.vivino.com/w/{wine_slug}/{wine_id}"
    
    # 3. Handle the vintage/year parameter
    query_params = parse_qs(parsed_url.query)
    vintage_year = query_params.get('year')
    
    if vintage_year and vintage_year[0].isdigit():
        canonical_url += f"?year={vintage_year[0]}"
        
    return canonical_url

# --- Scraping Logic ---

def _scrape_with_selenium(vivino_url):
    """
    Scrapes a Vivino URL using Selenium to handle JavaScript rendering.
    
    Returns:
        tuple: (data_dict, vivino_url) or (None, None) if scraping fails.
    """
    driver = None
    try:
        driver = _initialize_webdriver()
        if not driver:
            return None, None

        logger.info(f"Attempting Selenium scrape for: {vivino_url}")
        driver.get(vivino_url)
        
        # Wait for the main wine card/details to load
        # Wait for the script tag containing the JSON-LD data which is often rendered
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//script[@type='application/ld+json']"))
        )

        # Get the page source after JS execution
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 1. Extract JSON-LD data (often contains rich, structured data)
        json_data = {}
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if data.get('@type') == 'Product' or data.get('@type') == 'WebPage':
                    json_data = data
                    break
            except json.JSONDecodeError:
                continue

        # 2. Extract specific elements if JSON-LD is insufficient (e.g., Vivino Rating)
        name_tag = soup.find('h1', class_='winePageHeader__title--3B7CD')
        name = name_tag.text.strip() if name_tag else 'Unknown Wine'
        
        rating_tag = soup.find('div', class_='vivinoRating__averageValue--1J_h3')
        vivino_rating = float(rating_tag.text.strip()) if rating_tag and rating_tag.text.strip() else None

        image_tag = soup.find('img', class_='winePageHeader__vintageImage--2_3gZ')
        image_url = image_tag.get('src') if image_tag and image_tag.get('src') else None
        
        # 3. Extract varietal keywords (from the 'About the Wine' section or similar)
        varietal_keywords = []
        # Look for the 'Grapes' section or similar structure
        try:
            # Find the element that contains the structure (often a table or list of facts)
            fact_rows = soup.find_all('div', class_='wineFacts__fact--2N_xY')
            for row in fact_rows:
                header = row.find('div', class_='wineFacts__factHeader--3V1wU')
                content = row.find('div', class_='wineFacts__factContent--3-3g8')
                if header and content and header.text.strip() == 'Grapes':
                    # Varietals are often comma-separated or in a list
                    varietal_keywords = [s.strip() for s in content.text.strip().split(',') if s.strip()]
                    break
        except Exception:
            # Fail silently on fact extraction if structure changes
            pass 
        
        # 4. Process and structure the extracted data
        # Use JSON-LD data where available, fallback to scraped data
        
        # Extract Region/Country from JSON-LD or fall back to general text parsing if needed
        region = 'Unknown Region'
        country = 'Unknown Country'
        if json_data.get('offers') and json_data['offers'].get('seller'):
            seller_data = json_data['offers']['seller']
            if seller_data.get('address'):
                region = seller_data['address'].get('addressLocality', region)
                country = seller_data['address'].get('addressCountry', country)
        
        # Fallback for country/region from the breadcrumbs or path
        if country == 'Unknown Country' or region == 'Unknown Region':
             # Try to find breadcrumbs
            breadcrumbs = soup.find_all('a', class_='breadcrumbs__link--1Uj9I')
            if breadcrumbs:
                # Often the last two breadcrumbs are Region and Country
                if len(breadcrumbs) >= 2:
                    country = breadcrumbs[-1].text.strip()
                    region = breadcrumbs[-2].text.strip()
                elif len(breadcrumbs) == 1:
                    country = breadcrumbs[-1].text.strip()

        # Extract vintage from the name or path
        vintage = re.search(r'(\d{4})', name)
        vintage = int(vintage.group(1)) if vintage else None
        
        # Extract wine type (Red, White, Sparkling, etc.)
        wine_type = 'Unknown'
        if json_data.get('description'):
            # Simple check for common types in the description/title
            desc_lower = json_data['description'].lower()
            if 'red wine' in desc_lower or 'red blend' in desc_lower: wine_type = 'Red'
            elif 'white wine' in desc_lower or 'white blend' in desc_lower: wine_type = 'White'
            elif 'sparkling' in desc_lower: wine_type = 'Sparkling'
            elif 'rosé' in desc_lower or 'rose wine' in desc_lower: wine_type = 'Rosé'
            elif 'dessert wine' in desc_lower: wine_type = 'Dessert'
            elif 'fortified wine' in desc_lower: wine_type = 'Fortified'
        
        # Extract Alcohol Percentage (often in the facts section)
        alcohol_percent = None
        for row in fact_rows:
            header = row.find('div', class_='wineFacts__factHeader--3V1wU')
            content = row.find('div', class_='wineFacts__factContent--3-3g8')
            if header and content and 'Alcohol' in header.text.strip():
                match = re.search(r'(\d{1,2}(?:\.\d{1,2})?)', content.text.strip())
                if match:
                    alcohol_percent = float(match.group(1))
                    break

        # Find the best varietal match using the externally loaded list
        varietal_match = _search_for_varietal_match(name, varietal_keywords)

        final_data = {
            'name': name,
            'vintage': vintage,
            'varietal': varietal_match,
            'region': region,
            'country': country,
            'vivino_rating': vivino_rating,
            'image_url': image_url,
            'alcohol_percent': alcohol_percent,
            'wine_type': wine_type,
            'needs_review': False
        }
        
        # Vivino sometimes loads the page but the data is for a general product (ID) or missing 
        # a key field. Check for a basic level of completeness.
        if final_data['vivino_rating'] is None or final_data['vintage'] is None:
            final_data['needs_review'] = True
            logger.warning("Scrape succeeded but key data (rating/vintage) is missing. Flagging for review.")
            
        return final_data, vivino_url

    except TimeoutException:
        logger.warning(f"Selenium Timeout attempting to load: {vivino_url}")
        return None, None
    except Exception as e:
        logger.error(f"Selenium failed to scrape {vivino_url}: {e}", exc_info=True)
        return None, None
    finally:
        if driver:
            driver.quit()

def _parse_url_for_fallback_data(vivino_url):
    """
    Parses the normalized URL path for minimal wine data as a final fallback.
    
    Returns:
        dict: Minimal wine data or an empty dict.
    """
    parsed = urlparse(vivino_url)
    path_parts = [part for part in parsed.path.split('/') if part]
    
    if len(path_parts) >= 2 and path_parts[0] == 'w':
        # The slug is usually path_parts[1], and the ID is path_parts[2]
        slug = path_parts[1]
        wine_id = path_parts[2] if len(path_parts) > 2 else None
        
        # Heuristic: Slug contains name and sometimes vintage.
        name = slug.replace('-', ' ').title()
        
        # Check for vintage in URL query
        vintage = None
        query_params = parse_qs(parsed.query)
        if 'year' in query_params and query_params['year'][0].isdigit():
            vintage = int(query_params['year'][0])

        # Check for vintage in slug
        if not vintage:
            match = re.search(r'(\d{4})', slug)
            if match:
                vintage = int(match.group(1))

        # Remove vintage from the name if found
        if vintage:
            name = re.sub(r'\s*\d{4}\s*', '', name).strip()
            
        # Add the ID to the name to ensure uniqueness and flag for attention
        if wine_id:
             name = f"Vivino Wine ID {wine_id}: {name}"

        # Find the best varietal match using the externally loaded list
        varietal_match = _search_for_varietal_match(name, [])

        return {
            'name': name,
            'vintage': vintage,
            'varietal': varietal_match,
            'region': 'URL Fallback', 
            'country': 'URL Fallback',
        }
    return {}

def _attempt_to_borrow_data(vivino_url):
    """
    Attempts to scrape a nearby vintage (removing the 'year' parameter) to borrow 
    common data points if the specific vintage page fails.
    """
    parsed_url = urlparse(vivino_url)
    query_params = parse_qs(parsed_url.query)
    
    # Only proceed if a year/vintage was explicitly in the URL
    if 'year' not in query_params:
        return None, None

    # Construct the URL for the general wine page (all vintages/most popular vintage)
    borrow_url = urlunparse(parsed_url._replace(query='', fragment=''))
    
    logger.info(f"Specific vintage scrape failed. Attempting to borrow data from general page: {borrow_url}")
    
    # Scrape the general page
    borrowed_data, _ = _scrape_with_selenium(borrow_url)
    
    if borrowed_data and borrowed_data.get('vivino_rating') is not None:
        logger.info(f"Successfully borrowed data from general page.")
        # Only take the static, non-vintage specific data
        return {
            'name': borrowed_data.get('name', 'Unknown Wine'),
            'vintage': int(query_params['year'][0]) if query_params['year'][0].isdigit() else None, # Restore the original vintage
            'varietal': borrowed_data.get('varietal', 'Unknown Varietal'),
            'region': borrowed_data.get('region', 'Unknown Region'),
            'country': borrowed_data.get('country', 'Unknown Country'),
            'vivino_rating': None, # Rating is for the *other* vintage, so don't copy it
            'image_url': borrowed_data.get('image_url'),
            'alcohol_percent': borrowed_data.get('alcohol_percent'), # Usually consistent
            'wine_type': borrowed_data.get('wine_type'), # Always consistent
            'needs_review': True # Flag it because the rating is missing
        }, vivino_url
            
    return None, None


def scrape_vivino_url(vivino_url):
    """
    Main function to scrape wine data from a Vivino URL with retries and fallbacks.
    
    Args:
        vivino_url (str): The initial URL provided by the user.
        
    Returns:
        tuple: (dict: wine_data, str: final_normalized_url)
    """
    
    normalized_url = _normalize_vivino_url(vivino_url)
    final_data = {}
    
    # Retry loop with random sleep to mimic human behavior
    for attempt in range(3):
        logger.info(f"Scrape attempt {attempt + 1} for {normalized_url}")
        
        # 1. Primary Scrape Attempt
        data, _ = _scrape_with_selenium(normalized_url)
        
        if data and data.get('vintage') is not None and data.get('vivino_rating') is not None:
            # Full success!
            logger.info(f"Successfully scraped wine: {data.get('name')} ({data.get('vintage')})")
            return data, normalized_url
        
        if data and (data.get('vintage') is None or data.get('vivino_rating') is None):
            logger.warning(f"Primary scrape for vintage failed. Attempting to borrow data from general page.")
            
            # 2. Secondary Scrape Attempt: Borrow from the general wine page
            borrowed_data, _ = _attempt_to_borrow_data(normalized_url)
            
            if borrowed_data:
                # Borrowed the static data, but rating/vintage remains suspect
                logger.info(f"Borrowed data successfully, returning for review: {borrowed_data.get('name')}")
                return borrowed_data, normalized_url
            
            time.sleep(random.uniform(2.0, 4.0)) # Wait before the next full attempt

    logger.warning("All scrape attempts failed. Attempting to parse URL for final fallback data.")
    
    # 3. Final Fallback: Parse URL for minimal data
    fallback_data = _parse_url_for_fallback_data(normalized_url)
    
    if fallback_data and 'Vivino Wine ID' not in fallback_data.get('name', ''):
        # Construct a minimal, "needs review" entry
        minimal_data = {
            'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal', 
            'region': 'Unknown Region', 'country': 'Unknown Country', 
            'vivino_rating': None, 'image_url': None,
            'alcohol_percent': None, 'wine_type': None,
            'needs_review': True  # Flag this entry for user review
        }
        minimal_data.update(fallback_data)
        logger.warning(f"Full scrape failed, returning partial data from URL for review: {fallback_data.get('name')}")
        return minimal_data, normalized_url

    # If even the fallback data is garbage, raise an error
    raise Exception(f"Failed to extract meaningful data from Vivino URL: {vivino_url}")
