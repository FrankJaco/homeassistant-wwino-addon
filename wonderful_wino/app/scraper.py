import requests
from bs4 import BeautifulSoup
import re
import json
import logging
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
import time 
import random 

# Set up a logger specific to this module
logger = logging.getLogger(__name__)

# --- Create a single, persistent session ---
PERSISTENT_SESSION = requests.Session()
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0'
]
PERSISTENT_SESSION.headers.update({ 'User-Agent': random.choice(USER_AGENTS) })


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


def _perform_scrape_attempt(url: str):
    """
    Performs a single, complete scrape attempt for a given URL.
    """
    logger.debug(f"Executing scrape attempt for URL: {url}")
    
    try:
        response = None
        canonical_url = url
        for attempt in range(4): 
            if attempt > 0:
                delay = 2**(attempt - 1)
                logger.warning(f"Scrape attempt {attempt + 1} for {url} received status 202. Retrying after a {delay}s delay...")
                time.sleep(delay)

            PERSISTENT_SESSION.headers.update({ 'User-Agent': random.choice(USER_AGENTS) })
            response = PERSISTENT_SESSION.get(url, timeout=10)
            canonical_url = response.url

            if response.status_code == 200:
                logger.debug(f"Scrape attempt {attempt + 1} for {url} successful with status 200.")
                break 
            
            if response.status_code != 202:
                logger.warning(f"Scrape attempt failed for {url}. Status: {response.status_code}")
                return None, canonical_url
        
        if response.status_code != 200:
             logger.error(f"All scrape attempts for {url} failed to get a 200 response. Last status: {response.status_code}")
             return None, canonical_url

        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        wine_data = {
            'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal',
            'region': 'Unknown Region', 'country': 'Unknown Country',
            'vivino_rating': None, 'image_url': None
        }

        # --- (The extensive parsing logic remains the same) ---
        all_grape_names_collected = []
    
        script_tags = soup.find_all('script', type='application/ld+json')
        for script in script_tags:
            try:
                json_ld = json.loads(script.string)
    
                if isinstance(json_ld, dict):
                    if json_ld.get('@type') == 'Product':
                        if wine_data['name'] == 'Unknown Wine' and 'name' in json_ld:
                            wine_data['name'] = json_ld['name'].strip()
    
                        if wine_data['image_url'] is None and 'image' in json_ld:
                            if isinstance(json_ld['image'], list) and json_ld['image']:
                                wine_data['image_url'] = json_ld['image'][0]
                            elif isinstance(json_ld['image'], str):
                                wine_data['image_url'] = json_ld['image']
    
                        aggregate_rating = json_ld.get('aggregateRating')
                        if aggregate_rating and isinstance(aggregate_rating, dict):
                            if wine_data['vivino_rating'] is None:
                                rating_value = aggregate_rating.get('ratingValue')
                                if rating_value is not None:
                                    try: wine_data['vivino_rating'] = float(str(rating_value).replace(',', '.'));
                                    except ValueError: pass
                            
                        contains_wine = json_ld.get('containsWine')
                        if contains_wine and isinstance(contains_wine, dict) and contains_wine.get('@type') == 'Wine':
                            if wine_data['vintage'] is None and 'vintage' in contains_wine:
                                try: wine_data['vintage'] = int(contains_wine['vintage']);
                                except ValueError: pass
    
                            grapes = contains_wine.get('grape')
                            if grapes:
                                if isinstance(grapes, list):
                                    grape_names = [g.get('name') for g in grapes if isinstance(g, dict) and g.get('name')]
                                    if grape_names:
                                        all_grape_names_collected.extend(grape_names)
                                elif isinstance(grapes, dict) and 'name' in grapes:
                                    all_grape_names_collected.append(grapes['name'].strip())
    
                        main_entity_of_page = json_ld.get('mainEntityOfPage')
                        if main_entity_of_page and isinstance(main_entity_of_page, dict):
                            breadcrumb = main_entity_of_page.get('breadcrumb')
                            if breadcrumb and isinstance(breadcrumb, dict) and breadcrumb.get('@type') == 'BreadcrumbList':
                                item_list = breadcrumb.get('itemListElement')
                                if item_list and isinstance(item_list, list):
                                    for item_elem in item_list:
                                        if isinstance(item_elem, dict) and 'item' in item_elem:
                                            item = item_elem['item']
                                            if isinstance(item, dict) and 'name' in item and 'url' in item:
                                                if wine_data['country'] == 'Unknown Country' and '/countries/' in item['url']:
                                                    wine_data['country'] = item['name'].strip()
                                                if wine_data['region'] == 'Unknown Region' and '/regions/' in item['url']:
                                                    wine_data['region'] = item['name'].strip()
    
                    elif json_ld.get('@type') == 'WebPage':
                        content_location = json_ld.get('contentLocation')
                        if content_location and isinstance(content_location, dict):
                            if wine_data['region'] == 'Unknown Region' and 'name' in content_location:
                                wine_data['region'] = content_location['name'].strip()
                            if wine_data['country'] == 'Unknown Country' and 'address' in content_location and isinstance(content_location['address'], dict):
                                if 'addressCountry' in content_location['address']:
                                    wine_data['country'] = content_location['address']['addressCountry'].strip()
    
                    elif json_ld.get('@type') == 'Wine':
                        if wine_data['name'] == 'Unknown Wine' and 'name' in json_ld:
                            wine_data['name'] = json_ld['name'].strip()
                        if wine_data['vintage'] is None and 'vintage' in json_ld:
                            try: wine_data['vintage'] = int(json_ld['vintage']);
                            except ValueError: pass
                        if 'grape' in json_ld:
                            grapes = json_ld['grape']
                            if grapes:
                                if isinstance(grapes, list) and grapes:
                                    grape_names = [g.get('name') for g in grapes if isinstance(g, dict) and g.get('name')]
                                    if grape_names:
                                        all_grape_names_collected.extend(grape_names)
                                elif isinstance(grapes, dict) and 'name' in grapes:
                                    all_grape_names_collected.append(grapes['name'].strip())
                        if wine_data['region'] == 'Unknown Region' and 'region' in json_ld:
                            region_info = json_ld['region']
                            if isinstance(region_info, dict) and 'name' in region_info:
                                wine_data['region'] = region_info['name'].strip()
                        if wine_data['country'] == 'Unknown Country' and 'country' in json_ld:
                            country_info = json_ld['country']
                            if isinstance(country_info, dict) and 'name' in country_info:
                                wine_data['country'] = country_info['name'].strip()
                        if wine_data['image_url'] is None and 'image' in json_ld:
                            if isinstance(json_ld['image'], list) and json_ld['image']:
                                wine_data['image_url'] = json_ld['image'][0]
                            elif isinstance(json_ld['image'], str):
                                wine_data['image_url'] = json_ld['image']
    
            except (json.JSONDecodeError, KeyError, TypeError) as json_err:
                logger.debug(f"Vivino JSON-LD parsing error (may be benign if other schemas exist): {json_err}")
                pass
        
        if wine_data['image_url'] is None:
            preload_links = soup.find_all('link', rel='preload', attrs={'as': 'image'})
            
            best_image_url = None
            if preload_links:
                for link in preload_links:
                    if link.has_attr('imagesrcset'):
                        srcset_parts = [url.strip().split(' ')[0] for url in link['imagesrcset'].split(',')]
                        if srcset_parts:
                            best_image_url = srcset_parts[-1]
                            break
                    elif link.has_attr('href'):
                        best_image_url = link['href']
                
                if best_image_url:
                    wine_data['image_url'] = best_image_url
                    logger.debug(f"HTML Image URL (preload link) found: {wine_data['image_url']}")

        if wine_data['image_url'] is None:
            image_tag = soup.find('img', class_=re.compile(r'wine-page-image__image|vivinoImage_image|image-preview__image|image-container__image|wine-page__image'))
            if image_tag:
                if image_tag.has_attr('src'):
                    wine_data['image_url'] = image_tag['src']
                elif image_tag.has_attr('data-src'):
                    wine_data['image_url'] = image_tag['data-src']
                logger.debug(f"HTML Image URL (fallback img tag) found: {wine_data['image_url']}")
        
        if wine_data['image_url'] and wine_data['image_url'].startswith('//'):
            wine_data['image_url'] = 'https:' + wine_data['image_url']
            
        if wine_data['name'] == 'Unknown Wine':
            name_tag = soup.find('h1', class_=re.compile(r'wine-page-header__name|VintageTitle_wine'))
            if not name_tag:
                name_tag = soup.find('h1')

            if name_tag:
                wine_data['name'] = " ".join(name_tag.text.strip().split())
                logger.debug(f"HTML Name found: '{wine_data['name']}'")

        if wine_data['vintage'] is None and wine_data['name'] and 'Unknown Wine' not in wine_data['name']:
            name_vintage_match = re.search(r'\b(19\d{2}|20\d{2})\b', wine_data['name'])
            if name_vintage_match:
                try:
                    year = int(name_vintage_match.group(0))
                    current_year = 2025 
                    if 1900 <= year <= current_year + 5:
                        wine_data['vintage'] = year
                        cleaned_name = wine_data['name'].replace(name_vintage_match.group(0), '').strip()
                        wine_data['name'] = " ".join(cleaned_name.split())
                        logger.debug(f"HTML Vintage (name text) found and removed from name: {wine_data['vintage']}, Cleaned Name: '{wine_data['name']}'")
                except ValueError:
                    pass

        if wine_data['vintage'] is None:
            vintage_span = soup.find('span', class_='vintage')
            if vintage_span:
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', vintage_span.text.strip())
                if year_match:
                    try:
                        wine_data['vintage'] = int(year_match.group(0))
                        logger.debug(f"HTML Vintage (span.vintage) found: {wine_data['vintage']}")
                    except ValueError: pass

        all_relevant_links = soup.find_all('a', href=re.compile(r'/(wine-countries|wine-regions|grapes)/'))

        for link in all_relevant_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)

            if '/wine-countries/' in href and wine_data['country'] == 'Unknown Country':
                wine_data['country'] = text
            elif '/wine-regions/' in href and wine_data['region'] == 'Unknown Region':
                wine_data['region'] = text
            elif '/grapes/' in href:
                if text and 'blend' not in text.lower() and 'wine' not in text.lower():
                    all_grape_names_collected.append(text)
                elif text:
                    all_grape_names_collected.append(text)

        dl_tags = soup.find_all('dl', class_=re.compile(r'wine-facts|product-details'))
        for dl in dl_tags:
            dt_dd_pairs = list(zip(dl.find_all('dt'), dl.find_all('dd')))
            for dt, dd in dt_dd_pairs:
                label = dt.get_text(strip=True)
                value = dd.get_text(strip=True)

                if 'Country' in label and wine_data['country'] == 'Unknown Country' and value.strip():
                    wine_data['country'] = value
                elif 'Region' in label and wine_data['region'] == 'Unknown Region' and value.strip():
                    wine_data['region'] = value
                elif ('Grape' in label or 'Varietal' in label):
                    if value.strip():
                        all_grape_names_collected.append(value.strip())

        if all_grape_names_collected:
            filtered_grapes = [
                g for g in all_grape_names_collected
                if g.lower() not in ['red wine', 'white wine', 'sparkling wine', 'rosé wine', 'dessert wine', 'fortified wine', 'blend']
            ]

            if filtered_grapes:
                seen_grapes = set()
                ordered_unique_grapes = []
                for grape in all_grape_names_collected:
                    cleaned_grape = grape.strip()
                    if cleaned_grape.lower() not in [
                        'red wine', 'white wine', 'sparkling wine', 'rosé wine', 'dessert wine', 'fortified wine', 'blend'
                    ] and cleaned_grape not in seen_grapes:
                        ordered_unique_grapes.append(cleaned_grape)
                        seen_grapes.add(cleaned_grape)

                if 'region' in wine_data and isinstance(wine_data['region'], str):
                    region_str = wine_data['region'].lower()
                    if 'saint-émilion' in region_str or 'pomerol' in region_str or 'fronsac' in region_str or 'canon-fronsac' in region_str:
                        preferred_order = ['Merlot', 'Cabernet Franc', 'Cabernet Sauvignon']
                        reordered_grapes = [grape for pref in preferred_order for grape in ordered_unique_grapes if pref.lower() == grape.lower()]
                        reordered_grapes.extend([g for g in ordered_unique_grapes if g not in reordered_grapes])
                        ordered_unique_grapes = reordered_grapes
                    elif any(lb_region in region_str for lb_region in ['médoc', 'pauillac', 'margaux', 'haut-médoc', 'saint-estèphe', 'saint-julien', 'listrac', 'moulis', 'graves']):
                        preferred_order = ['Cabernet Sauvignon', 'Merlot', 'Cabernet Franc']
                        reordered_grapes = [grape for pref in preferred_order for grape in ordered_unique_grapes if pref.lower() == grape.lower()]
                        reordered_grapes.extend([g for g in ordered_unique_grapes if g not in reordered_grapes])
                        ordered_unique_grapes = reordered_grapes

                country_for_shiraz_syrah = wine_data.get('country', '').strip().lower()
                is_australia_sa = (country_for_shiraz_syrah == 'australia' or country_for_shiraz_syrah == 'south africa')
                transformed_grapes = []
                for grape in ordered_unique_grapes:
                    if 'syrah' in grape.lower(): transformed_grapes.append('Shiraz' if is_australia_sa else 'Syrah')
                    elif 'shiraz' in grape.lower(): transformed_grapes.append('Syrah' if not is_australia_sa else 'Shiraz')
                    else: transformed_grapes.append(grape)
                wine_data['varietal'] = ", ".join(transformed_grapes)
            elif 'blend' in [g.lower() for g in all_grape_names_collected]:
                wine_data['varietal'] = 'Blend'
            else:
                wine_data['varietal'] = 'Unknown Varietal'
        else:
            wine_data['varietal'] = 'Unknown Varietal'

        if wine_data['country'] == 'Unknown Country' and "/US/en/" in url:
            wine_data['country'] = "United States"

        if wine_data['vivino_rating'] is None:
            rating_tags = soup.find_all('div', class_=re.compile(r'vivinoRating_averageValue|average-value|community-score__score|rating-value'))
            for rating_tag in rating_tags:
                try:
                    rating_text = rating_tag.text.strip().replace(',', '.')
                    if rating_text:
                        wine_data['vivino_rating'] = float(rating_text)
                        break
                except ValueError: pass
        if wine_data['vintage'] is None:
            try:
                parsed_url = urlparse(canonical_url)
                query_params = parse_qs(parsed_url.query)
                if 'year' in query_params:
                    wine_data['vintage'] = int(query_params['year'][0])
            except (ValueError, IndexError):
                pass
        
        if wine_data['name'] != 'Unknown Wine':
            return wine_data, canonical_url
        
        return None, canonical_url

    except requests.exceptions.RequestException as e:
        logger.warning(f"Network error during scrape attempt for {url}: {e}")
        return None, url


def scrape_vivino_data(vivino_url):
    """
    Orchestrates a multi-stage scrape attempt to find the best possible wine data.
    """
    wine_data = None
    canonical_url = None
    try:
        logger.info(f"Starting advanced scrape for: {vivino_url}")
        
        wine_data, canonical_url = _perform_scrape_attempt(vivino_url)
        if wine_data:
            logger.info(f"Success on initial scrape for {canonical_url}")
            return wine_data, canonical_url
        
        # If the initial scrape fails, cool down before trying fallbacks
        logger.warning(f"Initial scrape failed. Cooling down for 5 seconds before checking nearby vintages.")
        time.sleep(5)

        try:
            parsed_url = urlparse(vivino_url)
            query_params = parse_qs(parsed_url.query)
            original_vintage = int(query_params.get('year', [None])[0])
        except (ValueError, TypeError):
            original_vintage = None

        if original_vintage:
            for i, year_offset in enumerate([-1, 1]):
                # Add a delay between the two nearby vintage checks
                if i > 0:
                    logger.debug("Applying 3-second delay between nearby vintage checks.")
                    time.sleep(3)

                new_vintage = original_vintage + year_offset
                
                # --- MODIFIED: Correctly build nearby vintage URL, preserving all other params ---
                new_query_params = query_params.copy()
                new_query_params['year'] = [str(new_vintage)]
                
                new_url_parts = list(parsed_url)
                new_url_parts[4] = urlencode(new_query_params, doseq=True)
                nearby_vintage_url = urlunparse(new_url_parts)
                # --- END MODIFIED SECTION ---

                logger.info(f"Attempting scrape of nearby vintage: {nearby_vintage_url}")
                nearby_data, nearby_canonical_url = _perform_scrape_attempt(nearby_vintage_url)
                
                if nearby_data:
                    logger.warning(f"Success scraping nearby vintage ({new_vintage}). Borrowing its data for original vintage ({original_vintage}).")
                    
                    nearby_name_cleaned = re.sub(r'\s*\b(19|20)\d{2}\b', '', nearby_data['name']).strip()

                    borrowed_data = {
                        'name': nearby_name_cleaned,
                        'vintage': original_vintage,
                        'varietal': nearby_data['varietal'],
                        'region': nearby_data['region'],
                        'country': nearby_data['country'],
                        'vivino_rating': None,
                        'image_url': nearby_data['image_url'],
                    }
                    return borrowed_data, canonical_url

        logger.warning("All scrape attempts failed. Attempting to parse URL for final fallback data.")
        fallback_data = _parse_url_for_fallback_data(vivino_url)
        
        if fallback_data and 'Vivino Wine ID' not in fallback_data.get('name', ''):
            logger.info(f"Successfully parsed fallback data for {fallback_data.get('name')}")
            minimal_data = {
                'name': 'Unknown Wine', 'vintage': None, 'varietal': 'Unknown Varietal',
                'region': 'Unknown Region', 'country': 'Unknown Country',
                'vivino_rating': None, 'image_url': None
            }
            minimal_data.update(fallback_data)
            return minimal_data, vivino_url

        logger.error(f"All scrape and fallback attempts failed to find a valid wine name for {vivino_url}.")
        return None, None
    finally:
        # A final, short cooldown to ensure calls to this function are spaced out.
        logger.debug("Applying a final 2-second cooldown.")
        time.sleep(2)