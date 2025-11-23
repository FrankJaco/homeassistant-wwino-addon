// js/modals.js
// Handles all modal interactions: opening, closing, preparing content.

import * as state from './state.js';
import { updateStarVisuals, updateFeedbackText, updateCostTierSelector, resetTasteStars, applyFocalPointAndZoom, updateImageTransform } from './ui.js';
import { fetchAndDisplayConsumptionHistory, getEntryFormData, checkFormChanges, getNotesFormData } from './forms.js';
import { fetchInventory } from './inventory.js';
import { apiCall } from './utils.js';
import { DEFAULT_COST_TIERS } from './config.js';
import { BASE_URL } from './config.js';

let initialCostTierValues = {};

// --- Modal Management ---

export function openModal(modalId, options = {}) {
    const modalEl = document.getElementById(modalId);
    if (!modalEl || (state.openModalElement && state.openModalElement.id === modalId)) return;
    state.setLastFocusedElement(document.activeElement);

    switch (modalId) {
        case 'entryModal': prepareEntryModal(options.mode, options.wine); break;
        case 'tasteModal': prepareTasteModal(options.wine); break;
        case 'notesModal': prepareNotesModal(options.wine); break;
        case 'settingsModal': prepareSettingsModal(); break;
        case 'helpModal': prepareHelpModal(options); break;
        case 'otherToolsModal': /* No prep needed */ break;
    }

    modalEl.classList.remove('hidden');
    state.setOpenModalElement(modalEl);

    const focusableElements = modalEl.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (focusableElements.length > 0) {
        const inputToFocus = modalId === 'nvPromptModal'
            ? modalEl.querySelector('#nvPromptVintageInput')
            : focusableElements[0];
        if (inputToFocus) inputToFocus.focus();
    }
}
// Expose to global scope for onclick attributes in HTML
window.closeModal = closeModal;
export function closeModal() {
    if (!state.openModalElement) return;
    const modalToClose = state.openModalElement;
    state.setOpenModalElement(null);
    const vintageInput = document.getElementById('manualVintageInput');
    if (vintageInput) {
        vintageInput.value = '';
    }
    modalToClose.classList.add('hidden');

    if (modalToClose.id === 'helpModal' && window.fromSettings) {
        window.fromSettings = false;
        openModal('settingsModal');
    } else if (state.lastFocusedElement) {
        state.lastFocusedElement.focus();
        state.setLastFocusedElement(null);
    }
}


// --- Modal Preparation ---

function prepareEntryModal(mode = 'add', wine = {}) {
    const form = document.getElementById('entryForm');
    if (!form) return;
    form.reset();
    document.getElementById('entryMessage').classList.add('hidden');
    const title = document.getElementById('entryModalTitle');
    const submitBtn = document.getElementById('entrySubmitBtn');
    const saveAsNewWineBtn = document.getElementById('entrySaveAsNewWineBtn');
    const vintageInput = document.getElementById('manualVintageInput');
    const nvCheckbox = document.getElementById('nvCheckbox');
    
    // Elements for the star rating system
    const ratingInput = document.getElementById('manualTasteRatingInput');
    const ratingSelector = document.getElementById('editTasteRatingSelector');
    const ratingFeedback = document.getElementById('editTasteRatingFeedback');

    vintageInput.disabled = false;
    vintageInput.required = true;
    nvCheckbox.checked = false;

    if (mode === 'edit') {
        title.textContent = 'Edit Wine';
        submitBtn.textContent = 'Save';
        saveAsNewWineBtn.classList.remove('hidden');

        document.getElementById('entryVivinoUrl').value = wine.vivino_url;
        document.getElementById('manualImageUrlInput').value = wine.image_url || '';
        document.getElementById('manualTastingNotesInput').value = wine.tasting_notes || '';
        document.getElementById('manualNameInput').value = wine.name;
        if (wine.vintage) {
            vintageInput.value = wine.vintage;
        } else {
            vintageInput.value = '';
            vintageInput.disabled = true;
            vintageInput.required = false;
            nvCheckbox.checked = true;
        }
        document.getElementById('manualVarietalInput').value = wine.varietal !== 'Unknown Varietal' ? wine.varietal : '';
        document.getElementById('manualRegionInput').value = wine.region !== 'Unknown Region' ? wine.region : '';
        document.getElementById('manualCountryInput').value = wine.country !== 'Unknown Country' ? wine.country : '';
        document.getElementById('manualWineTypeInput').value = wine.wine_type || '';
        document.getElementById('manualAlcoholInput').value = wine.alcohol_percent || '';
        document.getElementById('manualQuantityInput').value = wine.quantity;
        updateCostTierSelector(wine.cost_tier);
        
        // --- UPDATED: Handle visible rating input ---
        // Use explicit check so we show empty string (placeholder) instead of "0" if null
        const rating = wine.personal_rating;
        ratingInput.value = (rating !== null && rating !== undefined) ? rating : '';
        updateStarVisuals(ratingSelector, rating || 0, 'rated');
        updateFeedbackText(ratingFeedback, rating || 0);

        state.setInitialEntryFormData(getEntryFormData());
        saveAsNewWineBtn.disabled = true;
        saveAsNewWineBtn.title = 'Change a field to enable saving as a new wine';

    } else { // 'add' mode
        title.textContent = 'Add Wine Manually';
        submitBtn.textContent = 'Add Wine';
        saveAsNewWineBtn.classList.add('hidden');
        state.setInitialEntryFormData({}); // Clear initial data

        document.getElementById('entryVivinoUrl').value = '';
        document.getElementById('manualImageUrlInput').value = '';
        document.getElementById('manualQuantityInput').value = 1;
        updateCostTierSelector(null);
        
        // --- UPDATED: Reset rating to clean state ---
        ratingInput.value = ''; 
        updateStarVisuals(ratingSelector, 0, 'rated');
        updateFeedbackText(ratingFeedback, 0);
    }
}

function prepareTasteModal(wine) {
    const vivinoUrl = document.getElementById('tasteVivinoUrl');
    const wineName = document.getElementById('tasteModalWineName');
    if (vivinoUrl) vivinoUrl.value = wine.vivino_url;
    if (wineName) wineName.textContent = `${wine.name} (${wine.vintage || 'NV'})`;
    resetTasteStars();
}

// Unified event handler for both zoom and tilt
const handleImageControlChange = () => {
    updateImageTransform(); // This function in ui.js now reads both sliders
};

function prepareNotesModal(wine) {
    const imageUrlInput = document.getElementById('imageUrlInput');
    const toggleBtn = document.getElementById('toggleImageUrlLock');
    const focalPointEditor = document.getElementById('focalPointEditor');
    const draggableImage = document.getElementById('draggableImage');
    
    const zoomSlider = document.getElementById('zoomSlider');
    const zoomSliderContainer = document.getElementById('zoomSliderContainer');
    
    const tiltSlider = document.getElementById('tiltSlider');
    const tiltSliderContainer = document.getElementById('tiltSliderContainer');

    document.getElementById('notesVivinoUrl').value = wine.vivino_url;
    document.getElementById('notesModalWineName').textContent = `${wine.name} (${wine.vintage || 'NV'})`;
    document.getElementById('tastingNotesInput').value = wine.tasting_notes || '';
    document.getElementById('notesMessage').classList.add('hidden');

    const imageUrl = wine.image_url || '';
    imageUrlInput.value = imageUrl;
    draggableImage.src = imageUrl;

    // --- MODIFIED: Handle new "X% Y%" format and old "Y%" format ---
    let focalPoint = wine.image_focal_point || '50% 50%';
    // Handle backward compatibility for old format (which was just Y-percentage string)
    if (focalPoint && !focalPoint.includes(' ')) {
        focalPoint = `50% ${focalPoint}`;
    }
    // --- END MODIFICATION ---

    const zoomLevel = wine.image_zoom || 1;
    const tiltLevel = wine.image_tilt || 0; // Default to 0 if undefined

    // This function now handles zoom AND tilt
    applyFocalPointAndZoom(focalPoint, zoomLevel, tiltLevel, imageUrl);

    // Reset lock and disabled states on modal open
    imageUrlInput.setAttribute('readonly', true);
    toggleBtn.textContent = '🔒';
    focalPointEditor.classList.remove('is-unlocked');
    
    // Disable inputs
    zoomSlider.disabled = true;
    zoomSliderContainer.classList.add('opacity-50');
    tiltSlider.disabled = true;
    tiltSliderContainer.classList.add('opacity-50');
    
    // Attach listeners
    zoomSlider.removeEventListener('input', handleImageControlChange);
    zoomSlider.addEventListener('input', handleImageControlChange);
    
    tiltSlider.removeEventListener('input', handleImageControlChange);
    tiltSlider.addEventListener('input', handleImageControlChange);

    fetchAndDisplayConsumptionHistory(wine, state.consumptionLogSortOrder);
}

function prepareSettingsModal() {
    populateCostTierFieldsFromSettings();
    initialCostTierValues = {
        t1: document.getElementById('tier1').value,
        t2r: document.getElementById('tier2Right').value,
        t3r: document.getElementById('tier3Right').value,
        t4r: document.getElementById('tier4Right').value,
    };
    document.getElementById('costTierResetBtn').textContent = 'Default';
    document.getElementById('settingsMessage').classList.add('hidden');
}

function prepareHelpModal(options = {}) {
    const titleEl = document.getElementById('helpModalTitle');
    const maintenanceContent = document.getElementById('maintenance-help-content');
    const manualContent = document.getElementById('manual-help-content');
    const vivinoContent = document.getElementById('vivino-help-content');

    maintenanceContent.classList.add('hidden');
    manualContent.classList.add('hidden');
    vivinoContent.classList.add('hidden');

    if (options.topic === 'manual') {
        titleEl.textContent = 'Manual Entry Help';
        manualContent.classList.remove('hidden');
    } else if (options.topic === 'vivino') {
        titleEl.textContent = 'Vivino URL Help';
        vivinoContent.classList.remove('hidden');
    } else {
        titleEl.textContent = 'Maintenance Help';
        maintenanceContent.classList.remove('hidden');
    }
}

export function promptForVintage() {
    return new Promise((resolve, reject) => {
        window.nvPromptResolver = { resolve, reject };
        openModal('nvPromptModal');
        const confirmNvBtn = document.getElementById('confirmNvBtn');
        const applyVintageForm = document.getElementById('applyVintageForm');
        const vintageInput = document.getElementById('nvPromptVintageInput');
        const cancelBtn = document.getElementById('nvPromptCancelBtn');
        if (!confirmNvBtn || !applyVintageForm || !vintageInput || !cancelBtn) return reject('Modal elements not found');

        const currentYear = new Date().getFullYear();
        vintageInput.min = "1900";
        vintageInput.max = currentYear;
        vintageInput.value = '';

        const cleanup = () => {
            confirmNvBtn.removeEventListener('click', handleConfirmNv);
            applyVintageForm.removeEventListener('submit', handleApplyVintage);
            cancelBtn.removeEventListener('click', handleCancel);
            closeModal();
            window.nvPromptResolver = null;
        };
        const handleConfirmNv = () => { cleanup(); resolve({ isNv: true }); };
        const handleApplyVintage = (e) => {
            e.preventDefault();
            const vintage = vintageInput.value;
            if (vintage && parseInt(vintage) >= 1900 && parseInt(vintage) <= currentYear) {
                cleanup();
                resolve({ vintage: vintage });
            } else {
                vintageInput.classList.add('border-red-500');
                vintageInput.focus();
            }
        };
        const handleCancel = () => { cleanup(); reject('cancelled'); };

        vintageInput.addEventListener('input', () => vintageInput.classList.remove('border-red-500'));
        confirmNvBtn.addEventListener('click', handleConfirmNv);
        applyVintageForm.addEventListener('submit', handleApplyVintage);
        cancelBtn.addEventListener('click', handleCancel);
    });
}

// --- Settings and Maintenance Functions ---
window.handleSyncAllWines = handleSyncAllWines;
window.handleReinitializeDb = handleReinitializeDb;
window.handleBackupDb = handleBackupDb;
window.handleRestoreDb = handleRestoreDb;
window.handleCostTierReset = handleCostTierReset;
window.saveCostTiers = saveCostTiers;
window.openHelpFromSettings = openHelpFromSettings;
window.checkCostTierChanges = checkCostTierChanges;
window.updateTiers = updateTiers;


async function handleSyncAllWines(messageElementId) {
    if (!confirm('Sync all wines to your Home Assistant To-Do list?')) return;
    await apiCall('sync-all-wines', { method: 'POST' }, messageElementId, document.getElementById('syncAllBtn'));
}

async function handleReinitializeDb(messageElementId) {
    if (!confirm('ARE YOU SURE? This will permanently delete ALL wine data!')) return;
    await apiCall('reinitialize-database-action', { method: 'POST' }, messageElementId, document.getElementById('resetDbBtn'));
    fetchInventory();
}

async function handleBackupDb(messageElementId) {
    if (!confirm('Create a backup of your database? This will overwrite any existing backup file.')) return;
    await apiCall('backup-database', { method: 'POST' }, messageElementId, document.getElementById('backupDbBtn'));
}

async function handleRestoreDb(messageElementId) {
    if (!confirm('ARE YOU SURE? This will overwrite your current database with the backup file. Any changes since the last backup will be lost.')) return;
    await apiCall('restore-database', { method: 'POST' }, messageElementId, document.getElementById('restoreDbBtn'));
    setTimeout(fetchInventory, 1500);
}

function updateTiers() {
    const t1 = parseFloat(document.getElementById('tier1').value) || 0;
    const t2Right = parseFloat(document.getElementById('tier2Right').value) || 0;
    const t3Right = parseFloat(document.getElementById('tier3Right').value) || 0;
    const t4Right = parseFloat(document.getElementById('tier4Right').value) || 0;
    
    document.getElementById('tier2Left').value = t1;
    document.getElementById('tier3Left').value = t2Right;
    document.getElementById('tier4Left').value = t3Right;
    document.getElementById('tier5').value = t4Right;
    validateTiers([t1, t2Right, t3Right, t4Right]);
}

function validateTiers(values) {
    const errorEl = document.getElementById('costTierError');
    const saveBtn = document.getElementById('saveCostTiersBtn');
    if (!errorEl || !saveBtn) return;
    const valid = values.slice(1).every((value, i) => value > values[i]);
    saveBtn.disabled = !valid;
    saveBtn.title = valid ? "" : "Fix ranges before saving";
    errorEl.classList.toggle("hidden", valid);
    if (!valid) errorEl.textContent = "Each tier must be greater than the one before it.";
}

function checkCostTierChanges() {
    const btn = document.getElementById('costTierResetBtn');
    if (!btn) return;
    const currentValues = {
        t1: document.getElementById('tier1').value,
        t2r: document.getElementById('tier2Right').value,
        t3r: document.getElementById('tier3Right').value,
        t4r: document.getElementById('tier4Right').value,
    };
    const hasChanged = Object.keys(currentValues).some(key => currentValues[key] != initialCostTierValues[key]);
    btn.textContent = hasChanged ? 'Reset' : 'Default';
}

function handleCostTierReset() {
    const btn = document.getElementById('costTierResetBtn');
    const valuesToSet = btn.textContent === 'Default' ? DEFAULT_COST_TIERS : initialCostTierValues;
    document.getElementById('tier1').value = valuesToSet.t1;
    document.getElementById('tier2Right').value = valuesToSet.t2r;
    document.getElementById('tier3Right').value = valuesToSet.t3r;
    document.getElementById('tier4Right').value = valuesToSet.t4r;
    updateTiers();
    checkCostTierChanges();
}

async function saveCostTiers() {
    const t1 = document.getElementById('tier1').value;
    const t2r = document.getElementById('tier2Right').value;
    const t3r = document.getElementById('tier3Right').value;
    const t4r = document.getElementById('tier4Right').value;
    const payload = {
        cost_tier_1_label: `Under $${t1}`,
        cost_tier_2_label: `$${t1} - $${t2r}`,
        cost_tier_3_label: `$${t2r} - $${t3r}`,
        cost_tier_4_label: `$${t3r} - $${t4r}`,
        cost_tier_5_label: `Over $${t4r}`
    };
    try {
        await apiCall('api/settings', { method: 'POST', body: JSON.stringify(payload) }, 'settingsMessage', document.getElementById('saveCostTiersBtn'));
        state.setAppSettings({ ...state.appSettings, ...payload });
        updateCostTierTooltips();
    } catch (error) { /* Error already shown */ }
}

function populateCostTierFieldsFromSettings() {
    const parseValue = (label, regex) => {
        const match = label ? label.match(regex) : null;
        return match ? parseFloat(match[1]) : null;
    };
    document.getElementById('tier1').value = parseValue(state.appSettings.cost_tier_1_label, /Under \$([\d.]+)/) ?? DEFAULT_COST_TIERS.t1;
    document.getElementById('tier2Right').value = parseValue(state.appSettings.cost_tier_2_label, / - \$([\d.]+)/) ?? DEFAULT_COST_TIERS.t2r;
    document.getElementById('tier3Right').value = parseValue(state.appSettings.cost_tier_3_label, / - \$([\d.]+)/) ?? DEFAULT_COST_TIERS.t3r;
    document.getElementById('tier4Right').value = parseValue(state.appSettings.cost_tier_4_label, / - \$([\d.]+)/) ?? DEFAULT_COST_TIERS.t4r;
    updateTiers();
}

function openHelpFromSettings() {
    closeModal();
    window.fromSettings = true;
    openModal('helpModal');
}