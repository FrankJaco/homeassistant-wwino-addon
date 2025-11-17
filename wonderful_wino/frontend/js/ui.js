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
    
    selectorEl.addEventListener('mousemove', e => {
        if (!e.target.matches('span')) return;
        const star = e.target;
        const starRect = star.getBoundingClientRect();
        const isHalf = (e.clientX - starRect.left) < (starRect.width / 2);
        const rating = parseInt(star.dataset.value, 10) - (isHalf ? 0.5 : 0);
        
        // Update input value, visuals, and feedback text
        inputEl.value = rating;
        updateStarVisuals(selectorEl, rating);
        if (feedbackEl) updateFeedbackText(feedbackEl, rating);
    });

    selectorEl.addEventListener('click', e => {
        if (!e.target.matches('span')) return;
        // The click event simply confirms the rating set by mousemove
        const rating = parseFloat(inputEl.value);
        state.setRating(rating); // Store the final rating in state
        updateStarVisuals(selectorEl, rating); // Ensure the visual is locked
    });

    selectorEl.addEventListener('mouseleave', () => {
        // Reset to state rating when mouse leaves
        const currentRating = state.getRating();
        inputEl.value = currentRating;
        updateStarVisuals(selectorEl, currentRating);
        if (feedbackEl) updateFeedbackText(feedbackEl, currentRating);
    });
}

/**
 * Applies the calculated focal point and zoom to the image element.
 * Updates the hidden form fields to keep the state for saving.
 * @param {number} x The x-coordinate of the focal point (0-100).
 * @param {number} y The y-coordinate of the focal point (0-100).
 * @param {number} zoom The zoom level (1.0 to 3.0).
 */
export function applyFocalPointAndZoom(x, y, zoom) {
    const imgEl = document.getElementById('draggableImage');
    const focalXInput = document.getElementById('focalPointX');
    const focalYInput = document.getElementById('focalPointY');
    const zoomSlider = document.getElementById('zoomSlider');

    if (!imgEl) return;

    // 1. Update the visual transform on the image
    const transform = `scale(${zoom}) translate(${50 - x}%, ${50 - y}%)`;
    imgEl.style.transformOrigin = `${x}% ${y}%`;
    imgEl.style.transform = transform;
    
    // 2. Update the hidden form fields to save the current state
    if (focalXInput && focalYInput) {
        focalXInput.value = x.toFixed(2); // Store for saving
        focalYInput.value = y.toFixed(2); // Store for saving
    }
    
    // 3. Update the zoom slider value if it's not the source of the change
    if (zoomSlider) {
        zoomSlider.value = zoom.toFixed(1); // Keep the slider in sync
    }
}

export function updateStarVisuals(selectorEl, rating) {
    if (!selectorEl) return;
    const stars = selectorEl.querySelectorAll('span');
    stars.forEach(star => {
        const starRating = parseInt(star.dataset.value, 10);
        let icon = '★'; // Default full star
        let color = 'text-gray-300'; // Default unrated color

        if (rating >= starRating) {
            color = 'text-yellow-400';
        } else if (rating > starRating - 1) {
            // Check for half star
            icon = '½'; 
            color = 'text-yellow-400';
        }

        star.textContent = icon;
        star.className = `text-2xl cursor-pointer ${color}`;
    });
}

export function updateFeedbackText(feedbackEl, rating) {
    if (!feedbackEl) return;
    const descriptions = {
        0.5: 'Poor', 1.0: 'Bad', 1.5: 'Below Average', 2.0: 'Average', 
        2.5: 'Decent', 3.0: 'Good', 3.5: 'Very Good', 4.0: 'Excellent', 
        4.5: 'Outstanding', 5.0: 'Perfect'
    };
    feedbackEl.textContent = descriptions[rating] || 'Select Rating';
}

export function resetTasteStars(selectorEl, inputEl, feedbackEl) {
    // ... existing resetTasteStars logic ...
}

export function updateCostTierSelector(tier) {
    // ... existing updateCostTierSelector logic ...
}

/**
 * Hides a transient message element.
 * @param {string} elementId - The ID of the message element.
 */
function hideMessage(elementId) {
    const msgEl = document.getElementById(elementId);
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
    msgEl._hideTimer = setTimeout(() => hideMessage('scanMessage'), duration);
    msgEl.classList.remove('hidden'); // Ensure it's visible after setup
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
