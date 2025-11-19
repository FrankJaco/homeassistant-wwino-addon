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

export function setupStarRating(selectorId, inputId, feedbackId) {
    const selectorEl = document.getElementById(selectorId);
    const inputEl = document.getElementById(inputId);
    const feedbackEl = document.getElementById(feedbackId);
    if (!selectorEl || !inputEl) return;
    
    // 1. Handle Mouse Interaction on Stars (Hover effects)
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
        // On mouse leave, revert visuals to the actual value in the input
        const currentRating = parseFloat(inputEl.value) || 0;
        updateStarVisuals(selectorEl, currentRating, 'rated');
        updateFeedbackText(feedbackEl, currentRating);
    });

    // 2. Handle Clicks on Stars
    selectorEl.addEventListener('click', e => {
        if (!e.target.matches('span')) return;
        const star = e.target;
        const starRect = star.getBoundingClientRect();
        const isHalf = (e.clientX - starRect.left) < (starRect.width / 2);
        const rating = parseInt(star.dataset.value, 10) - (isHalf ? 0.5 : 0);
        
        // FORCE SET the value. We removed the toggle/clear logic to ensure stability.
        inputEl.value = rating;
        
        // CRITICAL: Manually trigger the 'input' event so the listener below runs.
        // This ensures visuals and state stay perfectly in sync.
        inputEl.dispatchEvent(new Event('input', { bubbles: true }));
    });

    // 3. Handle Input Changes (Spinner or Manual Typing)
    inputEl.addEventListener('input', () => {
        let val = parseFloat(inputEl.value);
        
        // Visual clamping (doesn't force input value change immediately to allow typing)
        let displayVal = val;
        if (val < 0) displayVal = 0;
        if (val > 5) displayVal = 5;

        if (!isNaN(displayVal)) {
            updateStarVisuals(selectorEl, displayVal, 'rated');
            updateFeedbackText(feedbackEl, displayVal);
        } else {
            // If empty or invalid, show 0 stars
            updateStarVisuals(selectorEl, 0, 'rated');
            updateFeedbackText(feedbackEl, 0);
        }
    });
    
    // 4. Enforce Strict Bounds on Blur
    inputEl.addEventListener('blur', () => {
         let val = parseFloat(inputEl.value);
         if (val > 5) inputEl.value = 5;
         if (val < 0) inputEl.value = 0;
         // Re-trigger visual update to be safe
         const finalVal = parseFloat(inputEl.value) || 0;
         updateStarVisuals(selectorEl, finalVal, 'rated');
         updateFeedbackText(feedbackEl, finalVal);
    });
}

export function updateStarVisuals(selectorEl, rating, stateClass) {
    if (!selectorEl) return;
    selectorEl.querySelectorAll('span').forEach((star, index) => {
        const starValue = index + 1;
        star.className = '';
        
        // Full Star
        if (rating >= starValue) {
            star.classList.add(`${stateClass}`);
        } 
        // Partial/Half Star logic
        else if (rating > index && rating < starValue) {
            star.classList.add(`${stateClass}-half`);
        }
    });
}

export function updateFeedbackText(feedbackEl, rating) {
    if (feedbackEl) feedbackEl.textContent = rating > 0 ? `${rating} star${rating !== 1 ? 's' : ''}` : '';
}

export function resetTasteStars() {
    const inputEl = document.getElementById('tasteRatingInput');
    const selectorEl = document.getElementById('tasteRatingSelector');
    const feedbackEl = document.getElementById('tasteRatingFeedback');
    
    if(inputEl) inputEl.value = ''; // Reset to empty
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

// --- UPDATED FUNCTION to set the visual state of the image editor ---
export function applyFocalPointAndZoom(focalPoint, zoom, tilt, imageUrl) {
    const draggableImage = document.getElementById('draggableImage');
    const zoomSlider = document.getElementById('zoomSlider');
    const tiltSlider = document.getElementById('tiltSlider');

    if (!draggableImage) return;

    // 1. Set the image source (if provided)
    if (imageUrl) {
        draggableImage.src = imageUrl;
    }

    // 2. Apply focal point (object-position)
    draggableImage.style.objectPosition = focalPoint || '50% 50%';

    // 3. Apply zoom and tilt (transform)
    const newZoom = parseFloat(zoom) || 1.0;
    const newTilt = parseFloat(tilt) || 0;
    
    draggableImage.style.transform = `scale(${newZoom}) rotate(${newTilt}deg)`;
    
    // 4. Set the slider values
    if (zoomSlider) {
        zoomSlider.value = newZoom;
    }
    if (tiltSlider) {
        tiltSlider.value = newTilt;
    }
}

// --- NEW HELPER: Centralized visual update logic for listeners ---
export function updateImageTransform() {
    const img = document.getElementById('draggableImage');
    const zoomSlider = document.getElementById('zoomSlider');
    const tiltSlider = document.getElementById('tiltSlider');
    
    if (!img || !zoomSlider || !tiltSlider) return;

    const zoom = parseFloat(zoomSlider.value) || 1.0;
    const tilt = parseFloat(tiltSlider.value) || 0;

    img.style.transform = `scale(${zoom}) rotate(${tilt}deg)`;
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