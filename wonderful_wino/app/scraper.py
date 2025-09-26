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

# Master list of common grapes to check for in the wine name if missing from scraped data.
# Using a set for fast lookups. Sorted by length descending to help with sub-string matching (e.g. 'Sauvignon' vs 'Sauvignon Blanc')
MASTER_GRAPE_LIST = sorted([
    'Cabernet Sauvignon', 'Sauvignon Blanc', 'Cabernet Franc', 'Pinot Noir', 'Merlot',
    'Chardonnay', 'Malbec', 'Syrah', 'Shiraz', 'Riesling', 'Zinfandel', 'Sangiovese',
    'Grenache', 'Tempranillo', 'Nebbiolo', 'Pinotage', 'Carménère', 'Viognier',
    'Chenin Blanc', 'Gewürztraminer', 'Pinot Gris', 'Pinot Grigio', 'Mourvèdre'
], key=len, reverse=True)


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

        WebDriverWait(driver, 25).until(
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
        'vivino_rating': None, 'image_url': None
    }

    all_grape_names_collected = []
    found_grapes_in_json = False
    
    script_tags = soup.find_all('script', type='application/ld+json')
    for script in script_tags:
        try:
            json_ld = json.loads(script.string)

            if isinstance(json_ld, dict):
                is_product = json_ld.get('@type') == 'Product'
                is_wine = json_ld.get('@type') == 'Wine'

                if is_product:
                    if wine_data['name'] == 'Unknown Wine' and 'name' in json_ld: wine_data['name'] = json_ld['name'].strip()
                    if wine_data['image_url'] is None and 'image' in json_ld:
                        if isinstance(json_ld['image'], list) and json_ld['image']: wine_data['image_url'] = json_ld['image'][0]
                        elif isinstance(json_ld['image'], str): wine_data['image_url'] = json_ld['image']
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
                    if wine_data['name'] == 'Unknown Wine' and 'name' in json_ld: wine_data['name'] = json_ld['name'].strip()
                    if wine_data['vintage'] is None and 'vintage' in json_ld:
                        try: wine_data['vintage'] = int(json_ld['vintage'])
                        except (ValueError, TypeError): pass

        except (json.JSONDecodeError, KeyError, TypeError) as json_err:
            logger.debug(f"Vivino JSON-LD parsing error (may be benign): {json_err}")
            pass

    if wine_data['image_url'] is None:
        preload_link = soup.find('link', rel='preload', attrs={'as': 'image'})
        if preload_link and preload_link.has_attr('href'):
            wine_data['image_url'] = preload_link['href']

    if wine_data['image_url'] is None:
        image_tag = soup.find('img', class_=re.compile(r'wine-page-image__image|vivinoImage_image|image-preview__image'))
        if image_tag:
            wine_data['image_url'] = image_tag.get('src') or image_tag.get('data-src')

    if wine_data['image_url'] and wine_data['image_url'].startswith('//'):
        wine_data['image_url'] = 'https:' + wine_data['image_url']
            
    if wine_data['name'] == 'Unknown Wine':
        name_tag = soup.find('h1', class_=re.compile(r'wine-page-header__name|VintageTitle_wine')) or soup.find('h1')
        if name_tag: wine_data['name'] = " ".join(name_tag.text.strip().split())

    if wine_data['vintage'] is None and wine_data['name'] and 'Unknown Wine' not in wine_data['name']:
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
    
    for link in soup.find_all('a', href=re.compile(r'/(wine-countries|wine-regions|grapes)/')):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        if '/wine-countries/' in href and wine_data['country'] == 'Unknown Country': wine_data['country'] = text
        elif '/wine-regions/' in href and wine_data['region'] == 'Unknown Region': wine_data['region'] = text
        elif not found_grapes_in_json and '/grapes/' in href and text and 'blend' not in text.lower(): all_grape_names_collected.append(text)

    # Heuristics for varietal ordering and naming convention.
    if all_grape_names_collected or 'Unknown Wine' not in wine_data['name']:
        # Stage 1: Preserve order of appearance from scrape and perform initial cleaning.
        cleaned_grapes = [g.strip() for g in all_grape_names_collected if g.strip().lower() not in ['wine']]
        unique_grapes_ordered = list(dict.fromkeys(cleaned_grapes))

        # Stage 2: Augment the grape list with varietals found in the name that were missing from scrape data.
        name_lower = wine_data['name'].lower()
        current_grapes_lower = {g.lower() for g in unique_grapes_ordered}
        for grape in MASTER_GRAPE_LIST:
            if grape.lower() not in current_grapes_lower:
                if re.search(r'\b' + re.escape(grape.lower()) + r'\b', name_lower):
                    unique_grapes_ordered.append(grape)
                    logger.debug(f"Augmented grape list with '{grape}' from wine name.")

        # Stage 3: Re-order the (now augmented) list if varietals are mentioned in the wine's name.
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

        # Stage 4: Implement Shiraz/Syrah logic on the now-finalized grape order.
        preferred_syrah_term = None
        if 'shiraz' in name_lower:
            preferred_syrah_term = 'Shiraz'
        elif 'syrah' in name_lower:
            preferred_syrah_term = 'Syrah'
        
        final_grapes = []
        for grape in unique_grapes_ordered:
            is_syrah_family = 'syrah' in grape.lower() or 'shiraz' in grape.lower()
            if not is_syrah_family:
                final_grapes.append(grape)
                continue
            
            term_to_use = 'Syrah' # Default
            if preferred_syrah_term:
                term_to_use = preferred_syrah_term
            elif wine_data.get('country') in ['Australia', 'South Africa']:
                term_to_use = 'Shiraz'
            
            final_grapes.append(term_to_use)

        # Stage 5: Final de-duplication and formatting.
        if final_grapes:
             wine_data['varietal'] = ", ".join(list(dict.fromkeys(final_grapes)))

    if wine_data['vivino_rating'] is None:
        rating_tag = soup.find('div', class_=re.compile(r'vivinoRating_averageValue|community-score__score'))
        if rating_tag:
            try: wine_data['vivino_rating'] = float(rating_tag.text.strip().replace(',', '.'))
            except (ValueError, TypeError): pass

    if wine_data['name'] and wine_data['name'] != 'Unknown Wine':
        return wine_data, final_url_after_scrape
    return None, final_url_after_scrape


def scrape_vivino_data(vivino_url):
    """
    Orchestrates scraping using a headless browser to be resilient to anti-bot measures.
    """
    logger.info(f"Starting Selenium-based scrape for: {vivino_url}")
    
    wine_data, canonical_url = _perform_scrape_attempt_selenium(vivino_url)

    if wine_data:
        logger.info(f"Success on initial Selenium scrape for {canonical_url}")
        return wine_data, canonical_url
    
    logger.warning(f"Initial Selenium scrape failed for {canonical_url}. Cooling down before checking nearby vintages.")
    time.sleep(random.uniform(3.0, 5.0))

    try:
        parsed_url = urlparse(vivino_url)
        query_params = parse_qs(parsed_url.query)
        original_vintage = int(query_params.get('year', [None])[0])
    except (ValueError, TypeError, IndexError):
        original_vintage = None

    if original_vintage:
        for year_offset in [-1, 1]:
            new_vintage = original_vintage + year_offset
            
            parsed_canonical = urlparse(canonical_url)
            new_query_params = parse_qs(parsed_canonical.query)
            new_query_params['year'] = [str(new_vintage)]
            nearby_vintage_url = urlunparse(list(parsed_canonical._replace(query=urlencode(new_query_params, doseq=True))))

            logger.info(f"Attempting scrape of nearby vintage: {nearby_vintage_url}")
            nearby_data, _ = _perform_scrape_attempt_selenium(nearby_vintage_url)
            
            if nearby_data:
                logger.warning(f"Success scraping nearby vintage ({new_vintage}). Borrowing its data for original vintage ({original_vintage}).")
                borrowed_data = {
                    'name': re.sub(r'\s*\b(19|20)\d{2}\b', '', nearby_data.get('name', 'Unknown Wine')).strip(),
                    'vintage': original_vintage,
                    'varietal': nearby_data.get('varietal', 'Unknown Varietal'),
                    'region': nearby_data.get('region', 'Unknown Region'),
                    'country': nearby_data.get('country', 'Unknown Country'),
                    'vivino_rating': None,
                    'image_url': nearby_data.get('image_url'),
                }
                return borrowed_data, vivino_url
            
            time.sleep(random.uniform(2.0, 4.0))

    logger.warning("All scrape attempts failed. Attempting to parse URL for final fallback data.")
    fallback_data = _parse_url_for_fallback_data(vivino_url)
    
    if fallback_data and 'Vivino Wine ID' not in fallback_data.get('name', ''):
        minimal_data = {'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal', 'region': 'Unknown Region', 'country': 'Unknown Country', 'vivino_rating': None, 'image_url': None}
        minimal_data.update(fallback_data)
        return minimal_data, vivino_url

    logger.error(f"All scrape and fallback attempts failed for {vivino_url}.")
    return None, None