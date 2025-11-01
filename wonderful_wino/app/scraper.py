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
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
]

def _get_random_user_agent():
    """Returns a random User-Agent string."""
    return random.choice(USER_AGENTS)

# --- NEW HELPER FUNCTION TO CHECK FOR MISSING EDGE CASE DATA (Country & ABV) ---
def all_required_fields_present(data):
    """
    Checks if the data contains country and alcohol_percent, which are often
    the fields missing from borrowed vintage data in edge cases.
    """
    is_country_missing = data.get('country') in [None, 'Unknown Country']
    is_abv_missing = data.get('alcohol_percent') is None
    
    # Return True only if both country and ABV are present/known.
    return not is_country_missing and not is_abv_missing
# ----------------------------------------------------------------------------

def _start_webdriver():
    """Starts a Chrome WebDriver instance."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={_get_random_user_agent()}')
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except WebDriverException as e:
        logger.error(f"Error starting WebDriver: {e}")
        return None

def _stop_webdriver(driver):
    """Stops the Chrome WebDriver instance."""
    if driver:
        driver.quit()

def _parse_url_for_fallback_data(vivino_url):
    """Extracts basic ID, Name, and Vintage from URL structure for minimum fallback data."""
    # This is a basic implementation, relying on the full version having all the details.
    # It is used at the very end as a last resort.
    
    parsed = urlparse(vivino_url)
    path_segments = parsed.path.strip('/').split('/')
    
    data = {'vivino_url': vivino_url}
    
    try:
        if 'w' in path_segments:
            wine_id_index = path_segments.index('w')
            wine_id = path_segments[wine_id_index + 1]
            data['vivino_wine_id'] = int(wine_id)
            
            # Extract name
            name_slug = path_segments[wine_id_index - 1]
            name_parts = name_slug.replace('-', ' ').split()
            # Crude attempt to capitalize the name from the slug
            name = ' '.join(p.capitalize() for p in name_parts)
            data['name'] = name
            
        
        # Extract vintage from query parameters
        query_params = parse_qs(parsed.query)
        vintage = query_params.get('year', [None])[0]
        if vintage and vintage.isdigit():
            data['vintage'] = int(vintage)
        
    except (IndexError, ValueError):
        data['name'] = f"Vivino Wine ID {data.get('vivino_wine_id', 'Unknown')}"
        data['vintage'] = None
        
    return data

def _extract_wine_data_from_json(soup, vivino_url):
    """
    Extracts structured wine data from the embedded JSON-LD script tag. 
    (Placeholder implementation, assuming the original A-scraper had a full one)
    """
    data = {
        'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal', 
        'region': 'Unknown Region', 'country': 'Unknown Country', 
        'vivino_rating': None, 'image_url': None,
        'alcohol_percent': None, 'wine_type': None,
    }

    try:
        script_tag = soup.find('script', type='application/ld+json')
        if not script_tag:
            return data

        json_data = json.loads(script_tag.string)
        wine_entity = json_data[0] if isinstance(json_data, list) else json_data
        
        data['name'] = wine_entity.get('name', data['name'])
        
        rating_data = wine_entity.get('aggregateRating', {})
        if rating_data and rating_data.get('ratingValue'):
            data['vivino_rating'] = float(rating_data['ratingValue'])

        image_url = wine_entity.get('image')
        if isinstance(image_url, list):
            image_url = image_url[0]
        data['image_url'] = image_url
        
        # Extract ABV from offers
        offers = wine_entity.get('offers', [])
        if not isinstance(offers, list): offers = [offers]
        for offer in offers:
            if offer.get('alcoholContent'):
                match = re.search(r'(\d+\.?\d*)%', offer['alcoholContent'])
                if match:
                    data['alcohol_percent'] = float(match.group(1))
                    break
        
        # Crude vintage extraction from name
        vintage_match = re.search(r'(\d{4})', data['name'])
        if data['vintage'] is None and vintage_match:
            data['vintage'] = int(vintage_match.group(1))
            data['name'] = data['name'].replace(vintage_match.group(0), '').strip()

    except Exception as e:
        logger.debug(f"Error parsing JSON-LD: {e}")

    # Augment with HTML data
    data.update(_extract_wine_data_from_html(soup, vivino_url, data))
    return data

def _extract_wine_data_from_html(soup, vivino_url, current_data):
    """
    Extracts additional wine data (Region, Country, Varietal) 
    from the static HTML structure, complementing the JSON data.
    """
    html_data = {}
    
    # Vivino ID
    try:
        wine_id_tag = soup.find('div', {'data-wine-id': re.compile(r'\d+')})
        if wine_id_tag:
            html_data['vivino_wine_id'] = int(wine_id_tag['data-wine-id'])
    except Exception:
        pass
        
    # Country / Region / Varietal / Type (Often in specific `div`s)
    wine_info_div = soup.find('div', class_='wine-page-header__wine-info')
    if not wine_info_div:
        wine_info_div = soup.find('div', class_='wine-page-link-container')

    if wine_info_div:
        links = wine_info_div.find_all('a')
        link_texts = [a.get_text(strip=True) for a in links]
        
        if len(link_texts) >= 1:
            html_data['country'] = link_texts[0]
        if len(link_texts) >= 2:
            html_data['region'] = link_texts[1]
        if len(link_texts) >= 3:
            html_data['varietal'] = link_texts[2]
            
    
    # Alcohol Percentage (ABV)
    if current_data.get('alcohol_percent') is None:
        try:
            # Look for the "Alcohol" label and get its sibling value
            alcohol_label = soup.find('div', string=re.compile(r'Alcohol', re.IGNORECASE))
            if alcohol_label:
                alcohol_value_tag = alcohol_label.find_next_sibling()
                if alcohol_value_tag:
                    match = re.search(r'(\d+\.?\d*)%', alcohol_value_tag.get_text(strip=True))
                    if match:
                        html_data['alcohol_percent'] = float(match.group(1))
        except Exception:
            pass
            
    return html_data

def _slow_scrape_with_selenium(vivino_url):
    """
    Performs a slow, full-page scrape using Selenium to capture data
    rendered by JavaScript, including country and ABV for edge cases.
    Returns extracted data or an empty dict on failure.
    """
    driver = None
    try:
        driver = _start_webdriver()
        if not driver:
            raise WebDriverException("Failed to start WebDriver.")

        driver.get(vivino_url)
        
        # Wait for the main wine details to load (a common element)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
        )
        
        # Get the fully rendered page source
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        scraped_data = _extract_wine_data_from_json(soup, vivino_url)
        scraped_data.update(_extract_wine_data_from_html(soup, vivino_url, scraped_data))

        # Check for wine name as a minimum success indicator
        if scraped_data.get('name') == 'Unknown Wine':
            logger.warning(f"Selenium scrape completed but returned minimal data for {vivino_url}")
            url_data = _parse_url_for_fallback_data(vivino_url)
            scraped_data.update(url_data)
            
        return scraped_data

    except (TimeoutException, WebDriverException) as e:
        logger.error(f"Selenium scrape attempt failed for {vivino_url}: {type(e).__name__} - {e}")
        return {}
    finally:
        _stop_webdriver(driver)

def _try_nearby_vintage_scrape(vivino_url, initial_data):
    """
    Attempts to scrape the main (parent) wine ID URL to borrow data
    when the specific vintage scrape is incomplete.
    """
    try:
        # 1. Construct the parent wine URL (remove vintage/price from query)
        parsed = urlparse(vivino_url)
        path_segments = parsed.path.strip('/').split('/')
        
        if 'w' not in path_segments:
            logger.warning("Could not find wine ID in URL for nearby vintage attempt.")
            return None
            
        wine_id_index = path_segments.index('w')
        if wine_id_index + 1 >= len(path_segments):
            logger.warning("Wine ID not present after 'w' in URL.")
            return None
            
        # Create the base URL for the parent wine
        parent_path = '/' + '/'.join(path_segments[:wine_id_index+2])
        nearby_url = urlunparse(parsed._replace(path=parent_path, query=''))
        
        logger.info(f"Attempting nearby vintage scrape from: {nearby_url}")
        
        # 2. Perform a fast request scrape on the nearby URL
        headers = {'User-Agent': _get_random_user_agent()}
        response = requests.get(nearby_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 3. Extract data from the nearby vintage/parent page
        nearby_data = _extract_wine_data_from_json(soup, nearby_url)
        nearby_data.update(_extract_wine_data_from_html(soup, nearby_url, nearby_data))

        if nearby_data and nearby_data.get('vivino_wine_id'):
            logger.info(f"Successfully scraped nearby vintage. Borrowing data from ID {nearby_data['vivino_wine_id']}")
            
            # Construct the borrowed data set
            borrowed_data = {
                'name': nearby_data.get('name'),
                'vintage': initial_data['vintage'], # Keep original vintage
                'varietal': nearby_data.get('varietal', 'Unknown Varietal'),
                'region': nearby_data.get('region', 'Unknown Region'),
                'country': nearby_data.get('country', 'Unknown Country'),
                'vivino_rating': None, # Rating is for the *other* vintage, so don't copy it
                'image_url': nearby_data.get('image_url'),
                'alcohol_percent': nearby_data.get('alcohol_percent'), # Usually consistent
                'wine_type': nearby_data.get('wine_type'), # Always consistent
                'vivino_wine_id': nearby_data.get('vivino_wine_id'),
            }
            return borrowed_data, vivino_url
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"Nearby vintage request failed: {e}")
    except Exception as e:
        logger.error(f"Error in nearby vintage scrape: {e}")
        
    return None

# The main function that orchestrates the scraping attempts
def scrape_wine_data(vivino_url):
    """
    Scrapes wine data from a Vivino URL using multiple fallbacks:
    1. Fast JSON/HTML scrape (requests)
    2. Nearby Vintage scrape (requests)
    3. Targeted Slow Scrape for edge cases (selenium) <--- B-SCRAPER LOGIC ADDED HERE
    4. Full Slow Scrape (selenium)
    5. Fallback from URL parsing
    """
    
    # 1. Initial Fast Scrape
    final_data = _parse_url_for_fallback_data(vivino_url)
    
    try:
        headers = {'User-Agent': _get_random_user_agent()}
        response = requests.get(vivino_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        initial_data = _extract_wine_data_from_json(soup, vivino_url)
        initial_data.update(_extract_wine_data_from_html(soup, vivino_url, initial_data))

        final_data.update(initial_data)

        # Check if the initial fast scrape was complete enough
        required_fields = ['name', 'vintage', 'vivino_rating', 'country']
        if all(final_data.get(field) not in [None, 'Unknown Wine', 'Unknown Country'] for field in required_fields):
            logger.info("Initial fast scrape successful.")
            return final_data, vivino_url
            
        logger.warning("Initial fast scrape incomplete. Proceeding to nearby vintage scrape.")

    except requests.exceptions.RequestException as e:
        logger.warning(f"Initial fast scrape failed (RequestException): {e}")
    except Exception as e:
        logger.error(f"Error during initial fast scrape: {e}")

    # 2. Try Nearby Vintage Scrape
    nearby_result = _try_nearby_vintage_scrape(vivino_url, final_data)
    
    if nearby_result:
        borrowed_data, vivino_url = nearby_result
        
        # --- NEW LOGIC FROM B-SCRAPER FOR TARGETED SLOW SCRAPE ---
        # 3. Targeted Slow Scrape for Country and ABV (The B-scraper's key fix)
        # Only run the slow, expensive Selenium scrape if the fast borrow failed
        # to acquire the essential metadata (Country/ABV).
        if not all_required_fields_present(borrowed_data):
            try:
                logger.warning("Borrowed data incomplete (Country/ABV missing). Performing targeted slow scrape on original URL for final details...")
                # Run the slow scrape on the original URL to get JavaScript rendered data
                slow_data = _slow_scrape_with_selenium(vivino_url)
            except Exception as e:
                logger.error(f"Targeted slow scrape failed: {e}")
                slow_data = {} # Ensure slow_data is defined

            # Merge missing fields from the slow scrape results into the borrowed data
            
            # Country Merge
            if borrowed_data.get('country') in [None, 'Unknown Country'] and slow_data.get('country') not in [None, 'Unknown Country']:
                borrowed_data['country'] = slow_data.get('country')
                logger.info("Successfully filled missing country from targeted slow scrape.")

            # ABV Merge
            if borrowed_data.get('alcohol_percent') is None and slow_data.get('alcohol_percent') is not None:
                borrowed_data['alcohol_percent'] = slow_data.get('alcohol_percent')
                logger.info("Successfully filled missing ABV from targeted slow scrape.")
        
        # Return the now potentially complete borrowed data
        return borrowed_data, vivino_url
    # -------------------------------------------------------------


    # 4. Fallback: Try a full slow scrape with Selenium if all fast attempts fail
    logger.warning("All fast scrape attempts failed (initial and nearby vintage). Attempting full slow scrape with Selenium...")
    
    # Try a couple of times with a delay
    for attempt in range(2):
        try:
            time.sleep(random.uniform(2.0, 4.0))
            slow_data = _slow_scrape_with_selenium(vivino_url)
            
            # Check for a successful full scrape
            if slow_data and slow_data.get('name') not in ['Unknown Wine', None] and slow_data.get('vintage') is not None:
                final_data.update(slow_data)
                logger.info("Full slow scrape successful on original URL.")
                return final_data, vivino_url
                
            logger.warning(f"Full slow scrape attempt {attempt + 1} was unsuccessful or returned minimal data.")
        except Exception as e:
            logger.error(f"Full slow scrape attempt {attempt + 1} failed: {e}")
    
    # 5. Final Fallback data from URL parsing
    logger.warning("All scrape attempts failed. Attempting to parse URL for final fallback data.")
    fallback_data = _parse_url_for_fallback_data(vivino_url)
    
    if fallback_data and 'Vivino Wine ID' not in fallback_data.get('name', ''):
        minimal_data = {
            'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal', 
            'region': 'Unknown Region', 'country': 'Unknown Country', 
            'vivino_rating': None, 'image_url': None,
            'alcohol_percent': None, 'wine_type': None,
            'needs_review': True  # Flag this entry for user review
        }
        minimal_data.update(fallback_data)
        logger.warning(f"Full scrape failed, returning partial data from URL for review: {fallback_data.get('name')}")
        return minimal_data, vivino_url

    logger.error(f"Failed to extract any useful data for {vivino_url}.")
    return {'name': 'Scrape Failed', 'vivino_url': vivino_url, 'needs_review': True}, vivino_url
