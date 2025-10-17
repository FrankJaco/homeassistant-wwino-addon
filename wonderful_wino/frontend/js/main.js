// js/main.js
// Main application entry point. Initializes the app and sets up event listeners.

import * as state from './state.js';
import { BASE_URL, VIVINO_SEARCH_URL } from './config.js';
import { loadHTML, apiCall, showMessage } from './utils.js';
import { fetchInventory, updateDisplayedInventory } from './inventory.js';
import { openModal, closeModal, promptForVintage } from './modals.js';
// Import getNotesFormData along with the others
import { getEntryFormData, checkFormChanges, fetchAndDisplayConsumptionHistory, getNotesFormData } from './forms.js';
import { 
    updateSortIcons, setupVintageControls, setupCostTierSelector, setupStarRating, 
    updateCostTierTooltips, updateCollapseIcon, collapseAddWinePanel, 
    startPanelCollapseTimer, resetVivinoPanel, saveFocalPoint 
} from './ui.js';

async function fetchSettings() {
    try {
        const response = await fetch(`${BASE_URL}api/settings`);
        if (!response.ok) throw new Error('Failed to fetch settings');
        const settings = await response.json();
        state.setAppSettings(settings);
        updateCostTierTooltips();
    } catch (error) {
        console.error('Error fetching settings:', error);
    }
}

function setupEventListeners() {
    document.getElementById('settingsButton').addEventListener('click', () => openModal('settingsModal'));
    
    document.getElementById('themeToggle').addEventListener('click', () => {
        document.body.classList.toggle('dark-theme');
        const isDark = document.body.classList.contains('dark-theme');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        document.getElementById('themeIcon').textContent = isDark ? '🌙' : '☀️';
    });

    // --- Global Event Delegation ---
    document.body.addEventListener('click', (e) => {
        const addWineHeader = e.target.closest('#addWineHeader');
        if (addWineHeader) {
            if (e.target.id === 'addViaVivinoBtn') { /* ... (handling logic below) ... */ }
            if (e.target.id === 'openEntryModalBtn') { /* ... */ }
            if (e.target.id === 'otherToolsBtn') { /* ... */ }
            if (e.target.id === 'manualHelpIcon') { openModal('helpModal', { topic: 'manual' }); return; }
            if (e.target.id === 'vivinoHelpIcon') { openModal('helpModal', { topic: 'vivino' }); return; }

            const addWineSection = document.getElementById('addWineSection');
            if (addWineSection) {
                 if (['addViaVivinoBtn', 'openEntryModalBtn', 'otherToolsBtn'].includes(e.target.id)) {
                    const isExpanded = addWineSection.classList.contains('is-expanded');
                    const openAction = () => {
                        if (e.target.id === 'addViaVivinoBtn') resetVivinoPanel();
                        if (e.target.id === 'openEntryModalBtn') openModal('entryModal', { mode: 'add' });
                        if (e.target.id === 'otherToolsBtn') openModal('otherToolsModal');
                    };
                    if (!isExpanded) {
                        addWineSection.classList.add('is-expanded');
                        localStorage.setItem('addWinePanelState', 'expanded');
                        updateCollapseIcon();
                        startPanelCollapseTimer();
                        if (e.target.id === 'addViaVivinoBtn') resetVivinoPanel();
                    }
                    if (e.target.id !== 'addViaVivinoBtn') {
                        collapseAddWinePanel();
                        setTimeout(openAction, 500);
                    } else if (isExpanded) {
                        resetVivinoPanel();
                        startPanelCollapseTimer();
                    }
                 } else {
                    const isNowExpanded = addWineSection.classList.toggle('is-expanded');
                    localStorage.setItem('addWinePanelState', isNowExpanded ? 'expanded' : 'collapsed');
                    updateCollapseIcon();
                    if (isNowExpanded) {
                        resetVivinoPanel();
                        startPanelCollapseTimer();
                    } else {
                        clearTimeout(state.panelCollapseTimer);
                        state.setPanelCollapseTimer(null);
                    }
                 }
            }
            return;
        }

        if (e.target.closest('#inventory-filters') && e.target.matches('.filter-button')) {
            state.setCurrentFilter(e.target.dataset.filter);
            document.querySelectorAll('#inventory-filters .filter-button').forEach(btn => btn.classList.remove('active'));
            e.target.classList.add('active');
            const heading = document.getElementById('inventory-heading');
            const headingText = `Wine ${state.currentFilter.replace('_', ' ')}`;
            heading.textContent = headingText.charAt(0).toUpperCase() + headingText.slice(1);
            fetchInventory();
        }
        
        if (e.target.closest('#type-filters') && e.target.closest('.type-filter-button')) {
            const button = e.target.closest('.type-filter-button');
            state.setCurrentTypeFilter(button.dataset.typeFilter);
            document.querySelectorAll('#type-filters .type-filter-button').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            updateDisplayedInventory();
        }
        
        if (e.target.closest('#sortDirectionToggle')) {
            state.setCurrentSortDirection(state.currentSortDirection === 'asc' ? 'desc' : 'asc');
            updateSortIcons();
            updateDisplayedInventory();
        }
        
        if (e.target.closest('#refreshInventoryBtn')) fetchInventory();
        if (e.target.closest('.cost-tier-selector') || e.target.closest('.taste-rating-selector')) setTimeout(checkFormChanges, 0);
        
        if (e.target.id === 'entrySaveAsNewWineBtn') {
            const payload = getEntryFormData();
            apiCall('add-manual-wine', { method: 'POST', body: JSON.stringify(payload) }, 'entryMessage', e.target)
                .then(() => { fetchInventory(); setTimeout(closeModal, 1500); })
                .catch(err => console.error(err));
        }

        if (e.target.id === 'toggleImageUrlLock') {
             const imageUrlInput = document.getElementById('imageUrlInput');
             const focalPointEditor = document.getElementById('focalPointEditor');
             const isReadonly = imageUrlInput.hasAttribute('readonly');
             imageUrlInput.toggleAttribute('readonly', !isReadonly);
             e.target.textContent = isReadonly ? '🔓' : '🔒';
             focalPointEditor.classList.toggle('is-unlocked', isReadonly);
             if (isReadonly) { imageUrlInput.focus(); }
        }

        if (e.target.id === 'logSortToggleBtn') {
            state.setConsumptionLogSortOrder(state.consumptionLogSortOrder === 'desc' ? 'asc' : 'desc');
            if (state.currentWineForLog) {
                fetchAndDisplayConsumptionHistory(state.currentWineForLog, state.consumptionLogSortOrder);
            }
        }
    });

    document.body.addEventListener('change', (e) => {
        if (e.target.id === 'sortSelect') {
            state.setCurrentSortBy(e.target.value);
            updateDisplayedInventory();
        }
        if (e.target.id === 'nvCheckbox') checkFormChanges();
    });

    document.body.addEventListener('input', (e) => {
        if (e.target.closest('#entryForm')) checkFormChanges();
    });
    
    document.body.addEventListener('submit', async (e) => {
        e.preventDefault();
        switch (e.target.id) {
            case 'vivinoSearchForm':
                window.open(`${VIVINO_SEARCH_URL}${encodeURIComponent(document.getElementById('vivinoSearchInput').value)}`, '_blank');
                e.target.reset();
                break;
            case 'scanWineForm':
                let vivinoUrl = document.getElementById('vivinoUrlInput').value;
                if (!/https:\/\/www\.vivino\.com\/.*\/w\/\d+/.test(vivinoUrl)) {
                    showMessage('scanMessage', "Invalid URL. Please use a specific Vivino wine page.", 'error');
                    return;
                }
                if (!/year=\d{4}/.test(vivinoUrl)) {
                    try {
                        const result = await promptForVintage();
                        if (result.vintage) {
                            const url = new URL(vivinoUrl);
                            url.searchParams.set('year', result.vintage);
                            vivinoUrl = url.toString();
                        }
                    } catch (error) {
                        if(error !== 'cancelled') showMessage('scanMessage', 'Action cancelled.', 'info');
                        return;
                    }
                }
                const payload = {
                    vivino_url: vivinoUrl,
                    quantity: parseInt(document.getElementById('quantityInput').value, 10) || 1,
                    cost_tier: parseInt(document.getElementById('mainCostTierInput').value, 10) || null
                };
                try {
                    await apiCall('scan-wine', { method: 'POST', body: JSON.stringify(payload) }, 'scanMessage', e.target.querySelector('button[type="submit"]'));
                    resetVivinoPanel();
                    fetchInventory();
                    startPanelCollapseTimer();
                } catch (error) {}
                break;
            case 'entryForm':
                const isEditMode = !!document.getElementById('entryVivinoUrl').value;
                const entryPayload = getEntryFormData();
                if (isEditMode) entryPayload.vivino_url = document.getElementById('entryVivinoUrl').value;
                try {
                    await apiCall(isEditMode ? 'edit-wine' : 'add-manual-wine', { method: 'POST', body: JSON.stringify(entryPayload) }, 'entryMessage', e.target.querySelector('button[type="submit"]'));
                    fetchInventory();
                    setTimeout(closeModal, 1500);
                } catch (error) {}
                break;
            case 'tasteForm':
                const tastePayload = {
                    vivino_url: document.getElementById('tasteVivinoUrl').value,
                    personal_rating: parseFloat(document.getElementById('tasteRatingInput').value) || null
                };
                try {
                    await apiCall('inventory/wine/consume', { method: 'POST', body: JSON.stringify(tastePayload) }, 'inventoryMessage', e.target.querySelector('button[type="submit"]'));
                    closeModal();
                    fetchInventory();
                } catch (error) {}
                break;
            case 'notesForm':
                // Use the new getNotesFormData function to build the payload
                const notesPayload = getNotesFormData();
                try {
                    // The API endpoint might need to be updated to handle the new fields
                    await apiCall('api/wine/notes', { method: 'POST', body: JSON.stringify(notesPayload) }, 'notesMessage', e.target.querySelector('button[type="submit"]'));
                    fetchInventory();
                    setTimeout(closeModal, 1500);
                } catch (error) {}
                break;
        }
    });

    // --- Focal Point Drag Logic ---
    let isDragging = false; let startY = 0; let startFocalPercent = 50;
    const getPointerY = (e) => e.touches ? e.touches[0].clientY : e.clientY;
    const startDrag = (e) => {
        const editor = document.getElementById('focalPointEditor');
        if (e.target.id !== 'draggableImage' || !editor?.classList.contains('is-unlocked')) return;
        e.preventDefault();
        isDragging = true; editor.classList.add('is-dragging'); startY = getPointerY(e);
        const currentPos = e.target.style.objectPosition || '50% 50%';
        startFocalPercent = parseFloat(currentPos.split(' ')[1]);
    };
    const onDrag = (e) => {
        if (!isDragging) return; e.preventDefault();
        const editor = document.getElementById('focalPointEditor');
        const img = document.getElementById('draggableImage');
        if (!editor || !img) return;
        const parentHeight = editor.clientHeight;
        const renderedImageHeight = (img.naturalHeight / img.naturalWidth) * editor.clientWidth;
        if (renderedImageHeight <= parentHeight || !img.naturalHeight) return;
        const deltaY = getPointerY(e) - startY;
        const travelRange = renderedImageHeight - parentHeight;
        const newFocalPercent = startFocalPercent - ((deltaY / travelRange) * 100);
        img.style.objectPosition = `50% ${Math.max(0, Math.min(100, newFocalPercent)).toFixed(2)}%`;
    };
    const endDrag = () => {
        if (!isDragging) return; isDragging = false;
        const editor = document.getElementById('focalPointEditor');
        if (editor) editor.classList.remove('is-dragging');
        const vivinoUrl = document.getElementById('notesVivinoUrl')?.value;
        const focalPoint = document.getElementById('draggableImage')?.style.objectPosition;
        if (vivinoUrl && focalPoint) saveFocalPoint(vivinoUrl, focalPoint.split(' ')[1]);
    };
    document.body.addEventListener('mousedown', startDrag); document.body.addEventListener('touchstart', startDrag, { passive: false });
    window.addEventListener('mousemove', onDrag, { passive: false }); window.addEventListener('touchmove', onDrag, { passive: false });
    window.addEventListener('mouseup', endDrag); window.addEventListener('touchend', endDrag);
}

document.addEventListener('keydown', (e) => {
    if (!state.openModalElement) return;
    if (e.key === 'Escape') {
        if (state.openModalElement.id === 'nvPromptModal' && window.nvPromptResolver) {
            window.nvPromptResolver.reject('cancelled');
        } else {
            closeModal();
        }
    }
});

// --- App Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    // Load all HTML components
    await Promise.all([
        loadHTML('components/add-wine.html', document.getElementById('addWineSection')),
        loadHTML('components/inventory.html', document.getElementById('inventorySection')),
        loadHTML('components/manual-entry-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/notes-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/settings-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/help-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/other-tools-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/taste-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/nv-prompt-modal.html', document.getElementById('modalContainer'), true)
    ]);

    // Initial Setup
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') document.body.classList.add('dark-theme');
    document.getElementById('themeIcon').textContent = savedTheme === 'dark' ? '🌙' : '☀️';

    localStorage.removeItem('addWinePanelState'); // Ensure panel is closed on startup
    updateCollapseIcon();
    updateSortIcons();

    await fetchSettings();
    fetchInventory();

    // Wire up UI components and event listeners
    setupEventListeners();
    setupVintageControls();
    setupCostTierSelector('mainCostTierSelector', 'mainCostTierInput');
    setupCostTierSelector('costTierSelector', 'manualCostTierInput');
    setupStarRating('tasteRatingSelector', 'tasteRatingInput', 'tasteRatingFeedback');
    setupStarRating('editTasteRatingSelector', 'manualTasteRatingInput', 'editTasteRatingFeedback');
    
    document.getElementById('addWineContent')?.addEventListener('input', startPanelCollapseTimer);
    document.getElementById('addWineContent')?.addEventListener('click', startPanelCollapseTimer);

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') fetchInventory();
    });
});
