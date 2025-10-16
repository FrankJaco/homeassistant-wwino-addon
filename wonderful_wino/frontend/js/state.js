// js/state.js
// Manages the shared state of the application.

export let masterInventoryList = [];
export let currentSortBy = 'name';
export let currentSortDirection = 'asc';
export let currentFilter = 'on_hand';
export let currentTypeFilter = 'all';
export let appSettings = {};
export let openModalElement = null;
export let lastFocusedElement = null;
export let initialEntryFormData = {};
export let consumptionLogSortOrder = 'desc';
export let currentWineForLog = null;
export let panelCollapseTimer = null;

// Functions to safely update state from other modules
export function setMasterInventoryList(list) { masterInventoryList = list; }
export function setCurrentSortBy(value) { currentSortBy = value; }
export function setCurrentSortDirection(value) { currentSortDirection = value; }
export function setCurrentFilter(value) { currentFilter = value; }
export function setCurrentTypeFilter(value) { currentTypeFilter = value; }
export function setAppSettings(settings) { appSettings = settings; }
export function setOpenModalElement(el) { openModalElement = el; }
export function setLastFocusedElement(el) { lastFocusedElement = el; }
export function setInitialEntryFormData(data) { initialEntryFormData = data; }
export function setConsumptionLogSortOrder(order) { consumptionLogSortOrder = order; }
export function setCurrentWineForLog(wine) { currentWineForLog = wine; }
export function setPanelCollapseTimer(timer) { panelCollapseTimer = timer; }