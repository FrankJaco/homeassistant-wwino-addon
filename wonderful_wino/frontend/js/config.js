// js/config.js
// Stores configuration and constant values for the application.

// This calculates the base URL to accommodate Home Assistant's Ingress feature,
// which serves the addon from a subpath.
let determinedBaseUrl = '';
if (typeof window !== 'undefined' && typeof window.__ingress_url !== 'undefined' && window.__ingress_url !== '') {
    determinedBaseUrl = window.__ingress_url;
} else {
    const pathParts = window.location.pathname.split('/');
    if (pathParts.length > 0 && pathParts[pathParts.length - 1].includes('.')) { pathParts.pop(); }
    determinedBaseUrl = pathParts.join('/');
    if (determinedBaseUrl !== '' && !determinedBaseUrl.endsWith('/')) { determinedBaseUrl += '/'; }
}
export const BASE_URL = determinedBaseUrl;

export const VIVINO_SEARCH_URL = 'https://www.vivino.com/search/wines?q=';
export const DEFAULT_COST_TIERS = { t1: 10, t2r: 20, t3r: 35, t4r: 50 };

// Emoji map for consistency with backend
export const WINE_TYPE_EMOJIS = {
    "Red": "🍷",
    "White": "🥂",
    "Rosé": "🌸",
    "Sparkling": "🍾",
    "Dessert": "🍰",
    "Fortified": "🍰",
};