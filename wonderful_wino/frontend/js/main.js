// This calculates the base URL to accommodate Home Assistant's Ingress feature,
// which serves the addon from a subpath.
let BASE_URL = '';
if (typeof window !== 'undefined' && typeof window.__ingress_url !== 'undefined' && window.__ingress_url !== '') {
    BASE_URL = window.__ingress_url;
} else {
    const pathParts = window.location.pathname.split('/');
    if (pathParts.length > 0 && pathParts[pathParts.length - 1].includes('.')) { pathParts.pop(); }
    BASE_URL = pathParts.join('/');
    if (BASE_URL !== '' && !BASE_URL.endsWith('/')) { BASE_URL += '/'; }
}

const VIVINO_SEARCH_URL = 'https://www.vivino.com/search/wines?q=';
const DEFAULT_COST_TIERS = { t1: 10, t2r: 20, t3r: 35, t4r: 50 };

// Emoji map for consistency with backend
const WINE_TYPE_EMOJIS = {
    "Red": "🍷",
    "White": "🥂",
    "Rosé": "🌸",
    "Sparkling": "🍾",
    "Dessert": "🍰",
    "Fortified": "🍰",
};

let masterInventoryList = [];
let currentSortBy = 'name';
let currentSortDirection = 'asc';
let currentFilter = 'on_hand';
let currentTypeFilter = 'all'; // State for type filter
let appSettings = {};
let initialCostTierValues = {};
let openModalElement = null;
let lastFocusedElement = null;
let initialEntryFormData = {};

/**
 * A reusable wrapper for fetch API calls that handles errors,
 * shows messages, and manages button loading states.
 */
async function apiCall(endpoint, options = {}, messageElementId, button) {
    const originalButtonText = button ? button.textContent : '';
    if (button) {
        button.disabled = true;
        button.textContent = 'Processing...';
    }
    try {
        const response = await fetch(`${BASE_URL}${endpoint}`, {
            ...options,
            headers: { 'Content-Type': 'application/json', ...options.headers },
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'An unknown error occurred');
        if (messageElementId) showMessage(messageElementId, result.message || 'Success!', 'info', true);
        return result;
    } catch (error) {
        if (messageElementId) showMessage(messageElementId, `Error: ${error.message}`, 'error', true);
        throw error; // Re-throw for further handling if needed
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = originalButtonText;
        }
    }
}

/**
 * Fetches HTML content from a URL and injects it into a specified element.
 * @param {string} url - The URL of the HTML file to load.
 * @param {HTMLElement} element - The element to inject the HTML into.
 * @param {boolean} [append=false] - If true, appends the HTML instead of replacing the content.
 */
async function loadHTML(url, element, append = false) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to load HTML from ${url}: ${response.statusText}`);
        }
        const text = await response.text();
        if (append) {
            element.insertAdjacentHTML('beforeend', text);
        } else {
            element.innerHTML = text;
        }
    } catch (error) {
        console.error(error);
        element.innerHTML = `<p class="text-red-500 text-center">Error loading component.</p>`;
    }
}


function showMessage(elementId, text, type = 'info', isModal = false) {
    const messageEl = document.getElementById(elementId);
    if (!messageEl) return;
    messageEl.textContent = text;
    messageEl.className = 'mt-4 text-center font-medium'; // Reset classes
    if (type === 'error') messageEl.classList.add('text-red-600');
    else messageEl.classList.add('text-green-600');

    if (!isModal) {
        setTimeout(() => messageEl.classList.add('hidden'), 3000);
    }
}

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

function sortInventory(inventory, sortBy, sortDirection) {
    return [...inventory].sort((a, b) => {
        let comparison = 0;
        const getValue = (item, prop) => {
            let value = item[prop];
            if (value == null) return prop.match(/vintage|rating|quantity|score/) ? (sortDirection === 'asc' ? Infinity : -Infinity) : '';
            return typeof value === 'string' ? value.toLowerCase() : value;
        };
        const valA = getValue(a, sortBy);
        const valB = getValue(b, sortBy);

        if (valA < valB) comparison = -1;
        if (valA > valB) comparison = 1;

        if (comparison === 0 && sortBy !== 'name') {
            const nameA = getValue(a, 'name');
            const nameB = getValue(b, 'name');
            if (nameA < nameB) return -1;
            if (nameA > nameB) return 1;
        }
        return sortDirection === 'desc' ? -comparison : comparison;
    });
}

function updateFilterVisibility() {
    if (!masterInventoryList) return;

    const availableTypes = new Set(masterInventoryList.map(wine => wine.wine_type).filter(Boolean));
    const redFilter = document.querySelector('[data-type-filter="Red"]');
    if (redFilter) redFilter.classList.toggle('hidden', !availableTypes.has('Red'));
    const whiteFilter = document.querySelector('[data-type-filter="White"]');
    if (whiteFilter) whiteFilter.classList.toggle('hidden', !availableTypes.has('White'));
    const roseFilter = document.querySelector('[data-type-filter="Rosé"]');
    if (roseFilter) roseFilter.classList.toggle('hidden', !availableTypes.has('Rosé'));
    const sparklingFilter = document.querySelector('[data-type-filter="Sparkling"]');
    if (sparklingFilter) sparklingFilter.classList.toggle('hidden', !availableTypes.has('Sparkling'));

    const hasSpecialty = availableTypes.has('Dessert') || availableTypes.has('Fortified');
    const specialtyFilter = document.querySelector('[data-type-filter="specialty"]');
    if (specialtyFilter) specialtyFilter.classList.toggle('hidden', !hasSpecialty);

    const activeFilterButton = document.querySelector('#type-filters .type-filter-button.active');
    if (activeFilterButton && activeFilterButton.classList.contains('hidden')) {
        document.querySelector('[data-type-filter="all"]').click();
    }
}

function updateDisplayedInventory() {
    let inventoryToDisplay = [...masterInventoryList];

    if (currentTypeFilter !== 'all') {
        if (currentTypeFilter === 'specialty') {
            inventoryToDisplay = inventoryToDisplay.filter(wine =>
                ['Dessert', 'Fortified'].includes(wine.wine_type)
            );
        } else {
            inventoryToDisplay = inventoryToDisplay.filter(wine => wine.wine_type === currentTypeFilter);
        }
    }

    const sortedData = sortInventory(inventoryToDisplay, currentSortBy, currentSortDirection);
    displayInventory(sortedData);
}

async function fetchInventory() {
    const inventoryTableBody = document.getElementById('inventoryTableBody');
    if (inventoryTableBody) {
        inventoryTableBody.innerHTML = '<tr><td colspan="3" class="py-4 text-center text-gray-500">Loading inventory...</td></tr>';
    }
    try {
        const response = await fetch(`${BASE_URL}inventory?filter=${currentFilter}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        masterInventoryList = await response.json();
        updateFilterVisibility();
        updateDisplayedInventory();
    } catch (error) {
        showMessage('inventoryMessage', `Failed to load inventory: ${error.message}`, 'error');
        if (inventoryTableBody) {
            inventoryTableBody.innerHTML = '<tr><td colspan="3" class="py-4 text-center text-red-600">Error loading inventory.</td></tr>';
        }
    }
}

function escapeAttr(str) {
    if (!str) return '';
    return str.toString().replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function displayInventory(inventory) {
    const container = document.getElementById('inventoryTableBody');
    const summaryEl = document.getElementById('inventory-summary');
    if (!container || !summaryEl) return;

    container.innerHTML = '';

    if (inventory.length > 0) {
        const totalBottles = inventory.reduce((sum, wine) => sum + wine.quantity, 0);
        const uniqueWines = inventory.length;
        summaryEl.textContent = `${uniqueWines} unique ${uniqueWines === 1 ? 'wine' : 'wines'} / ${totalBottles} total ${totalBottles === 1 ? 'bottle' : 'bottles'}`;
        summaryEl.classList.remove('hidden');
    } else {
        summaryEl.classList.add('hidden');
    }

    if (inventory.length === 0) {
        let message = `No wines found for filter: ${currentFilter.replace('_', ' ')}`;
        if (currentTypeFilter !== 'all') {
            const filterName = document.querySelector(`[data-type-filter="${currentTypeFilter}"]`)?.title || currentTypeFilter;
            message += ` and type: ${filterName}`;
        }
        container.innerHTML = `<tr><td colspan="3" class="py-4 text-center text-gray-500">${message}</td></tr>`;
        return;
    }

    inventory.forEach(item => {
        const row = document.createElement('tr');
        row.className = 'border-b border-gray-200 flex flex-col sm:table-row';

        const imageCell = document.createElement('td');
        imageCell.className = 'py-4 sm:p-4 flex justify-center sm:block';
        const imageContainer = document.createElement('div');
        imageContainer.className = 'wine-image-container rounded-md overflow-hidden';
        imageContainer.onclick = () => openModal('notesModal', { wine: item });
        imageContainer.title = item.tasting_notes ? item.tasting_notes : 'Click to add tasting notes';

        const focalPoint = item.image_focal_point || '50%';
        const imageStyle = `object-position: 50% ${focalPoint};`;
        imageContainer.innerHTML = item.image_url
            ? `<img src="${item.image_url}" class="h-24 w-24 object-cover" alt="${escapeAttr(item.name)}" style="${imageStyle}">`
            : '<div class="text-gray-400 text-center w-24 h-24 flex items-center justify-center bg-gray-100">No Image</div>';

        imageCell.appendChild(imageContainer);

        const detailsCell = document.createElement('td');
        detailsCell.className = 'py-4 sm:p-4 text-sm text-gray-900 wine-details-cell w-full sm:w-auto text-center sm:text-left';

        let detailsHtml = `<h4>${item.name || 'N/A'} ${item.vintage ? `(${item.vintage})` : '(NV)'}</h4>`;

        if (item.varietal && item.varietal !== "Unknown Varietal") {
            detailsHtml += `<p><strong>Varietal:</strong> ${item.varietal}</p>`;
        }

        const location = [item.region, item.country].filter(loc => loc && !loc.startsWith('Unknown')).join(', ');
        if (location) {
            detailsHtml += `<p><strong>Origin:</strong> ${location}</p>`;
        }

        const wineTypeColors = {
            'Red': { color: 'var(--wine-red-text)', backgroundColor: 'var(--wine-red-bg)', },
            'White': { color: '#F8D987', backgroundColor: 'var(--wine-tag-bg)' },
            'Rosé': { color: '#FFC0CB', backgroundColor: 'var(--wine-tag-bg)' },
            'Sparkling': { color: '#E0E0E0', backgroundColor: 'var(--wine-tag-bg)' },
            'Dessert': { color: '#D4AF37' },
            'Fortified': { color: '#8B4513' }
        };

        const typeAndAlcoholParts = [];

        if (item.wine_type) {
            const style = wineTypeColors[item.wine_type];
            const emoji = WINE_TYPE_EMOJIS[item.wine_type] || '🍇';
            let styleString = '';
            if (style) {
                const padding = style.backgroundColor ? 'padding: 2px 8px;' : '';
                const borderRadius = style.backgroundColor ? 'border-radius: 9999px;' : '';
                styleString = `style="font-weight: 700; color:${style.color}; ${style.backgroundColor ? `background-color:${style.backgroundColor};` : ''} ${padding} ${borderRadius}"`;
            }
            typeAndAlcoholParts.push(`<strong>Type:</strong> <span class="mr-1">${emoji}</span><span ${styleString}>${item.wine_type}</span>`);
        }

        if (item.alcohol_percent) {
            typeAndAlcoholParts.push(`<strong>ABV:</strong> ${item.alcohol_percent.toFixed(1)}%`);
        }

        if (typeAndAlcoholParts.length > 0) {
            detailsHtml += `<p>${typeAndAlcoholParts.join('&nbsp; | &nbsp;')}</p>`;
        }

        let display_rating = item.personal_rating ?? item.vivino_rating;
        if (item.personal_rating != null && item.vivino_rating != null) {
            display_rating = (item.personal_rating + item.vivino_rating) / 2;
        }
        if (display_rating != null) {
            detailsHtml += `<p><strong>Quality:</strong> ⭐ ${display_rating.toFixed(1)}</p>`;
        }

        const costAndB4bParts = [];
        if (item.cost_tier) {
            costAndB4bParts.push(`<strong>Cost:</strong> ${'$'.repeat(item.cost_tier)}`);
        }
        if (item.b4b_score != null) {
            const b4bValue = Math.round(item.b4b_score);
            const formatted = (b4bValue > 0 ? `+${b4bValue}` : b4bValue);
            const colorClass = b4bValue > 0 ? "text-green-600" : b4bValue < 0 ? "text-red-600" : "";
            costAndB4bParts.push(`<strong>B4B:</strong> 🎯 <span class="${colorClass} font-bold">${formatted}</span>`);
        }
        if (costAndB4bParts.length > 0) {
            detailsHtml += `<p>${costAndB4bParts.join('&nbsp; | &nbsp;')}</p>`;
        }

        detailsCell.innerHTML = detailsHtml;

        const actionsCell = document.createElement('td');
        actionsCell.className = 'py-4 sm:p-4 flex flex-row justify-center items-center gap-2 w-full sm:w-auto';

        const consumeBtn = document.createElement('button');
        consumeBtn.innerHTML = '<img src="res/consumebuticon.png" alt="Consume 1 Bottle" class="w-8 h-8">';
        consumeBtn.title = 'Consume 1 Bottle';
        consumeBtn.className = 'icon-button';
        consumeBtn.onclick = () => openModal('tasteModal', { wine: item });

        const qtyInput = document.createElement('input');
        qtyInput.type = 'number';
        qtyInput.value = item.quantity;
        qtyInput.min = 0;
        qtyInput.className = 'w-16 text-center border border-gray-300 rounded-md px-2 py-1';
        qtyInput.title = 'Edit Quantity';
        qtyInput.oninput = () => {
            qtyInput.value = qtyInput.value.replace(/[^0-9]/g, '');
            if (parseInt(qtyInput.value, 10) < 0) qtyInput.value = 0;
        };
        qtyInput.onblur = () => setWineQuantity(item.vivino_url, qtyInput.value);
        qtyInput.onkeydown = (e) => { if (e.key === 'Enter') qtyInput.blur(); };

        const editBtn = document.createElement('button');
        editBtn.innerHTML = '✏️';
        editBtn.title = 'Edit Wine Details';
        editBtn.className = 'text-yellow-600 hover:text-yellow-900 text-xl icon-button';
        editBtn.onclick = () => openModal('entryModal', { mode: 'edit', wine: item });

        const deleteBtn = document.createElement('button');
        deleteBtn.innerHTML = '🗑️';
        deleteBtn.title = 'Delete Wine from Inventory';
        deleteBtn.className = 'text-red-600 hover:text-red-900 text-xl icon-button';
        deleteBtn.onclick = () => deleteWine(item.vivino_url);

        actionsCell.append(consumeBtn, qtyInput, editBtn, deleteBtn);
        row.append(imageCell, detailsCell, actionsCell);
        container.appendChild(row);
    });
}

async function setWineQuantity(vivinoUrl, newQuantity) {
    const quantity = parseInt(newQuantity, 10);
    if (isNaN(quantity) || quantity < 0) {
        showMessage('inventoryMessage', 'Quantity must be a non-negative number.', 'error');
        fetchInventory(); return;
    }
    try {
        await apiCall('inventory/wine/set_quantity', {
            method: 'POST',
            body: JSON.stringify({ vivino_url: vivinoUrl, quantity: quantity })
        }, 'inventoryMessage');
        fetchInventory();
    } catch (error) { /* Error already shown by apiCall */ }
}

async function deleteWine(vivinoUrl) {
    if (!confirm('Delete this wine from your inventory? This cannot be undone.')) return;
    try {
        await apiCall('inventory/wine', {
            method: 'DELETE',
            body: JSON.stringify({ vivino_url: vivinoUrl })
        }, 'inventoryMessage');
        fetchInventory();
    } catch (error) { /* Error already shown by apiCall */ }
}

function openModal(modalId, options = {}) {
    const modalEl = document.getElementById(modalId);
    if (!modalEl || (openModalElement && openModalElement.id === modalId)) return;
    lastFocusedElement = document.activeElement;

    switch (modalId) {
        case 'entryModal': prepareEntryModal(options.mode, options.wine); break;
        case 'tasteModal': prepareTasteModal(options.wine); break;
        case 'notesModal': prepareNotesModal(options.wine); break;
        case 'settingsModal': prepareSettingsModal(); break;
        case 'helpModal': prepareHelpModal(options.fromSettings); break;
    }

    modalEl.classList.remove('hidden');
    openModalElement = modalEl;

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

function closeModal() {
    if (!openModalElement) return;
    const modalToClose = openModalElement;
    openModalElement = null;
    const vintageInput = document.getElementById('manualVintageInput');
    if (vintageInput) {
        vintageInput.value = '';
    }
    modalToClose.classList.add('hidden');

    if (modalToClose.id === 'helpModal' && window.fromSettings) {
        window.fromSettings = false;
        openModal('settingsModal');
    } else if (lastFocusedElement) {
        lastFocusedElement.focus();
        lastFocusedElement = null;
    }
}

document.addEventListener('keydown', (e) => {
    if (!openModalElement) return;
    if (e.key === 'Escape') {
        if (openModalElement.id === 'nvPromptModal' && window.nvPromptResolver) {
            window.nvPromptResolver.reject('cancelled');
        } else {
            closeModal();
        }
    }
    if (e.key === 'Tab') {
        const focusableElements = Array.from(openModalElement.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')).filter(el => !el.disabled);
        if (focusableElements.length === 0) { e.preventDefault(); return; }
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];
        const currentIndex = focusableElements.indexOf(document.activeElement);

        if (e.shiftKey && document.activeElement === firstElement) {
            lastElement.focus();
            e.preventDefault();
        } else if (!e.shiftKey && document.activeElement === lastElement) {
            firstElement.focus();
            e.preventDefault();
        }
    }
});

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

    vintageInput.disabled = false;
    vintageInput.required = true;
    nvCheckbox.checked = false;

    if (mode === 'edit') {
        title.textContent = 'Edit Wine';
        submitBtn.textContent = 'Save'; // Relabeled
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
        const rating = wine.personal_rating || 0;
        document.getElementById('manualTasteRatingInput').value = rating;
        updateStarVisuals(document.getElementById('editTasteRatingSelector'), rating, 'rated');
        updateFeedbackText(document.getElementById('editTasteRatingFeedback'), rating);

        initialEntryFormData = getEntryFormData();
        saveAsNewWineBtn.disabled = true;
        saveAsNewWineBtn.title = 'Change a field to enable saving as a new wine';

    } else { // 'add' mode
        title.textContent = 'Add Wine Manually';
        submitBtn.textContent = 'Add Wine';
        saveAsNewWineBtn.classList.add('hidden');
        initialEntryFormData = {}; // Clear initial data

        document.getElementById('entryVivinoUrl').value = '';
        document.getElementById('manualImageUrlInput').value = '';
        document.getElementById('manualQuantityInput').value = 1;
        updateCostTierSelector(null);
        updateStarVisuals(document.getElementById('editTasteRatingSelector'), 0, 'rated');
        updateFeedbackText(document.getElementById('editTasteRatingFeedback'), 0);
    }
}

function prepareTasteModal(wine) {
    const vivinoUrl = document.getElementById('tasteVivinoUrl');
    const wineName = document.getElementById('tasteModalWineName');
    if (vivinoUrl) vivinoUrl.value = wine.vivino_url;
    if (wineName) wineName.textContent = `${wine.name} (${wine.vintage || 'NV'})`;
    resetTasteStars();
}

async function fetchAndDisplayConsumptionHistory(wine) {
    const container = document.getElementById('consumptionLogContainer');
    if (!container) return;
    container.innerHTML = '<p>Loading history...</p>';
    try {
        const response = await fetch(`${BASE_URL}api/wine/history?vivino_url=${encodeURIComponent(wine.vivino_url)}`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Could not fetch history.');
        }
        const history = await response.json();

        if (history.length === 0) {
            container.innerHTML = '<p>No consumption history recorded.</p>';
            return;
        }

        const historyHtml = history.map(record => {
            const date = new Date(record.consumed_at).toLocaleDateString(undefined, {
                year: 'numeric', month: 'short', day: 'numeric'
            });
            const rating = record.personal_rating ? `(Rated: ${record.personal_rating.toFixed(1)} ★)` : '(Not rated)';
            return `<div class="flex justify-between items-center py-1 border-b border-gray-200">
                                <span>Consumed on ${date}</span>
                                <span class="text-gray-500">${rating}</span>
                            </div>`;
        }).join('');

        container.innerHTML = historyHtml;

    } catch (error) {
        console.error('Failed to fetch consumption history:', error);
        container.innerHTML = `<p class="text-red-600">Error loading history: ${error.message}</p>`;
    }
}

function prepareNotesModal(wine) {
    const imageUrlInput = document.getElementById('imageUrlInput');
    const toggleBtn = document.getElementById('toggleImageUrlLock');
    const focalPointEditor = document.getElementById('focalPointEditor');
    const draggableImage = document.getElementById('draggableImage');

    document.getElementById('notesVivinoUrl').value = wine.vivino_url;
    document.getElementById('notesModalWineName').textContent = `${wine.name} (${wine.vintage || 'NV'})`;
    document.getElementById('tastingNotesInput').value = wine.tasting_notes || '';
    document.getElementById('notesMessage').classList.add('hidden');

    const imageUrl = wine.image_url || '';
    imageUrlInput.value = imageUrl;

    draggableImage.src = imageUrl;
    const focalPoint = wine.image_focal_point || '50%';
    draggableImage.style.objectPosition = `50% ${focalPoint}`;

    imageUrlInput.setAttribute('readonly', true);
    toggleBtn.textContent = '🔒';
    focalPointEditor.classList.remove('is-unlocked');

    fetchAndDisplayConsumptionHistory(wine);
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

function prepareHelpModal(fromSettings = false) {
    window.fromSettings = fromSettings;
}

function openHelpFromSettings() {
    closeModal();
    openModal('helpModal', { fromSettings: true });
}

function setupVintageControls() {
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

function setupStarRating(selectorId, inputId, feedbackId) {
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


function updateStarVisuals(selectorEl, rating, stateClass) {
    if (!selectorEl) return;
    selectorEl.querySelectorAll('span').forEach((star, index) => {
        const starValue = index + 1;
        star.className = '';
        if (rating >= starValue) star.classList.add(`${stateClass}`);
        else if (rating > index && rating < starValue) star.classList.add(`${stateClass}-half`);
    });
}

function updateFeedbackText(feedbackEl, rating) {
    if (feedbackEl) feedbackEl.textContent = rating > 0 ? `${rating} star${rating !== 1 ? 's' : ''}` : '';
}

function resetTasteStars() {
    const inputEl = document.getElementById('tasteRatingInput');
    const selectorEl = document.getElementById('tasteRatingSelector');
    const feedbackEl = document.getElementById('tasteRatingFeedback');
    if (inputEl) inputEl.value = '';
    updateStarVisuals(selectorEl, 0, 'rated');
    updateFeedbackText(feedbackEl, 0);
}

function setupCostTierSelector(selectorId, inputId) {
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

function updateCostTierSelector(selectedValue) {
    const selector = document.getElementById('costTierSelector');
    const input = document.getElementById('manualCostTierInput');
    if (selector && input) {
        updateCostTierDisplay(selector, input, selectedValue);
    }
}

function updateMainCostTierSelector(selectedValue) {
    const selector = document.getElementById('mainCostTierSelector');
    const input = document.getElementById('mainCostTierInput');
    if (selector && input) {
        updateCostTierDisplay(selector, input, selectedValue);
    }
}

function updateTiers() {
    const t1Input = document.getElementById('tier1');
    const t2RightInput = document.getElementById('tier2Right');
    const t3RightInput = document.getElementById('tier3Right');
    const t4RightInput = document.getElementById('tier4Right');
    if (!t1Input || !t2RightInput || !t3RightInput || !t4RightInput) return;

    const t1 = parseFloat(t1Input.value) || 0;
    const t2Right = parseFloat(t2RightInput.value) || 0;
    const t3Right = parseFloat(t3RightInput.value) || 0;
    const t4Right = parseFloat(t4RightInput.value) || 0;

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
        appSettings = { ...appSettings, ...payload };
        updateCostTierTooltips();
    } catch (error) { /* Error already shown */ }
}

function populateCostTierFieldsFromSettings() {
    const parseValue = (label, regex) => {
        const match = label ? label.match(regex) : null;
        return match ? parseFloat(match[1]) : null;
    };
    const tier1 = document.getElementById('tier1');
    if (tier1) tier1.value = parseValue(appSettings.cost_tier_1_label, /Under \$([\d.]+)/) ?? DEFAULT_COST_TIERS.t1;
    const tier2Right = document.getElementById('tier2Right');
    if (tier2Right) tier2Right.value = parseValue(appSettings.cost_tier_2_label, / - \$([\d.]+)/) ?? DEFAULT_COST_TIERS.t2r;
    const tier3Right = document.getElementById('tier3Right');
    if (tier3Right) tier3Right.value = parseValue(appSettings.cost_tier_3_label, / - \$([\d.]+)/) ?? DEFAULT_COST_TIERS.t3r;
    const tier4Right = document.getElementById('tier4Right');
    if (tier4Right) tier4Right.value = parseValue(appSettings.cost_tier_4_label, / - \$([\d.]+)/) ?? DEFAULT_COST_TIERS.t4r;
    updateTiers();
}

async function fetchSettings() {
    try {
        const response = await fetch(`${BASE_URL}api/settings`);
        if (!response.ok) throw new Error('Failed to fetch settings');
        appSettings = await response.json();
        updateCostTierTooltips();
    } catch (error) {
        console.error('Error fetching settings:', error);
    }
}

function updateCostTierTooltips() {
    document.querySelectorAll('.cost-tier-selector').forEach(selector => {
        selector.querySelectorAll('span').forEach(span => {
            const tierValue = span.dataset.value;
            span.title = appSettings[`cost_tier_${tierValue}_label`] || `Tier ${tierValue}`;
        });
    });
}

function updateSortIcons() {
    const ascIcon = document.getElementById('sortAscIcon');
    const descIcon = document.getElementById('sortDescIcon');
    if (ascIcon) ascIcon.classList.toggle('hidden', currentSortDirection === 'desc');
    if (descIcon) descIcon.classList.toggle('hidden', currentSortDirection === 'asc');
}

function promptForVintage() {
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

async function saveFocalPoint(vivinoUrl, focalPoint) {
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

function getEntryFormData() {
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


function checkFormChanges() {
    const saveAsNewWineBtn = document.getElementById('entrySaveAsNewWineBtn');
    if (!saveAsNewWineBtn || saveAsNewWineBtn.classList.contains('hidden')) return;
    const currentFormData = getEntryFormData();
    const hasChanged = JSON.stringify(currentFormData) !== JSON.stringify(initialEntryFormData);
    saveAsNewWineBtn.disabled = !hasChanged;
    saveAsNewWineBtn.title = hasChanged ? 'Save the current details as a new wine entry' : 'Change a field to enable saving as a new wine';
}

function setupEventListeners() {
    document.getElementById('settingsButton').addEventListener('click', () => openModal('settingsModal'));
    document.getElementById('themeToggle').addEventListener('click', () => {
        document.body.classList.toggle('dark-theme');
        const isDark = document.body.classList.contains('dark-theme');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        document.getElementById('themeIcon').textContent = isDark ? '🌙' : '☀️';
    });

    document.body.addEventListener('click', (e) => {
        if (e.target.closest('#addWineHeader')) {
            const addWineSection = document.getElementById('addWineSection');
            if (addWineSection) {
                const isExpanded = addWineSection.classList.toggle('is-expanded');
                localStorage.setItem('addWinePanelState', isExpanded ? 'expanded' : 'collapsed');
            }
        }
        if (e.target.id === 'openEntryModalBtn') {
            openModal('entryModal');
            const manualVintageInput = document.getElementById('manualVintageInput');
            const currentYear = new Date().getFullYear();
            if (manualVintageInput) manualVintageInput.value = currentYear - 3;
        }
        if (e.target.closest('#inventory-filters') && e.target.matches('.filter-button')) {
            currentFilter = e.target.dataset.filter;
            document.querySelectorAll('#inventory-filters .filter-button').forEach(btn => btn.classList.remove('active'));
            e.target.classList.add('active');
            const heading = document.getElementById('inventory-heading');
            if (heading) {
                const headingText = `Wine ${currentFilter.replace('_', ' ')}`;
                heading.textContent = headingText.charAt(0).toUpperCase() + headingText.slice(1);
            }
            fetchInventory();
        }
        if (e.target.closest('#type-filters') && e.target.closest('.type-filter-button')) {
            const button = e.target.closest('.type-filter-button');
            currentTypeFilter = button.dataset.typeFilter;
            document.querySelectorAll('#type-filters .type-filter-button').forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            updateDisplayedInventory();
        }
        if (e.target.closest('#sortDirectionToggle')) {
            currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
            updateSortIcons();
            updateDisplayedInventory();
        }
        if (e.target.closest('#refreshInventoryBtn')) {
            fetchInventory();
        }
        if (e.target.closest('.cost-tier-selector') || e.target.closest('.taste-rating-selector')) {
            setTimeout(checkFormChanges, 0);
        }
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
    });

    document.body.addEventListener('change', (e) => {
        if (e.target.id === 'sortSelect') {
            currentSortBy = e.target.value;
            updateDisplayedInventory();
        }
        if (e.target.id === 'nvCheckbox') {
            checkFormChanges();
        }
    });

    document.body.addEventListener('input', (e) => {
        if (e.target.closest('#entryForm')) {
            checkFormChanges();
        }
    });

    document.body.addEventListener('submit', async (e) => {
        e.preventDefault();
        switch (e.target.id) {
            case 'vivinoSearchForm': {
                const queryInput = document.getElementById('vivinoSearchInput');
                if (queryInput) {
                    window.open(`${VIVINO_SEARCH_URL}${encodeURIComponent(queryInput.value)}`, '_blank');
                    const button = e.target.querySelector('button[type="submit"]');
                    const originalText = button.textContent;
                    button.textContent = 'Opening...';
                    setTimeout(() => { button.textContent = originalText; }, 1500);
                    e.target.reset();
                }
                break;
            }
            case 'scanWineForm': {
                const vivinoUrlInput = document.getElementById('vivinoUrlInput');
                let vivinoUrl = vivinoUrlInput.value;
                const isValidVivinoWineUrl = (url) => {
                    if (!url) return false;
                    try {
                        const parsedUrl = new URL(url);
                        const isHostValid = parsedUrl.hostname === 'www.vivino.com' || parsedUrl.hostname === 'vivino.com';
                        const isPathValid = /\/w\/\d+/.test(parsedUrl.pathname);
                        return isHostValid && isPathValid;
                    } catch (e) {
                        return false;
                    }
                };
                if (!isValidVivinoWineUrl(vivinoUrl)) {
                    showMessage('scanMessage', "Invalid URL. Please use a specific Vivino wine page (e.g., https://www.vivino.com/...).", 'error');
                    vivinoUrlInput.value = '';
                    return;
                }
                if (!/year=\d{4}/.test(vivinoUrl)) {
                    try {
                        const result = await promptForVintage();
                        if (result.vintage) {
                            const url = new URL(vivinoUrl);
                            url.searchParams.set('year', result.vintage);
                            vivinoUrl = url.toString();
                            vivinoUrlInput.value = vivinoUrl;
                        }
                    } catch (error) {
                        if (error !== 'cancelled') console.error(error);
                        showMessage('scanMessage', 'Action cancelled.', 'info');
                        vivinoUrlInput.focus();
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
                    e.target.reset();
                    updateMainCostTierSelector(null);
                    fetchInventory();
                } catch (error) { }
                break;
            }
            case 'entryForm': {
                const isEditMode = !!document.getElementById('entryVivinoUrl').value;
                const payload = getEntryFormData();
                if (isEditMode) payload.vivino_url = document.getElementById('entryVivinoUrl').value;
                try {
                    await apiCall(isEditMode ? 'edit-wine' : 'add-manual-wine', { method: 'POST', body: JSON.stringify(payload) }, 'entryMessage', e.target.querySelector('button[type="submit"]'));
                    fetchInventory();
                    setTimeout(closeModal, 1500);
                } catch (error) { }
                break;
            }
            case 'tasteForm': {
                const payload = {
                    vivino_url: document.getElementById('tasteVivinoUrl').value,
                    personal_rating: parseFloat(document.getElementById('tasteRatingInput').value) || null
                };
                try {
                    await apiCall('inventory/wine/consume', { method: 'POST', body: JSON.stringify(payload) }, 'inventoryMessage', e.target.querySelector('button[type="submit"]'));
                    closeModal();
                    fetchInventory();
                } catch (error) { }
                break;
            }
            case 'notesForm': {
                const payload = {
                    vivino_url: document.getElementById('notesVivinoUrl').value,
                    tasting_notes: document.getElementById('tastingNotesInput').value,
                    image_url: document.getElementById('imageUrlInput').value
                };
                try {
                    await apiCall('api/wine/notes', { method: 'POST', body: JSON.stringify(payload) }, 'notesMessage', e.target.querySelector('button[type="submit"]'));
                    fetchInventory();
                    setTimeout(closeModal, 1500);
                } catch (error) { }
                break;
            }
        }
    });

    let isDragging = false;
    let startY = 0;
    let startFocalPercent = 50;
    const getPointerY = (e) => e.touches ? e.touches[0].clientY : e.clientY;

    const startDrag = (e) => {
        if (e.target.id !== 'draggableImage') return;
        const focalPointEditor = document.getElementById('focalPointEditor');
        if (!focalPointEditor || !focalPointEditor.classList.contains('is-unlocked')) return;
        e.preventDefault();
        isDragging = true;
        focalPointEditor.classList.add('is-dragging');
        startY = getPointerY(e);
        const currentPosition = e.target.style.objectPosition || '50% 50%';
        startFocalPercent = parseFloat(currentPosition.split(' ')[1]);
    };

    const onDrag = (e) => {
        if (!isDragging) return;
        e.preventDefault();
        const focalPointEditor = document.getElementById('focalPointEditor');
        const draggableImage = document.getElementById('draggableImage');
        if (!focalPointEditor || !draggableImage) return;

        const parentHeight = focalPointEditor.clientHeight;
        const renderedImageHeight = (draggableImage.naturalHeight / draggableImage.naturalWidth) * focalPointEditor.clientWidth;
        if (renderedImageHeight <= parentHeight || !draggableImage.naturalHeight) return;

        const currentY = getPointerY(e);
        const deltaY = currentY - startY;
        const travelRange = renderedImageHeight - parentHeight;
        const deltaPercent = (deltaY / travelRange) * 100;
        const newFocalPercent = startFocalPercent - deltaPercent;
        const clampedPercent = Math.max(0, Math.min(100, newFocalPercent));
        draggableImage.style.objectPosition = `50% ${clampedPercent.toFixed(2)}%`;
    };

    const endDrag = () => {
        if (!isDragging) return;
        isDragging = false;
        const focalPointEditor = document.getElementById('focalPointEditor');
        const vivinoUrl = document.getElementById('notesVivinoUrl');
        const focalPoint = document.getElementById('draggableImage');

        if (focalPointEditor) focalPointEditor.classList.remove('is-dragging');

        if (vivinoUrl && focalPoint && vivinoUrl.value && focalPoint.style.objectPosition) {
            saveFocalPoint(vivinoUrl.value, focalPoint.style.objectPosition.split(' ')[1]);
        }
    };

    document.body.addEventListener('mousedown', startDrag);
    document.body.addEventListener('touchstart', startDrag, { passive: false });
    window.addEventListener('mousemove', onDrag, { passive: false });
    window.addEventListener('touchmove', onDrag, { passive: false });
    window.addEventListener('mouseup', endDrag);
    window.addEventListener('touchend', endDrag);
}


document.addEventListener('DOMContentLoaded', async () => {
    // Load all HTML components into their respective containers
    await Promise.all([
        loadHTML('components/add-wine.html', document.getElementById('addWineSection')),
        loadHTML('components/inventory.html', document.getElementById('inventorySection')),
        loadHTML('components/manual-entry-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/notes-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/settings-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/help-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/taste-modal.html', document.getElementById('modalContainer'), true),
        loadHTML('components/nv-prompt-modal.html', document.getElementById('modalContainer'), true)
    ]);

    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') document.body.classList.add('dark-theme');
    document.getElementById('themeIcon').textContent = savedTheme === 'dark' ? '🌙' : '☀️';

    setupEventListeners();

    await fetchSettings();
    fetchInventory();

    if (localStorage.getItem('addWinePanelState') === 'expanded') {
        const addWineSection = document.getElementById('addWineSection');
        if (addWineSection) addWineSection.classList.add('is-expanded');
    }

    updateSortIcons();
    setupVintageControls();
    setupCostTierSelector('mainCostTierSelector', 'mainCostTierInput');
    setupCostTierSelector('costTierSelector', 'manualCostTierInput');
    setupStarRating('tasteRatingSelector', 'tasteRatingInput', 'tasteRatingFeedback');
    setupStarRating('editTasteRatingSelector', 'manualTasteRatingInput', 'editTasteRatingFeedback');


    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            console.log("Tab is visible, refreshing inventory.");
            fetchInventory();
        }
    });
});

