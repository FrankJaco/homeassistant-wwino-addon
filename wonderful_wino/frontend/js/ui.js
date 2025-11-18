// js/ui.js
// Handles UI interactions and element manipulations.

import * as state from './state.js';
import { apiCall } from './utils.js';
import { fetchInventory } from './inventory.js';

export function setupVintageControls() {
    const vintageInput = document.getElementById('manualVintageInput');
    const nvCheckbox = document.getElementById('nvCheckbox');
    if (!vintageInput || !nvCheckbox) return;
    vintageInput.max = new Date().getFullYear() + 5;
    nvCheckbox.addEventListener('change', () => {
        vintageInput.disabled = nvCheckbox.checked;
        vintageInput.required = !nvCheckbox.checked;
        if (nvCheckbox.checked) vintageInput.value = '';
        else vintageInput.focus();
    });
}

// NOTE: setupStarRating is used for 'edit' mode in the entry modal
export function setupStarRating(selectorId, inputId, feedbackId) {
    const selectorEl = document.getElementById(selectorId);
    const inputEl = document.getElementById(inputId);
    const feedbackEl = document.getElementById(feedbackId);
    if (!selectorEl || !inputEl) return;
    
    // If setting up the Taste Modal stars, exit here as dedicated controls handle it
    if (selectorId === 'tasteRatingSelector') {
        return;
    }

    selectorEl.addEventListener('mousemove', e => {
        if (!e.target.matches('span')) return;
        const star = e.target;
        const starRect = star.getBoundingClientRect();
        const isHalf = (e.clientX - starRect.left) < (starRect.width / 2);
        const rating = parseInt(star.dataset.value, 10) - (isHalf ? 0.5 : 0);
        updateFeedbackText(feedbackEl, rating);
        updateStarVisuals(selectorEl, rating, 'hover');
    });
    selectorEl.addEventListener('mouseleave', () => {
        const currentRating = parseFloat(inputEl.value) || 0;
        updateStarVisuals(selectorEl, currentRating, 'rated');
        updateFeedbackText(feedbackEl, currentRating);
    });
    selectorEl.addEventListener('click', e => {
        if (!e.target.matches('span')) return;
        const star = e.target;
        const starRect = star.getBoundingClientRect();
        const isHalf = (e.clientX - starRect.left) < (starRect.width / 2);
        const rating = parseInt(star.dataset.value, 10) - (isHalf ? 0.5 : 0);
        const currentValue = parseFloat(inputEl.value) || 0;
        inputEl.value = (currentValue === rating) ? '' : rating;
        const newRating = parseFloat(inputEl.value) || 0;
        updateStarVisuals(selectorEl, newRating, 'rated');
        updateFeedbackText(feedbackEl, newRating);
    });
}

/**
 * Sets up the fine-grain rating spinner and coarse star selector for the taste modal,
 * keeping both synchronized.
 */
export function setupTasteRatingControls() {
    const spinnerEl = document.getElementById('tasteRatingSpinner');
    const hiddenInputEl = document.getElementById('tasteRatingInput');
    const selectorEl = document.getElementById('tasteRatingSelector');
    const feedbackEl = document.getElementById('tasteRatingFeedback');

    if (!spinnerEl || !hiddenInputEl || !selectorEl || !feedbackEl) return;

    // --- Core Sync Function (Reads Spinner, Updates Hidden Input, Visuals, and Text) ---
    const syncRating = () => {
        let rating = parseFloat(spinnerEl.value);
        
        // Clamp the value and ensure it's a number
        if (isNaN(rating) || rating < 0) {
            rating = 0;
        } else if (rating > 5) {
            rating = 5;
        }
        
        // Format to one decimal place for display consistency in the spinner
        spinnerEl.value = rating.toFixed(1);

        // Update the hidden input for form submission
        hiddenInputEl.value = rating.toFixed(1);

        // Update visual elements
        updateStarVisuals(selectorEl, rating, 'rated');
        updateFeedbackText(feedbackEl, rating);
    };
    
    // --- 1. Star Click Handler (Coarse 0.5 increment) ---
    // User can now click stars to set the rating in 0.5 increments.
    selectorEl.addEventListener('click', e => {
        if (!e.target.matches('span')) return;
        const star = e.target;
        const starRect = star.getBoundingClientRect();
        
        // Calculate rating in 0.5 increments
        const isHalf = (e.clientX - starRect.left) < (starRect.width / 2);
        const clickRating = parseInt(star.dataset.value, 10) - (isHalf ? 0.5 : 0);
        
        // If they click the same rating, treat it as a reset (to 0)
        const currentRating = parseFloat(spinnerEl.value) || 0;
        const newRating = (currentRating === clickRating) ? 0 : clickRating;

        // Update the spinner value (which is the source of truth) and trigger synchronization
        spinnerEl.value = newRating.toFixed(1);
        syncRating();
    });

    // --- 2. Star Hover Handler ---
    selectorEl.addEventListener('mousemove', e => {
        if (!e.target.matches('span')) return;
        const star = e.target;
        const starRect = star.getBoundingClientRect();
        const isHalf = (e.clientX - starRect.left) < (starRect.width / 2);
        const hoverRating = parseInt(star.dataset.value, 10) - (isHalf ? 0.5 : 0);
        updateFeedbackText(feedbackEl, hoverRating);
        updateStarVisuals(selectorEl, hoverRating, 'hover');
    });
    
    selectorEl.addEventListener('mouseleave', () => {
        // Revert visuals to the actual rated value on mouseleave
        const currentRating = parseFloat(hiddenInputEl.value) || 0;
        syncRating(); 
        updateFeedbackText(feedbackEl, currentRating);
    });


    // --- 3. Spinner Input Handler (Fine 0.1 increment) ---
    spinnerEl.addEventListener('input', syncRating);
    spinnerEl.addEventListener('change', syncRating); // Also handle 'change' for validation/clamping on blur

    // Initial setup
    syncRating();
}


export function updateStarVisuals(selectorEl, rating, stateClass) {
    if (!selectorEl) return;
    selectorEl.querySelectorAll('span').forEach((star, index) => {
        const starValue = index + 1;
        star.className = '';
        if (rating >= starValue) star.classList.add(`${stateClass}`);
        else if (rating > index && rating < starValue) star.classList.add(`${stateClass}-half`);
    });
}

export function updateFeedbackText(feedbackEl, rating) {
    // Ensure rating is displayed with 1 decimal place for the new precision
    if (feedbackEl) feedbackEl.textContent = rating > 0 ? `${parseFloat(rating).toFixed(1)} star${rating !== 1 ? 's' : ''}` : '';
}

export function resetTasteStars() {
    // Now resets both the hidden input and the visible spinner input
    const hiddenInputEl = document.getElementById('tasteRatingInput');
    const spinnerEl = document.getElementById('tasteRatingSpinner');
    const selectorEl = document.getElementById('tasteRatingSelector');
    const feedbackEl = document.getElementById('tasteRatingFeedback');
    
    // Reset all values to '0.0'
    if (hiddenInputEl) hiddenInputEl.value = '0.0';
    if (spinnerEl) spinnerEl.value = '0.0';
    
    // Update visuals to reflect 0.0
    updateStarVisuals(selectorEl, 0, 'rated');
    updateFeedbackText(feedbackEl, 0);
}

export function setupCostTierSelector(selectorId, inputId) {
    const selector = document.getElementById(selectorId);
    const input = document.getElementById(inputId);
    if (!selector || !input) return;
    selector.addEventListener('click', (e) => {
        if (e.target.matches('span')) {
            const value = e.target.dataset.value;
            const newValue = (input.value === value) ? '' : value;
            updateCostTierDisplay(selector, input, newValue);
        }
    });
}

function updateCostTierDisplay(selectorEl, inputEl, selectedValue) {
    if (!selectorEl || !inputEl) return;
    inputEl.value = selectedValue || '';
    selectorEl.querySelectorAll('span').forEach(span => {
        span.classList.toggle('selected', span.dataset.value == selectedValue);
    });
}

export function updateCostTierSelector(selectedValue) {
    const selector = document.getElementById('costTierSelector');
    const input = document.getElementById('manualCostTierInput');
    if (selector && input) {
        updateCostTierDisplay(selector, input, selectedValue);
    }
}

export function updateMainCostTierSelector(selectedValue) {
    const selector = document.getElementById('mainCostTierSelector');
    const input = document.getElementById('mainCostTierInput');
    if (selector && input) {
        updateCostTierDisplay(selector, input, selectedValue);
    }
}

export function updateCostTierTooltips() {
    document.querySelectorAll('.cost-tier-selector').forEach(selector => {
        selector.querySelectorAll('span').forEach(span => {
            const tierValue = span.dataset.value;
            span.title = state.appSettings[`cost_tier_${tierValue}_label`] || `Tier ${tierValue}`;
        });
    });
}

export function updateSortIcons() {
    document.getElementById('sortAscIcon').classList.toggle('hidden', state.currentSortDirection === 'desc');
    document.getElementById('sortDescIcon').classList.toggle('hidden', state.currentSortDirection === 'asc');
}

export async function saveFocalPoint(vivinoUrl, focalPoint) {
    try {
        await apiCall('api/wine/focal-point', {
            method: 'POST',
            body: JSON.stringify({ vivino_url: vivinoUrl, focal_point: focalPoint })
        }, 'notesMessage');
        fetchInventory();
    } catch (error) {
        console.error("Failed to save focal point:", error);
    }
}
// --- function to set the visual state of the image editor ---
export function applyFocalPointAndZoom(focalPoint, zoom, imageUrl) {
    const draggableImage = document.getElementById('draggableImage');
    const zoomSlider = document.getElementById('zoomSlider');

    if (!draggableImage) return;

    // 1. Set the image source (if provided)
    if (imageUrl) {
        draggableImage.src = imageUrl;
    }

    // 2. Apply focal point (object-position)
    // This is what the drag handler modifies, and we set it here on load.
    draggableImage.style.objectPosition = focalPoint || '50% 50%';

    // 3. Apply zoom (scale transform)
    const newZoom = parseFloat(zoom) || 1.0;
    draggableImage.style.transform = `scale(${newZoom})`;
    
    // 4. Set the slider value
    if (zoomSlider) {
        zoomSlider.value = newZoom;
    }
}

export function updateCollapseIcon() {
    const addWineSection = document.getElementById('addWineSection');
    const collapseIcon = document.getElementById('collapseIcon');
    if (addWineSection && collapseIcon) {
        const isExpanded = addWineSection.classList.contains('is-expanded');
        collapseIcon.style.transform = isExpanded ? 'rotate(90deg)' : 'rotate(0deg)';
    }
}

export function collapseAddWinePanel() {
    const addWineSection = document.getElementById('addWineSection');
    if (addWineSection && addWineSection.classList.contains('is-expanded')) {
        addWineSection.classList.remove('is-expanded');
        localStorage.setItem('addWinePanelState', 'collapsed');
        updateCollapseIcon();
    }
    clearTimeout(state.panelCollapseTimer);
    state.setPanelCollapseTimer(null);
        // Also hide any status message when collapsing
    const msgEl = document.getElementById('scanMessage');
    if (msgEl) {
        msgEl.classList.add('hidden');
        msgEl.textContent = '';
        clearTimeout(msgEl._hideTimer);
    }
}

export function startPanelCollapseTimer() {
    clearTimeout(state.panelCollapseTimer);
    const timer = setTimeout(collapseAddWinePanel, 180000); // 180 seconds
    state.setPanelCollapseTimer(timer);
}

export function resetVivinoPanel() {
    document.getElementById('vivinoSearchInput').value = '';
    document.getElementById('vivinoUrlInput').value = '';
    document.getElementById('quantityInput').value = '1';
    updateMainCostTierSelector(null);
}
export function showScanMessage(message, type = 'info', duration = 7000) {
    const msgEl = document.getElementById('scanMessage');
    if (!msgEl) return;

    // Style based on message type
    msgEl.classList.remove('hidden', 'text-green-600', 'text-red-600', 'text-blue-600');
    msgEl.classList.add(
        type === 'success' ? 'text-green-600' :
        type === 'error'   ? 'text-red-600' :
                             'text-blue-600'
    );
    msgEl.textContent = message;

    // Show and auto-hide after `duration` ms
    clearTimeout(msgEl._hideTimer);
    msgEl._hideTimer = setTimeout(() => {
        msgEl.classList.add('hidden');
        msgEl.textContent = '';
    }, duration);

    // Allow manual dismissal by click
    msgEl.onclick = () => {
        msgEl.classList.add('hidden');
        msgEl.textContent = '';
        clearTimeout(msgEl._hideTimer);
    };
}