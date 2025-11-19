// js/inventory.js
// Handles all logic for the main wine inventory display.

import * as state from './state.js';
import { apiCall, showMessage, escapeAttr } from './utils.js';
import { openModal } from './modals.js';
import { BASE_URL, WINE_TYPE_EMOJIS } from './config.js';

export async function fetchInventory() {
    const inventoryTableBody = document.getElementById('inventoryTableBody');
    if (inventoryTableBody) {
        inventoryTableBody.innerHTML = '<tr><td colspan="3" class="py-4 text-center text-gray-500">Loading inventory...</td></tr>';
    }
    try {
        const response = await fetch(`${BASE_URL}inventory?filter=${state.currentFilter}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const inventoryList = await response.json();
        state.setMasterInventoryList(inventoryList);
        updateFilterVisibility();
        updateDisplayedInventory();
    } catch (error) {
        showMessage('inventoryMessage', `Failed to load inventory: ${error.message}`, 'error');
        if (inventoryTableBody) {
            inventoryTableBody.innerHTML = '<tr><td colspan="3" class="py-4 text-center text-red-600">Error loading inventory.</td></tr>';
        }
    }
}

export function updateDisplayedInventory() {
    let inventoryToDisplay = [...state.masterInventoryList];

    if (state.currentTypeFilter !== 'all') {
        if (state.currentTypeFilter === 'specialty') {
            inventoryToDisplay = inventoryToDisplay.filter(wine =>
                ['Dessert', 'Fortified'].includes(wine.wine_type)
            );
        } else {
            inventoryToDisplay = inventoryToDisplay.filter(wine => wine.wine_type === state.currentTypeFilter);
        }
    }

    const sortedData = sortInventory(inventoryToDisplay, state.currentSortBy, state.currentSortDirection);
    displayInventory(sortedData);
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
        let message = `No wines found for filter: ${state.currentFilter.replace('_', ' ')}`;
        if (state.currentTypeFilter !== 'all') {
            const filterName = document.querySelector(`[data-type-filter="${state.currentTypeFilter}"]`)?.title || state.currentTypeFilter;
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

        let focalPoint = item.image_focal_point || '50% 50%';
        // Handle backward compatibility for old format (which was just Y-percentage string)
        if (focalPoint && !focalPoint.includes(' ')) {
            focalPoint = `50% ${focalPoint}`;
        }
        const zoomLevel = item.image_zoom || 1;
        const tiltLevel = item.image_tilt || 0;
        
        // --- FIX 2: Included rotate() in the transform string ---
        // Combine all styles into a single string
        const imageStyle = `object-position: ${focalPoint}; transform: scale(${zoomLevel}) rotate(${tiltLevel}deg); transform-origin: ${focalPoint};`;

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
            const regionFull = item.region_full && item.region_full !== location ? item.region_full : null;
            detailsHtml += `<p><strong>Origin:</strong> <span${regionFull ? ` title="${escapeAttr(regionFull)}"` : ''}>${location}</span></p>`;
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

function updateFilterVisibility() {
    if (!state.masterInventoryList) return;

    const availableTypes = new Set(state.masterInventoryList.map(wine => wine.wine_type).filter(Boolean));
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