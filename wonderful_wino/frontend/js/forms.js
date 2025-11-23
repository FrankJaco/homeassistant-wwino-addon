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
    const imageTilt = parseFloat(document.getElementById('tiltSlider').value);

    // --- MODIFIED: Get the full "X% Y%" string ---
    const imageStyle = document.getElementById('draggableImage').style.objectPosition;
    const imageFocalPoint = imageStyle || '50% 50%'; // Default if empty
    // --- END MODIFICATION ---

    return {
        vivino_url: vivinoUrl,
        image_url: imageUrl,
        tasting_notes: tastingNotes,
        image_focal_point: imageFocalPoint,
        image_zoom: imageZoom,
        image_tilt: imageTilt
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

    // --- START FIX 1: Ensure date string is parsed as UTC ---
    // We assume DB timestamps are UTC. If the string lacks timezone
    // info (like 'Z' or +/- offset), append 'Z' to force UTC parsing.
    let utcDateStr = isoDate;
    
    // Handle 'YYYY-MM-DD HH:MM:SS' format from some DBs by replacing space with 'T'
    // This is common if a 'DATETIME' field is used.
    if (utcDateStr.length >= 19 && utcDateStr.charAt(10) === ' ') {
        utcDateStr = utcDateStr.replace(' ', 'T');
    }

    // Check if string looks like it's missing timezone info
    // A simple check: doesn't end in 'Z' and doesn't contain '+' or '-' in the timezone position
    if (!utcDateStr.endsWith('Z') && utcDateStr.indexOf('+', 10) === -1 && utcDateStr.indexOf('-', 10) === -1) {
        utcDateStr += 'Z';
    }
    
    // Create a Date object from the (now guaranteed) UTC string
    const date = new Date(utcDateStr);
    // --- END FIX 1 ---

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
 * NEW: Shows save/cancel buttons when a date input is changed.
 * Listens for 'change' on the log container.
 * @param {Event} event - The DOM change event.
 */
function showLogEditControls(event) {
    if (!event.target.classList.contains('log-date-input')) return;

    const input = event.target;
    // Controls are the next sibling
    const controls = input.nextElementSibling; 
    if (!controls || !controls.classList.contains('log-entry-controls')) return;

    if (input.value !== input.dataset.originalValue) {
        controls.classList.remove('hidden');
    } else {
        // If user changes it back to original, hide controls
        controls.classList.add('hidden');
    }
}

/**
 * NEW: Handles save/cancel button clicks using event delegation.
 * Listens for 'click' on the log container.
 * @param {Event} event - The DOM click event.
 */
async function handleLogEditClick(event) {
    const button = event.target.closest('button');
    // Exit if not a button or not one of our log buttons
    if (!button || (!button.classList.contains('log-save-btn') && !button.classList.contains('log-cancel-btn'))) {
        return;
    }

    const controls = button.parentElement; // .log-entry-controls
    const input = controls.previousElementSibling; // .log-date-input
    const logId = input.dataset.logId;

    if (button.classList.contains('log-cancel-btn')) {
        // Reset value and hide controls
        input.value = input.dataset.originalValue;
        controls.classList.add('hidden');
    }

    if (button.classList.contains('log-save-btn')) {
        // Save logic
        const localDateString = input.value;
        if (!logId || !localDateString) return;

        // Convert the local datetime-local string back to a full UTC ISO string
        const newDateUTC = new Date(localDateString).toISOString();

        // Add a simple pending state
        input.style.opacity = '0.5';
        input.disabled = true;
        button.disabled = true;
        const cancelBtn = controls.querySelector('.log-cancel-btn');
        if (cancelBtn) cancelBtn.disabled = true;

        try {
            await apiCall('/api/log/update', {
                method: 'POST',
                body: JSON.stringify({
                    log_id: parseInt(logId, 10),
                    new_date: newDateUTC
                }),
                headers: { 'Content-Type': 'application/json' },
            });

            // Success: Update original value, hide controls
            input.dataset.originalValue = input.value;
            controls.classList.add('hidden');

        } catch (error) {
            console.error('Failed to update log date:', error);
            // On error, show a message
            const errorMsg = document.createElement('span');
            errorMsg.className = 'text-red-500 text-xs ml-1';
            errorMsg.textContent = 'Error!';
            controls.appendChild(errorMsg);
            setTimeout(() => errorMsg.remove(), 2000);
        } finally {
            // Re-enable controls regardless of outcome
            input.style.opacity = '1';
            input.disabled = false;
            button.disabled = false;
            if (cancelBtn) cancelBtn.disabled = false;
        }
    }
}


// --- UPDATED FUNCTION ---
/**
 * Fetches and renders the consumption history for a wine.
 * Now renders dates as editable <input> fields with save/cancel buttons.
 * @param {object} wine - The wine object.
 * @param {string} sortOrder - 'asc' or 'desc'.
 */
export async function fetchAndDisplayConsumptionHistory(wine, sortOrder = 'desc') {
    const logContainer = document.getElementById('consumptionLogContainer');
    if (!logContainer) return;

    logContainer.innerHTML = '<p class="text-gray-500 dark:text-gray-400">Loading history...</p>';
    // Clean up old listeners to prevent duplicates
    logContainer.removeEventListener('input', showLogEditControls); // <-- MODIFIED from 'change'
    logContainer.removeEventListener('click', handleLogEditClick);
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
            // MODIFIED FOR ISSUE 4: Changed to flex-col for consistent 2-line layout
            entryEl.className = 'log-entry flex flex-col items-start py-2 space-y-1 border-b border-gray-200 dark:border-gray-600 w-full';

            // Convert DB UTC ISO string to local datetime-local format for the input field
            const localDateString = toLocalInputString(entry.consumed_at);

            let details = '';
            let logTypeClass = entry.log_type === 'consumed' ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400';

            if (entry.log_type === 'consumed') {
                const rating = entry.personal_rating ? `(Rated: ${entry.personal_rating.toFixed(1)} ★)` : '(Not rated)';
                // MODIFIED FOR ISSUE 3: Removed cost from 'Consumed' log
                // const cost = entry.cost_tier ? `(Cost: ${'$'.repeat(entry.cost_tier)})` : '';
                details = `<span class="${logTypeClass} font-medium">Consumed</span> <span class="text-gray-500 dark:text-gray-400">${rating}</span>`;
            } else {
                const cost = entry.cost_tier ? `(Cost: ${'$'.repeat(entry.cost_tier)})` : '';
                details = `<span class="${logTypeClass} font-medium">Acquired</span> <span class="text-gray-500 dark:text-gray-400">${cost}</span>`;
            }

            // MODIFIED:
            // 1. Changed width from w-[160px] to w-[195px] to show AM/PM.
            // 2. Added data-original-value to track changes.
            // 3. Added hidden save/cancel buttons.
            entryEl.innerHTML = `
                <div class="flex items-center space-x-2">
                    <input type="datetime-local" 
                           class="log-date-input w-[195px] cursor-pointer focus:ring-purple-500 focus:border-purple-500 focus:ring-1"
                           value="${localDateString}" 
                           data-original-value="${localDateString}" 
                           data-log-id="${entry.id}" 
                           title="Click to edit date">
                    <div class="log-entry-controls hidden space-x-1">
                        <button class="log-save-btn p-1 text-xs bg-green-600 hover:bg-green-700 text-white rounded" title="Save change">
                            <svg class="w-3 h-3 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                        </button>
                        <button class="log-cancel-btn p-1 text-xs bg-gray-500 hover:bg-gray-600 text-white rounded" title="Cancel change">
                            <svg class="w-3 h-3 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                        </button>
                    </div>
                </div>
                <!-- MODIFIED FOR ISSUE 4: Added padding-left for alignment -->
                <div class="log-details pl-1">${details}</div>
            `;
            logContainer.appendChild(entryEl);
        });

        // Add new, delegated event listeners to the container
        logContainer.addEventListener('input', showLogEditControls); // <-- MODIFIED from 'change'
        logContainer.addEventListener('click', handleLogEditClick);

    } catch (error) {
        console.error('Failed to load consumption history:', error);
        logContainer.innerHTML = `<p class="text-red-500">Error loading history: ${error.message}</p>`;
    }
}