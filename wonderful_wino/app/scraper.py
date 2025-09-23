import requests
from bs4 import BeautifulSoup
import re
import json
import logging
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

# Set up a logger specific to this module
logger = logging.getLogger(__name__)


def _parse_url_for_fallback_data(url: str):
    """
    Parses a Vivino URL to get a fallback name and vintage.
    This is the final safety net if all scraping fails.
    """
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        vintage = int(query_params['year'][0]) if 'year' in query_params else None

        path_name = None
        match = re.search(r'/(?:[a-zA-Z]{2}/)?([^/]+)/w/', parsed_url.path)
        if match:
            path_name = match.group(1).replace('-', ' ').title()

        if path_name:
            return {'name': path_name, 'vintage': vintage}
    except (ValueError, IndexError, TypeError) as e:
        logger.error(f"Could not parse fallback data from URL {url}: {e}")
    
    return None


def _perform_scrape_attempt(url: str):
    """
    Performs a single, complete scrape attempt for a given URL.
    Returns (wine_data, canonical_url) on success, or (None, canonical_url) on failure.
    """
    logger.debug(f"Executing scrape attempt for URL: {url}")
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    ]
    headers = { 'User-Agent': user_agents[0] }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        canonical_url = response.url
        
        if response.status_code not in [200, 202]:
            logger.warning(f"Scrape attempt failed for {url}. Status: {response.status_code}")
            return None, canonical_url

        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        wine_data = {
            'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal',
            'region': 'Unknown Region', 'country': 'Unknown Country',
            'vivino_rating': None, 'image_url': None
        }

        # --- (Full, detailed parsing logic) ---
        # This is the same ~200 lines of parsing logic as before.
        # It attempts to fill the wine_data dictionary with rich details.
        all_grape_names_collected = []
        script_tags = soup.find_all('script', type='application/ld+json')
        # ... (all the existing JSON-LD and HTML parsing logic) ...
        # (For brevity, not re-pasting the ~200 lines of parsing logic here)
        # Assume the full parsing logic from your original file is here.
        name_tag = soup.find('h1', class_=re.compile(r'wine-page-header__name|VintageTitle_wine'))
        if name_tag:
            wine_data['name'] = " ".join(name_tag.text.strip().split())
        
        name_vintage_match = re.search(r'\b(19\d{2}|20\d{2})\b', wine_data['name'])
        if name_vintage_match:
            try:
                wine_data['vintage'] = int(name_vintage_match.group(0))
                cleaned_name = wine_data['name'].replace(name_vintage_match.group(0), '').strip()
                wine_data['name'] = " ".join(cleaned_name.split())
            except ValueError: pass
        
        if wine_data['vintage'] is None:
            try:
                parsed_url_for_vintage = urlparse(canonical_url)
                query_params_for_vintage = parse_qs(parsed_url_for_vintage.query)
                if 'year' in query_params_for_vintage:
                    wine_data['vintage'] = int(query_params_for_vintage['year'][0])
            except (ValueError, IndexError): pass
        # --- (End of full parsing logic) ---

        if wine_data['name'] != 'Unknown Wine':
            return wine_data, canonical_url
        
        return None, canonical_url

    except requests.exceptions.RequestException:
        logger.warning(f"Network error during scrape attempt for {url}.")
        return None, url


def scrape_vivino_data(vivino_url):
    """
    Orchestrates a multi-stage scrape attempt to find the best possible wine data.
    """
    logger.info(f"Starting advanced scrape for: {vivino_url}")
    
    # --- Attempt 1: Scrape the original URL ---
    wine_data, canonical_url = _perform_scrape_attempt(vivino_url)
    if wine_data:
        logger.info(f"Success on initial scrape for {canonical_url}")
        return wine_data, canonical_url
    
    logger.warning(f"Initial scrape failed for {vivino_url}. Checking for nearby vintages.")

    # --- Nearby Vintage Logic ---
    try:
        parsed_url = urlparse(vivino_url)
        query_params = parse_qs(parsed_url.query)
        original_vintage = int(query_params.get('year', [None])[0])
    except (ValueError, TypeError):
        original_vintage = None

    if original_vintage:
        for year_offset in [-1, 1]: # Try previous year, then next year
            new_vintage = original_vintage + year_offset
            query_params['year'] = [str(new_vintage)]
            
            # Rebuild the URL with the new vintage
            # urlunparse requires a 6-tuple: (scheme, netloc, path, params, query, fragment)
            new_url_parts = list(parsed_url)
            new_url_parts[4] = urlencode(query_params, doseq=True)
            nearby_vintage_url = urlunparse(new_url_parts)

            logger.info(f"Attempting scrape of nearby vintage: {nearby_vintage_url}")
            nearby_data, nearby_canonical_url = _perform_scrape_attempt(nearby_vintage_url)
            
            if nearby_data:
                logger.warning(f"Success scraping nearby vintage ({new_vintage}). Borrowing its data for original vintage ({original_vintage}).")
                # --- This is the "Cherry-Picking" logic ---
                # We create a new record, borrowing data but preserving the user's intended vintage.
                borrowed_data = {
                    'name': nearby_data['name'],
                    'vintage': original_vintage, # CRITICAL: Use the user's requested vintage
                    'varietal': nearby_data['varietal'],
                    'region': nearby_data['region'],
                    'country': nearby_data['country'],
                    'vivino_rating': None, # CRITICAL: Do not borrow the rating
                    'image_url': nearby_data['image_url'],
                }
                # Return the original canonical URL so the database key is correct
                return borrowed_data, canonical_url

    # --- Final Fallback: Parse the URL itself ---
    logger.warning("All scrape attempts failed. Attempting to parse URL for final fallback data.")
    fallback_data = _parse_url_for_fallback_data(vivino_url)
    if fallback_data:
        logger.info(f"Successfully parsed fallback data for {fallback_data.get('name')}")
        minimal_data = {
            'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal',
            'region': 'Unknown Region', 'country': 'Unknown Country',
            'vivino_rating': None, 'image_url': None
        }
        minimal_data.update(fallback_data)
        return minimal_data, vivino_url # Use original URL as canonical here

    # --- Ultimate Failure ---
    logger.error(f"All scrape and fallback attempts failed for {vivino_url}.")
    return None, None