// js/main.js
// Main application entry point. Initializes the app and sets up event listeners.

import * as state from './state.js';
import { BASE_URL, VIVINO_SEARCH_URL } from './config.js';
import { loadHTML, apiCall, showMessage } from './utils.js';
import { fetchInventory, updateDisplayedInventory } from './inventory.js';
import { openModal, closeModal, promptForVintage } from './modals.js';
import { getEntryFormData, checkFormChanges, fetchAndDisplayConsumptionHistory, getNotesFormData } from './forms.js';
import { 
    updateSortIcons, setupVintageControls, setupCostTierSelector, setupStarRating, 
    updateCostTierTooltips, updateCollapseIcon, collapseAddWinePanel, 
    startPanelCollapseTimer, resetVivinoPanel, saveFocalPoint, 
    // --- EDITED: ADDED showScanMessage for Vivino submission feedback ---
    showScanMessage 
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
            // NOTE: The actual submission logic for 'addViaVivinoBtn' is handled by the form submit listener below.
            if (e.target.id === 'addViaVivinoBtn') { /* ... */ }
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
             
             const zoomSlider = document.getElementById('zoomSlider');
             const zoomSliderContainer = document.getElementById('zoomSliderContainer');
             
             const tiltSlider = document.getElementById('tiltSlider');
             const tiltSliderContainer = document.getElementById('tiltSliderContainer');

             const isReadonly = imageUrlInput.hasAttribute('readonly');

             imageUrlInput.toggleAttribute('readonly', !isReadonly);
             e.target.textContent = isReadonly ? '🔓' : '🔒';
             focalPointEditor.classList.toggle('is-unlocked', isReadonly);
             
             zoomSlider.disabled = !isReadonly;
             zoomSliderContainer.classList.toggle('opacity-50', !isReadonly);
             
             tiltSlider.disabled = !isReadonly;
             tiltSliderContainer.classList.toggle('opacity-50', !isReadonly);

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
                // --- CHANGE 2: Show loading message immediately ---
                showScanMessage("Data acquisition in progress...", 'info', 15000); 

                let vivinoUrl = document.getElementById('vivinoUrlInput').value;
                if (!/https:\/\/www\.vivino\.com\/.*\/w\/\d+/.test(vivinoUrl)) {
                    // Use showScanMessage for the dedicated message element
                    showScanMessage("Invalid URL. Please use a specific Vivino wine page.", 'error'); 
                    return;
                }
                
                // Vintage Prompting Logic
                if (!/year=\d{4}/.test(vivinoUrl)) {
                    try {
                        const result = await promptForVintage();
                        if (result.vintage) {
                            const url = new URL(vivinoUrl);
                            url.searchParams.set('year', result.vintage);
                            vivinoUrl = url.toString();
                        } else {
                            // If the user cancels the vintage prompt
                            showScanMessage('Action cancelled.', 'info');
                            return;
                        }
                    } catch (error) {
                        // Catch error during prompt, which might be 'cancelled' rejection
                        if(error !== 'cancelled') console.error("Vintage prompt error:", error);
                        showScanMessage('Action cancelled.', 'info');
                        return;
                    }
                }

                const payload = {
                    vivino_url: vivinoUrl,
                    quantity: parseInt(document.getElementById('quantityInput').value, 10) || 1,
                    cost_tier: parseInt(document.getElementById('mainCostTierInput').value, 10) || null
                };
                
                try {
                    // Pass null for the message container ID, as we handle success/error messages manually via showScanMessage
                    await apiCall('scan-wine', { method: 'POST', body: JSON.stringify(payload) }, null, e.target.querySelector('button[type="submit"]'));
                    
                    // --- CHANGE 1: Update user-friendly success message ---
                    showScanMessage("Wine facts obtained and stored/updated", 'success');
                    
                    resetVivinoPanel();
                    fetchInventory();
                    startPanelCollapseTimer();

                } catch (error) {
                    console.error('Vivino URL submission error:', error);
                    // Show a robust error message to the user
                    showScanMessage(`Error acquiring wine facts. Please check the URL and try again.`, 'error');
                }
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
                const notesPayload = getNotesFormData();
                try {
                    await apiCall('api/wine/notes', { method: 'POST', body: JSON.stringify(notesPayload) }, 'notesMessage', e.target.querySelector('button[type="submit"]'));
                    fetchInventory();
                    setTimeout(closeModal, 1500);
                } catch (error) {}
                break;
        }
    });

    // --- MODIFIED: Focal Point Drag Logic (Now supports X and Y with Rotation) ---
    let isDragging = false; 
    let startX = 0, startY = 0; 
    let startFocalXPercent = 50, startFocalYPercent = 50;
    
    const getPointer = (e) => e.touches ? { x: e.touches[0].clientX, y: e.touches[0].clientY } : { x: e.clientX, y: e.clientY };
    
    const startDrag = (e) => {
        const editor = document.getElementById('focalPointEditor');
        if (e.target.id !== 'draggableImage' || !editor?.classList.contains('is-unlocked')) return;
        e.preventDefault();
        
        isDragging = true; 
        editor.classList.add('is-dragging'); 
        const pointer = getPointer(e);
        startX = pointer.x;
        startY = pointer.y;
        
        const currentPos = e.target.style.objectPosition || '50% 50%';
        const parts = currentPos.split(' ');
        startFocalXPercent = parseFloat(parts[0]);
        startFocalYPercent = parseFloat(parts[1]);
    };

    const onDrag = (e) => {
        if (!isDragging) return; 
        e.preventDefault();
        
        const editor = document.getElementById('focalPointEditor');
        const img = document.getElementById('draggableImage');
        if (!editor || !img || !img.naturalWidth || !img.naturalHeight) return;

        const pointer = getPointer(e);
        const containerWidth = editor.clientWidth;
        const containerHeight = editor.clientHeight; // containerWidth === containerHeight due to aspect-ratio: 1/1

        // 1. Get image's natural aspect ratio
        const imgRatio = img.naturalWidth / img.naturalHeight;

        // 2. Determine base rendered dimensions based on object-fit: cover in a 1:1 container
        let baseRenderedWidth, baseRenderedHeight;
        if (imgRatio >= 1) { // Image is wide or square, scales to fit container height
            baseRenderedHeight = containerHeight;
            baseRenderedWidth = baseRenderedHeight * imgRatio;
        } else { // Image is tall, scales to fit container width
            baseRenderedWidth = containerWidth;
            baseRenderedHeight = baseRenderedWidth / imgRatio;
        }

        // 3. Apply zoom and get tilt
        const transform = img.style.transform || '';
        let zoom = 1;
        let tilt = 0;
        
        const zoomMatch = transform.match(/scale\(([\d.]+)\)/);
        if (zoomMatch) {
            zoom = parseFloat(zoomMatch[1]);
        }

        // --- FIX 1: Parse rotation to adjust drag direction ---
        const rotateMatch = transform.match(/rotate\(([-\d.]+)deg\)/);
        if (rotateMatch) {
            tilt = parseFloat(rotateMatch[1]);
        }

        const renderedImageWidth = baseRenderedWidth * zoom;
        const renderedImageHeight = baseRenderedHeight * zoom;

        // 4. Calculate overflow/travel range
        const travelRangeX = Math.max(0, renderedImageWidth - containerWidth);
        const travelRangeY = Math.max(0, renderedImageHeight - containerHeight);
        
        // 5. Calculate deltas from start position
        const deltaScreenX = pointer.x - startX;
        const deltaScreenY = pointer.y - startY;

        // --- FIX 1 Cont'd: Rotate screen delta vectors to match image's tilted coordinate system ---
        // We rotate the delta vector by -tilt degrees to map screen movement to image axes.
        const rad = -tilt * (Math.PI / 180);
        const deltaX = deltaScreenX * Math.cos(rad) - deltaScreenY * Math.sin(rad);
        const deltaY = deltaScreenX * Math.sin(rad) + deltaScreenY * Math.cos(rad);

        // 6. Calculate new focal points
        let newFocalXPercent = startFocalXPercent;
        if (travelRangeX > 0) {
            // Convert pixel delta to percentage delta based on travel range
            const pxToPercentX = 100 / travelRangeX;
            newFocalXPercent = startFocalXPercent - (deltaX * pxToPercentX);
        }

        let newFocalYPercent = startFocalYPercent;
        if (travelRangeY > 0) {
            const pxToPercentY = 100 / travelRangeY;
            newFocalYPercent = startFocalYPercent - (deltaY * pxToPercentY);
        }

        // 7. Clamp values between 0% and 100%
        newFocalXPercent = Math.max(0, Math.min(100, newFocalXPercent));
        newFocalYPercent = Math.max(0, Math.min(100, newFocalYPercent));

        const newPos = `${newFocalXPercent.toFixed(2)}% ${newFocalYPercent.toFixed(2)}%`;
        img.style.objectPosition = newPos;
        // Also update transform-origin so zoom stays centered on the focal point
        img.style.transformOrigin = newPos;
    };
    
    const endDrag = () => {
        if (!isDragging) return; 
        isDragging = false;
        const editor = document.getElementById('focalPointEditor');
        if (editor) editor.classList.remove('is-dragging');
        
        const vivinoUrl = document.getElementById('notesVivinoUrl')?.value;
        const focalPoint = document.getElementById('draggableImage')?.style.objectPosition;
        
        // Save the full "X% Y%" string
        if (vivinoUrl && focalPoint) {
            saveFocalPoint(vivinoUrl, focalPoint);
        }
    };
    // --- END MODIFIED DRAG LOGIC ---

    document.body.addEventListener('mousedown', startDrag); 
    document.body.addEventListener('touchstart', startDrag, { passive: false });
    window.addEventListener('mousemove', onDrag, { passive: false }); 
    window.addEventListener('touchmove', onDrag, { passive: false });
    window.addEventListener('mouseup', endDrag); 
    window.addEventListener('touchend', endDrag);
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