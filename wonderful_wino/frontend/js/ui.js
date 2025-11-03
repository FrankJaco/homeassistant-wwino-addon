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
    if (feedbackEl) feedbackEl.textContent = rating > 0 ? `${rating} star${rating !== 1 ? 's' : ''}` : '';
}

export function resetTasteStars() {
    const inputEl = document.getElementById('tasteRatingInput');
    const selectorEl = document.getElementById('tasteRatingSelector');
    const feedbackEl = document.getElementById('tasteRatingFeedback');
    if(inputEl) inputEl.value = '';
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
