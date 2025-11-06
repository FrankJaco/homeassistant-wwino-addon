// js/forms.js
// Logic for handling forms and form data.

import * as state from './state.js';
import { BASE_URL } from './config.js';
// Now explicitly importing apiCall from utils.js
import { apiCall } from './utils.js';

export function getNotesFormData() {
    const vivinoUrl = document.getElementById('notesVivinoUrl').value;
    const imageUrl = document.getElementById('imageUrlInput').value;
    const tastingNotes = document.getElementById('tastingNotesInput').value;
    const imageZoom = parseFloat(document.getElementById('zoomSlider').value);

    const imageStyle = document.getElementById('draggableImage').style.objectPosition;
    const imageFocalPoint = imageStyle ? imageStyle.split(' ')[1] : '50%';

    return {
        vivino_url: vivinoUrl,
        image_url: imageUrl,
        tasting_notes: tastingNotes,
        image_focal_point: imageFocalPoint,
        image_zoom: imageZoom
    };
}

export function getEntryFormData() {
    const getElementValue = (id, parser) => {
        const el = document.getElementById(id);
        if (!el || el.value === '') return null;
        return parser(el.value);
    };

    return {
        name: getElementValue('manualNameInput', String),
        vintage: document.getElementById('nvCheckbox')?.checked ? null : getElementValue('manualVintageInput', v => parseInt(v, 10)),
        quantity: getElementValue('manualQuantityInput', v => parseInt(v, 10)),
        varietal: getElementValue('manualVarietalInput', String),
        region: getElementValue('manualRegionInput', String),
        country: getElementValue('manualCountryInput', String),
        wine_type: getElementValue('manualWineTypeInput', String) || null,
        alcohol_percent: getElementValue('manualAlcoholInput', v => parseFloat(v)) || null,
        cost_tier: getElementValue('manualCostTierInput', v => parseInt(v, 10)) || null,
        personal_rating: getElementValue('manualTasteRatingInput', v => parseFloat(v)) || null,
        tasting_notes: getElementValue('manualTastingNotesInput', String),
        image_url: getElementValue('manualImageUrlInput', String),
    };
}

export function checkFormChanges() {
    const saveAsNewWineBtn = document.getElementById('entrySaveAsNewWineBtn');
    if (!saveAsNewWineBtn || saveAsNewWineBtn.classList.contains('hidden')) return;
    const currentFormData = getEntryFormData();
    const hasChanged = JSON.stringify(currentFormData) !== JSON.stringify(state.initialEntryFormData);
    saveAsNewWineBtn.disabled = !hasChanged;
    saveAsNewWineBtn.title = hasChanged ? 'Save the current details as a new wine entry' : 'Change a field to enable saving as a new wine';
}

// --- NEW HELPER FUNCTIONS FOR EDITABLE DATES ---

/**
 * Converts a UTC date string (from DB) to the format needed
 * by <input type="datetime-local"> (YYYY-MM-DDTHH:MM).
 * @param {string} isoDate - An ISO 8601 date string.
 * @returns {string} A string formatted for datetime-local input.
 */
function toLocalInputString(isoDate) {
    if (!isoDate) return '';
    // Create a Date object. It will be in the local timezone.
    const date = new Date(isoDate);

    // Get local date components
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0'); // Months are 0-indexed
    const day = date.getDate().toString().padStart(2, '0');
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');

    // Assemble the string
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

/**
 * Handles the 'change' event on the consumption log container.
 * When a date input is changed, it calls the API to update the log.
 * @param {Event} event - The DOM change event.
 */
async function handleLogDateChange(event) {
    if (!event.target.classList.contains('log-date-input')) return;

    const input = event.target;
    // The log ID is the unique ID from the log table
    const logId = input.dataset.logId;
    const localDateString = input.value;

    if (!logId || !localDateString) return;

    // Convert the local datetime-local string back to a full UTC ISO string
    const newDateUTC = new Date(localDateString).toISOString();

    // Add a simple pending state
    input.style.opacity = '0.5';
    input.disabled = true;

    try {
        await apiCall('/api/log/update', {
            method: 'POST',
            body: JSON.stringify({
                log_id: parseInt(logId, 10),
                new_date: newDateUTC
            }),
            headers: { 'Content-Type': 'application/json' },
        });

        // Success: show a checkmark next to the input
        const check = document.createElement('span');
        check.className = 'date-saved-check text-green-500 ml-2';
        check.textContent = '✅';
        input.insertAdjacentElement('afterend', check);
        setTimeout(() => check.remove(), 1500);

    } catch (error) {
        console.error('Failed to update log date:', error);
        // We don't have a message element here, so just log and re-enable
    } finally {
        input.style.opacity = '1';
        input.disabled = false;
    }
}


// --- UPDATED FUNCTION ---
/**
 * Fetches and renders the consumption history for a wine.
 * Now renders dates as editable <input> fields using the new log ID for tracking.
 * @param {object} wine - The wine object.
 * @param {string} sortOrder - 'asc' or 'desc'.
 */
export async function fetchAndDisplayConsumptionHistory(wine, sortOrder = 'desc') {
    const logContainer = document.getElementById('consumptionLogContainer');
    if (!logContainer) return;

    logContainer.innerHTML = '<p class="text-gray-500 dark:text-gray-400">Loading history...</p>';
    // Clean up old listener to prevent duplicates
    logContainer.removeEventListener('change', handleLogDateChange);
    state.setCurrentWineForLog(wine); // Keep existing state tracking

    try {
        // Fetch history using the same endpoint
        const url = `${BASE_URL}api/wine/history?vivino_url=${encodeURIComponent(wine.vivino_url)}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        let history = await response.json();

        if (history.length === 0) {
            logContainer.innerHTML = '<p class="text-gray-500 dark:text-gray-400">No history recorded for this wine.</p>';
            return;
        }

        // Sort history based on the user's preference
        if (sortOrder === 'desc') {
            history.sort((a, b) => new Date(b.consumed_at) - new Date(a.consumed_at));
        } else {
            history.sort((a, b) => new Date(a.consumed_at) - new Date(b.consumed_at));
        }

        logContainer.innerHTML = ''; // Clear loading message

        history.forEach(entry => {
            const entryEl = document.createElement('div');
            // Added Tailwind classes for styling the log entries
            entryEl.className = 'log-entry flex justify-between items-center py-1 border-b border-gray-200 dark:border-gray-600';

            // Convert DB UTC ISO string to local datetime-local format for the input field
            const localDateString = toLocalInputString(entry.consumed_at);

            let details = '';
            let logTypeClass = entry.log_type === 'consumed' ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400';

            if (entry.log_type === 'consumed') {
                const rating = entry.personal_rating ? `(Rated: ${entry.personal_rating.toFixed(1)} ★)` : '(Not rated)';
                const cost = entry.cost_tier ? `(Cost: ${'$'.repeat(entry.cost_tier)})` : '';
                details = `<span class="${logTypeClass} font-medium">Consumed</span> <span class="text-gray-500 dark:text-gray-400">${rating} ${cost}</span>`;
            } else {
                const cost = entry.cost_tier ? `(Cost: ${'$'.repeat(entry.cost_tier)})` : '';
                details = `<span class="${logTypeClass} font-medium">Acquired</span> <span class="text-gray-500 dark:text-gray-400">${cost}</span>`;
            }

            entryEl.innerHTML = `
                <div class="flex items-center space-x-2">
                    <input type="datetime-local" class="log-date-input bg-transparent border-none p-0 w-[160px] cursor-pointer focus:ring-purple-500 focus:border-purple-500 focus:ring-1"
                           value="${localDateString}" data-log-id="${entry.id}" title="Click to edit date">
                </div>
                <div class="log-details">${details}</div>
            `;
            logContainer.appendChild(entryEl);
        });

        // Add a single, delegated event listener to the container to handle date changes
        logContainer.addEventListener('change', handleLogDateChange);

    } catch (error) {
        console.error('Failed to load consumption history:', error);
        logContainer.innerHTML = `<p class="text-red-500">Error loading history: ${error.message}</p>`;
    }
}