// js/utils.js
// Contains reusable utility functions.

/**
 * A reusable wrapper for fetch API calls that handles errors,
 * shows messages, and manages button loading states.
 */
import { BASE_URL } from './config.js';

export async function apiCall(endpoint, options = {}, messageElementId, button) {
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
        throw error;
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = originalButtonText;
        }
    }
}


export function showMessage(elementId, text, type = 'info', isModal = false) {
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

export function escapeAttr(str) {
    if (!str) return '';
    return str.toString().replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

export async function loadHTML(url, element, append = false) {
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