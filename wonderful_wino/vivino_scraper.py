import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)

# --- Internal Helpers ---
def _fetch_page(vivino_url, headers):
    resp = requests.get(vivino_url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.text

def _parse_json_ld_scripts(soup, wine_data, grape_accumulator):
    script_tags = soup.find_all('script', type='application/ld+json')
    for script in script_tags:
        try:
            if not script.string:
                continue
            json_ld = json.loads(script.string)
            items = json_ld if isinstance(json_ld, list) else [json_ld]

            for json_obj in items:
                if not isinstance(json_obj, dict):
                    continue

                # --- Product schema ---
                if json_obj.get('@type') == 'Product':
                    if wine_data['name'] == 'Unknown Wine' and json_obj.get('name'):
                        wine_data['name'] = json_obj['name'].strip()

                    if wine_data['image_url'] is None and 'image' in json_obj:
                        img = json_obj['image']
                        if isinstance(img, list) and img:
                            wine_data['image_url'] = img[0]
                        elif isinstance(img, str):
                            wine_data['image_url'] = img

                    aggregate_rating = json_obj.get('aggregateRating')
                    if aggregate_rating and isinstance(aggregate_rating, dict):
                        if wine_data['vivino_rating'] is None:
                            rating_value = aggregate_rating.get('ratingValue')
                            if rating_value is not None:
                                try:
                                    wine_data['vivino_rating'] = float(str(rating_value).replace(',', '.'))
                                except ValueError:
                                    pass

                    contains_wine = json_obj.get('containsWine')
                    if contains_wine and isinstance(contains_wine, dict) and contains_wine.get('@type') == 'Wine':
                        if wine_data['vintage'] is None and 'vintage' in contains_wine:
                            try:
                                wine_data['vintage'] = int(contains_wine['vintage'])
                            except (ValueError, TypeError):
                                pass

                        grapes = contains_wine.get('grape')
                        if grapes:
                            if isinstance(grapes, list):
                                grape_names = [g.get('name') for g in grapes if isinstance(g, dict) and g.get('name')]
                                if grape_names:
                                    grape_accumulator.extend(grape_names)
                            elif isinstance(grapes, dict) and 'name' in grapes:
                                grape_accumulator.append(grapes['name'].strip())

                    main_entity = json_obj.get('mainEntityOfPage')
                    if main_entity and isinstance(main_entity, dict):
                        breadcrumb = main_entity.get('breadcrumb')
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

                # --- WebPage schema ---
                elif json_obj.get('@type') == 'WebPage':
                    content_location = json_obj.get('contentLocation')
                    if content_location and isinstance(content_location, dict):
                        if wine_data['region'] == 'Unknown Region' and 'name' in content_location:
                            wine_data['region'] = content_location['name'].strip()
                        if wine_data['country'] == 'Unknown Country' and 'address' in content_location and isinstance(content_location['address'], dict):
                            if 'addressCountry' in content_location['address']:
                                wine_data['country'] = content_location['address']['addressCountry'].strip()

                # --- Wine schema ---
                elif json_obj.get('@type') == 'Wine':
                    if wine_data['name'] == 'Unknown Wine' and 'name' in json_obj:
                        wine_data['name'] = json_obj['name'].strip()
                    if wine_data['vintage'] is None and 'vintage' in json_obj:
                        try:
                            wine_data['vintage'] = int(json_obj['vintage'])
                        except (ValueError, TypeError):
                            pass
                    if 'grape' in json_obj:
                        grapes = json_obj['grape']
                        if grapes:
                            if isinstance(grapes, list) and grapes:
                                grape_names = [g.get('name') for g in grapes if isinstance(g, dict) and g.get('name')]
                                if grape_names:
                                    grape_accumulator.extend(grape_names)
                            elif isinstance(grapes, dict) and 'name' in grapes:
                                grape_accumulator.append(grapes['name'].strip())
                    if wine_data['region'] == 'Unknown Region' and 'region' in json_obj:
                        region_info = json_obj['region']
                        if isinstance(region_info, dict) and 'name' in region_info:
                            wine_data['region'] = region_info['name'].strip()
                    if wine_data['country'] == 'Unknown Country' and 'country' in json_obj:
                        country_info = json_obj['country']
                        if isinstance(country_info, dict) and 'name' in country_info:
                            wine_data['country'] = country_info['name'].strip()
                    if wine_data['image_url'] is None and 'image' in json_obj:
                        img = json_obj['image']
                        if isinstance(img, list) and img:
                            wine_data['image_url'] = img[0]
                        elif isinstance(img, str):
                            wine_data['image_url'] = img

        except (json.JSONDecodeError, KeyError, TypeError) as json_err:
            logger.debug(f"Vivino JSON-LD parsing error: {json_err}")

def _image_from_preload_links(soup):
    preload_links = soup.find_all('link', rel='preload', attrs={'as': 'image'})
    for link in preload_links:
        if link.has_attr('imagesrcset'):
            srcset_parts = [url.strip().split(' ')[0] for url in link['imagesrcset'].split(',')]
            if srcset_parts:
                return srcset_parts[-1]
        elif link.has_attr('href'):
            return link['href']
    return None

def _image_from_img_tag(soup):
    image_tag = soup.find('img', class_=re.compile(r'wine-page-image__image|vivinoImage_image|image-preview__image|image-container__image|wine-page__image'))
    if image_tag:
        if image_tag.has_attr('src'):
            return image_tag['src']
        elif image_tag.has_attr('data-src'):
            return image_tag['data-src']
    return None

def _name_from_html(soup):
    name_tag = soup.find('h1', class_=re.compile(r'wine-page-header__name|VintageTitle_wine'))
    if not name_tag:
        name_tag = soup.find('h1')
    return " ".join(name_tag.text.strip().split()) if name_tag else None

def _vintage_from_span(soup):
    vintage_span = soup.find('span', class_='vintage')
    if vintage_span:
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', vintage_span.text.strip())
        if year_match:
            try:
                return int(year_match.group(0))
            except ValueError:
                pass
    return None

def _collect_links_for_region_grapes(soup, wine_data, grape_accumulator):
    all_relevant_links = soup.find_all('a', href=re.compile(r'/(wine-countries|wine-regions|grapes)/'))
    for link in all_relevant_links:
        href = link.get('href', '')
        text = link.get_text(strip=True)
        if '/wine-countries/' in href and wine_data['country'] == 'Unknown Country':
            wine_data['country'] = text
        elif '/wine-regions/' in href and wine_data['region'] == 'Unknown Region':
            wine_data['region'] = text
        elif '/grapes/' in href:
            grape_accumulator.append(text)

def _parse_dl_facts(soup, wine_data, grape_accumulator):
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
            elif ('Grape' in label or 'Varietal' in label) and value.strip():
                grape_accumulator.append(value.strip())

def _process_grapes_and_heuristics(all_grape_names_collected, wine_data):
    if all_grape_names_collected:
        filtered_grapes = [
            g for g in all_grape_names_collected
            if g.lower() not in [
                'red wine', 'white wine', 'sparkling wine', 'rosé wine',
                'dessert wine', 'fortified wine', 'blend'
            ]
        ]

        if filtered_grapes:
            seen_grapes = set()
            ordered_unique_grapes = []
            for grape in all_grape_names_collected:
                cleaned_grape = grape.strip()
                if (cleaned_grape.lower() not in [
                        'red wine', 'white wine', 'sparkling wine',
                        'rosé wine', 'dessert wine', 'fortified wine', 'blend']
                    and cleaned_grape not in seen_grapes):
                    ordered_unique_grapes.append(cleaned_grape)
                    seen_grapes.add(cleaned_grape)

            # --- Bordeaux heuristics ---
            region_str = wine_data.get('region', '')
            if isinstance(region_str, str):
                region_lower = region_str.lower()

                # Right Bank: Merlot → Cab Franc → Cab Sauv
                if any(rb in region_lower for rb in [
                    'saint-émilion', 'pomerol', 'fronsac', 'canon-fronsac'
                ]):
                    preferred_order = ['Merlot', 'Cabernet Franc', 'Cabernet Sauvignon']
                    reordered = [g for pref in preferred_order
                                   for g in ordered_unique_grapes if pref.lower() == g.lower()]
                    reordered.extend([g for g in ordered_unique_grapes if g not in reordered])
                    ordered_unique_grapes = reordered

                # Left Bank: Cab Sauv → Merlot → Cab Franc
                elif any(lb in region_lower for lb in [
                    'médoc', 'pauillac', 'margaux', 'haut-médoc',
                    'saint-estèphe', 'saint-julien', 'listrac', 'moulis', 'graves'
                ]):
                    preferred_order = ['Cabernet Sauvignon', 'Merlot', 'Cabernet Franc']
                    reordered = [g for pref in preferred_order
                                   for g in ordered_unique_grapes if pref.lower() == g.lower()]
                    reordered.extend([g for g in ordered_unique_grapes if g not in reordered])
                    ordered_unique_grapes = reordered

            # --- Syrah / Shiraz heuristics ---
            country = wine_data.get('country', '').strip().lower()
            is_australia_sa = country in ['australia', 'south africa']
            transformed_grapes = []
            for grape in ordered_unique_grapes:
                if 'syrah' in grape.lower():
                    transformed_grapes.append('Shiraz' if is_australia_sa else 'Syrah')
                elif 'shiraz' in grape.lower():
                    transformed_grapes.append('Shiraz' if is_australia_sa else 'Syrah')
                else:
                    transformed_grapes.append(grape)

            wine_data['varietal'] = ", ".join(transformed_grapes)

        elif 'blend' in [g.lower() for g in all_grape_names_collected]:
            wine_data['varietal'] = 'Blend'
        else:
            wine_data['varietal'] = 'Unknown Varietal'
    else:
        wine_data['varietal'] = 'Unknown Varietal'

def _rating_from_html(soup):
    rating_tags = soup.find_all('div', class_=re.compile(r'vivinoRating_averageValue|average-value|community-score__score|rating-value'))
    for rating_tag in rating_tags:
        try:
            rating_text = rating_tag.text.strip().replace(',', '.')
            if rating_text:
                return float(rating_text)
        except ValueError:
            pass
    return None

def _year_from_query(vivino_url):
    try:
        parsed_url = urlparse(vivino_url)
        query_params = parse_qs(parsed_url.query)
        if 'year' in query_params:
            return int(query_params['year'][0])
    except (ValueError, IndexError):
        pass
    return None

# --- Public API ---
def scrape_vivino_data(vivino_url):
    """
    Scrapes detailed wine information from a given Vivino URL.
    Preserves the same interface and output structure.
    """
    logger.debug(f"Starting Vivino data scrape for URL: {vivino_url}")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    wine_data = {
        'vivino_url': vivino_url,
        'name': 'Unknown Wine',
        'vintage': None,
        'varietal': 'Unknown Varietal',
        'region': 'Unknown Region',
        'country': 'Unknown Country',
        'vivino_rating': None,
        'image_url': None,
    }

    all_grape_names_collected = []

    try:
        html = _fetch_page(vivino_url, headers)
        soup = BeautifulSoup(html, 'lxml')

        _parse_json_ld_scripts(soup, wine_data, all_grape_names_collected)

        if wine_data['image_url'] is None:
            wine_data['image_url'] = _image_from_preload_links(soup) or _image_from_img_tag(soup)

        if wine_data['image_url'] and wine_data['image_url'].startswith('//'):
            wine_data['image_url'] = 'https:' + wine_data['image_url']

        if wine_data['name'] == 'Unknown Wine':
            name_from_html = _name_from_html(soup)
            if name_from_html:
                wine_data['name'] = name_from_html

        if wine_data['vintage'] is None:
            vs = _vintage_from_span(soup)
            if vs:
                wine_data['vintage'] = vs

        _collect_links_for_region_grapes(soup, wine_data, all_grape_names_collected)
        _parse_dl_facts(soup, wine_data, all_grape_names_collected)

        _process_grapes_and_heuristics(all_grape_names_collected, wine_data)

        if wine_data['country'] == 'Unknown Country' and "/US/en/" in vivino_url:
            wine_data['country'] = "United States"

        if wine_data['vivino_rating'] is None:
            wine_data['vivino_rating'] = _rating_from_html(soup)

        if wine_data['vintage'] is None:
            wine_data['vintage'] = _year_from_query(vivino_url)

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP/Network error during Vivino scrape for {vivino_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during Vivino scrape for {vivino_url}: {e}")
        return None

    logger.info(f"Scraped Vivino: {wine_data.get('name', 'Unknown')} ({wine_data.get('vintage', 'NV')})")
    return wine_data
