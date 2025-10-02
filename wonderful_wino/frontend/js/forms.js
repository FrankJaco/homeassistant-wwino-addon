// js/forms.js
// Logic for handling forms and form data.

import * as state from './state.js';
import { BASE_URL } from './config.js';

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

export async function fetchAndDisplayConsumptionHistory(wine, sortOrder = 'desc') {
    const container = document.getElementById('consumptionLogContainer');
    if (!container) return;
    state.setCurrentWineForLog(wine);
    container.innerHTML = '<p>Loading history...</p>';
    try {
        const response = await fetch(`${BASE_URL}api/wine/history?vivino_url=${encodeURIComponent(wine.vivino_url)}`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Could not fetch history.');
        }
        let history = await response.json();

        if (sortOrder === 'asc') {
            history.reverse();
        }

        if (history.length === 0) {
            container.innerHTML = '<p>No history recorded for this wine.</p>';
            return;
        }

        const historyHtml = history.map(record => {
            const date = new Date(record.consumed_at).toLocaleDateString(undefined, {
                year: 'numeric', month: 'short', day: 'numeric'
            });
            let logEntryHtml = '';
            if (record.log_type === 'acquired') {
                const cost = record.cost_tier ? `(Cost: ${'$'.repeat(record.cost_tier)})` : '';
                logEntryHtml = `<span>Acquired on ${date}</span><span class="text-gray-500">${cost}</span>`;
            } else {
                const rating = record.personal_rating ? `(Rated: ${record.personal_rating.toFixed(1)} ★)` : '(Not rated)';
                logEntryHtml = `<span>Consumed on ${date}</span><span class="text-gray-500">${rating}</span>`;
            }
            return `<div class="flex justify-between items-center py-1 border-b border-gray-200 dark:border-gray-600">${logEntryHtml}</div>`;
        }).join('');

        container.innerHTML = historyHtml;
    } catch (error) {
        console.error('Failed to fetch consumption history:', error);
        container.innerHTML = `<p class="text-red-600">Error loading history: ${error.message}</p>`;
    }
}