/**
 * Script Launcher - Frontend Application
 */

// State
let scripts = [];
let selectedScriptId = null;
let ws = null;
let allLogs = [];  // Store all logs for filtering
let originalFormData = null;  // Track original form values for change detection

// DOM Elements
const tabScripts = document.getElementById('tab-scripts');
const tabLogs = document.getElementById('tab-logs');
const panelScripts = document.getElementById('panel-scripts');
const panelLogs = document.getElementById('panel-logs');
const scriptList = document.getElementById('script-list');
const scriptDetail = document.getElementById('script-detail');
const scriptPlaceholder = document.getElementById('script-placeholder');
const detailTitle = document.getElementById('detail-title');
const btnNewScript = document.getElementById('btn-new-script');
const logContainer = document.getElementById('log-container');
const logFilterScript = document.getElementById('log-filter-script');
const logFilterLevel = document.getElementById('log-filter-level');
const logFilterDate = document.getElementById('log-filter-date');
const logAutoscroll = document.getElementById('log-autoscroll');
const btnClearLogs = document.getElementById('btn-clear-logs');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initWebSocket();
    loadScripts();

    logFilterDate.value = new Date().toISOString().split('T')[0];

    btnNewScript.addEventListener('click', showNewScriptForm);
    btnClearLogs.addEventListener('click', clearLogs);

    // Filter change listeners
    logFilterScript.addEventListener('change', renderLogs);
    logFilterLevel.addEventListener('change', renderLogs);
    logFilterDate.addEventListener('change', loadHistoricalLogs);
});

// Tab Navigation
function initTabs() {
    tabScripts.addEventListener('click', () => switchTab('scripts'));
    tabLogs.addEventListener('click', () => switchTab('logs'));
}

function switchTab(tab) {
    const isScripts = tab === 'scripts';

    tabScripts.className = `tab-btn px-4 py-1.5 rounded-md text-sm font-medium ${isScripts ? 'bg-blue-600 text-white' : 'text-dark-300 hover:text-white'}`;
    tabLogs.className = `tab-btn px-4 py-1.5 rounded-md text-sm font-medium ${!isScripts ? 'bg-blue-600 text-white' : 'text-dark-300 hover:text-white'}`;

    panelScripts.classList.toggle('hidden', !isScripts);
    panelLogs.classList.toggle('hidden', isScripts);

    if (isScripts) {
        // Reload scripts and refresh selected script view when returning to scripts tab
        loadScripts().then(() => {
            if (selectedScriptId) {
                showScriptDetail(selectedScriptId);
            }
        });
    } else {
        // Load historical logs when switching to logs tab
        loadHistoricalLogs();
    }
}

// WebSocket
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/logs`);

    ws.onopen = () => {
        logContainer.innerHTML = '<p class="text-dark-500">Conectado. Esperando logs...</p>';
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        appendLog(data);
    };

    ws.onclose = () => setTimeout(initWebSocket, 3000);
    ws.onerror = () => {};
}

function detectLogLevel(message) {
    if (message.includes('[DEBUG]')) return 'DEBUG';
    if (message.includes('[WARNING]')) return 'WARNING';
    if (message.includes('[ERROR]')) return 'ERROR';
    if (message.includes('[INFO]')) return 'INFO';
    return 'STDOUT';
}

function appendLog(data) {
    // Store log with detected level
    data.detectedLevel = detectLogLevel(data.message);
    allLogs.unshift(data);  // Add to beginning (most recent first)

    // Limit stored logs to prevent memory issues
    if (allLogs.length > 1000) {
        allLogs = allLogs.slice(0, 500);  // Keep first 500 (most recent)
    }

    // Check if this log passes current filters
    const filterScript = logFilterScript.value;
    const filterLevel = logFilterLevel.value;

    if (filterScript && data.script_id != filterScript) return;
    if (filterLevel && data.detectedLevel !== filterLevel) return;

    // Render this single log entry at the top
    renderLogEntry(data, true);

    if (logAutoscroll.checked) {
        logContainer.scrollTop = 0;  // Scroll to top (most recent)
    }
}

function renderLogEntry(data, prepend = false) {
    const placeholder = logContainer.querySelector('.text-dark-500');
    if (placeholder) placeholder.remove();

    const levelClasses = {
        'DEBUG': 'log-debug',
        'WARNING': 'log-warning',
        'ERROR': 'log-error',
        'INFO': 'log-info',
        'STDOUT': 'log-stdout',
    };
    const logClass = levelClasses[data.detectedLevel] || 'log-stdout';

    const entry = document.createElement('div');
    entry.className = `py-0.5 ${logClass}`;
    const time = new Date(data.timestamp).toLocaleTimeString();
    entry.textContent = `${time}  ${data.script_name.padEnd(15)}  ${data.message}`;

    if (prepend) {
        logContainer.insertBefore(entry, logContainer.firstChild);
    } else {
        logContainer.appendChild(entry);
    }
}

function renderLogs() {
    const filterScript = logFilterScript.value;
    const filterLevel = logFilterLevel.value;

    // Clear container
    logContainer.innerHTML = '';

    // Filter and render (allLogs already in reverse chronological order)
    const filtered = allLogs.filter(log => {
        if (filterScript && log.script_id != filterScript) return false;
        if (filterLevel && log.detectedLevel !== filterLevel) return false;
        return true;
    });

    if (filtered.length === 0) {
        logContainer.innerHTML = '<p class="text-dark-500">No hay logs que coincidan con los filtros</p>';
        return;
    }

    filtered.forEach(log => renderLogEntry(log));

    if (logAutoscroll.checked) {
        logContainer.scrollTop = 0;  // Scroll to top (most recent)
    }
}

function clearLogs() {
    allLogs = [];
    logContainer.innerHTML = '<p class="text-dark-500">Logs limpiados</p>';
}

async function loadHistoricalLogs() {
    const selectedDate = logFilterDate.value;
    if (!selectedDate) return;

    try {
        const response = await fetch(`/api/logs?log_date=${selectedDate}`);
        if (!response.ok) throw new Error('Failed to load logs');

        const logs = await response.json();

        // Clear existing logs and load historical ones (reverse to show most recent first)
        allLogs = logs.map(log => ({
            ...log,
            detectedLevel: detectLogLevel(log.message),
        })).reverse();

        renderLogs();
    } catch (error) {
        logContainer.innerHTML = '<p class="text-red-400">Error al cargar logs</p>';
    }
}

// Scripts API
async function loadScripts() {
    try {
        const response = await fetch('/api/scripts');
        scripts = await response.json();
        renderScriptList();
        updateScriptFilter();
    } catch (error) {
        scriptList.innerHTML = '<p class="text-red-400 text-sm p-3">Error al cargar scripts</p>';
    }
}

function renderScriptList() {
    if (scripts.length === 0) {
        scriptList.innerHTML = '<p class="text-dark-500 text-sm p-3">No hay scripts. Crea uno nuevo.</p>';
        return;
    }

    scriptList.innerHTML = scripts.map(script => `
        <div class="p-3 rounded-lg cursor-pointer transition-colors hover:bg-dark-800 ${script.id === selectedScriptId ? 'bg-dark-800 border-l-2 border-blue-500' : ''}"
             onclick="selectScript(${script.id})">
            <div class="flex items-center gap-2">
                <span class="status-dot ${getStatusClass(script)}"></span>
                <span class="font-medium text-sm text-dark-100">${escapeHtml(script.name)}</span>
            </div>
            ${script.repeat_enabled ? `
                <p class="text-xs text-dark-400 mt-1 ml-4">Cada ${script.interval_value} ${translateUnit(script.interval_unit)}</p>
            ` : '<p class="text-xs text-dark-500 mt-1 ml-4">Sin repeticion</p>'}
        </div>
    `).join('');
}

function translateUnit(unit) {
    const units = { seconds: 'segundos', minutes: 'minutos', hours: 'horas', days: 'dias' };
    return units[unit] || unit;
}

function getStatusClass(script) {
    if (!script.is_active) return 'status-paused';
    return 'status-running';  // Active scripts show as running (green)
}

function selectScript(id) {
    selectedScriptId = id;
    renderScriptList();
    showScriptDetail(id);
}

function showScriptDetail(id) {
    const script = scripts.find(s => s.id === id);
    if (!script) return;

    // Store original values for change detection
    // When weekdays is null or empty, all days are selected (0-6)
    const parsedWeekdays = script.weekdays ? JSON.parse(script.weekdays) : [];
    const allDaysSelected = parsedWeekdays.length === 0 || parsedWeekdays.length === 7;

    originalFormData = {
        path: script.path || '',
        repeat_enabled: script.repeat_enabled || false,
        interval_value: script.interval_value || 1,
        interval_unit: script.interval_unit || 'seconds',
        weekdays: allDaysSelected ? [0, 1, 2, 3, 4, 5, 6] : parsedWeekdays.sort(),
        scheduled_start_enabled: script.scheduled_start_enabled || false,
        scheduled_start_datetime: script.scheduled_start_datetime?.slice(0, 16) || '',
    };

    detailTitle.textContent = `Editar: ${script.name}`;
    scriptPlaceholder.classList.add('hidden');
    scriptDetail.classList.remove('hidden');
    scriptDetail.innerHTML = renderScriptForm(script);
    attachFormHandlers();
}

function showNewScriptForm() {
    selectedScriptId = null;
    originalFormData = null;  // New script - no original data
    renderScriptList();
    detailTitle.textContent = 'Nuevo Script';
    scriptPlaceholder.classList.add('hidden');
    scriptDetail.classList.remove('hidden');
    scriptDetail.innerHTML = renderScriptForm(null);
    attachFormHandlers();
}

function renderScriptForm(script) {
    const isNew = !script;
    const isActive = script?.is_active || false;
    const hasScheduling = script?.scheduled_start_enabled || script?.repeat_enabled;
    const canActivate = !isActive && hasScheduling;
    const weekdays = script?.weekdays ? JSON.parse(script.weekdays) : [];
    const allDays = weekdays.length === 0;

    return `
        <form id="script-form" class="space-y-6">
            <!-- Datos basicos -->
            <fieldset class="space-y-4">
                <legend class="text-xs font-semibold text-dark-400 uppercase tracking-wide mb-3">Informacion del Script</legend>

                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs font-medium text-dark-300 mb-1.5">Nombre</label>
                        <input type="text" name="name" required
                               class="w-full bg-dark-800 border border-dark-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                               placeholder="mi_script"
                               value="${escapeHtml(script?.name || '')}">
                    </div>
                    <div>
                        <label class="block text-xs font-medium text-dark-300 mb-1.5">Ruta del archivo</label>
                        <input type="text" name="path" required
                               class="w-full bg-dark-800 border border-dark-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                               placeholder="/ruta/al/script.py"
                               value="${escapeHtml(script?.path || '')}">
                    </div>
                </div>

                <div>
                    <label class="block text-xs font-medium text-dark-300 mb-1.5">Descripcion (opcional)</label>
                    <textarea name="description" rows="2"
                              class="w-full bg-dark-800 border border-dark-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 resize-none"
                              placeholder="Describe que hace este script...">${escapeHtml(script?.description || '')}</textarea>
                </div>
            </fieldset>

            <!-- Configuracion de programacion -->
            <fieldset class="space-y-4 pt-4 border-t border-dark-700">
                <legend class="text-xs font-semibold text-dark-400 uppercase tracking-wide mb-3">Programacion</legend>

                <!-- Inicio Programado -->
                <div class="space-y-2">
                    <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox" name="scheduled_start_enabled" ${script?.scheduled_start_enabled ? 'checked' : ''}
                               class="w-4 h-4 rounded border-dark-600 bg-dark-800 text-blue-600 focus:ring-blue-500 focus:ring-offset-dark-900">
                        <span class="text-sm text-dark-200">Inicio Programado</span>
                    </label>

                    <div id="scheduled-start-config" class="ml-7 ${script?.scheduled_start_enabled ? '' : 'opacity-50'}">
                        <input type="datetime-local" name="scheduled_start_datetime"
                               value="${script?.scheduled_start_datetime?.slice(0, 16) || ''}"
                               ${script?.scheduled_start_enabled ? '' : 'disabled'}
                               class="bg-dark-800 border border-dark-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 disabled:cursor-not-allowed">
                    </div>
                </div>

                <!-- Repeticion -->
                <div class="space-y-2 pt-2">
                    <label class="flex items-center gap-3 cursor-pointer">
                        <input type="checkbox" name="repeat_enabled" ${script?.repeat_enabled ? 'checked' : ''}
                               class="w-4 h-4 rounded border-dark-600 bg-dark-800 text-blue-600 focus:ring-blue-500 focus:ring-offset-dark-900">
                        <span class="text-sm text-dark-200">Repeticion</span>
                    </label>

                    <div id="schedule-config" class="space-y-4 ml-7 ${script?.repeat_enabled ? '' : 'opacity-50'}">
                        <div class="flex items-center gap-3">
                            <span class="text-sm text-dark-300">Ejecutar cada</span>
                            <input type="number" name="interval_value" min="1"
                                   ${script?.repeat_enabled ? '' : 'disabled'}
                                   class="w-20 bg-dark-800 border border-dark-600 rounded-lg px-3 py-1.5 text-sm text-center focus:outline-none focus:border-blue-500 disabled:cursor-not-allowed"
                                   value="${script?.interval_value || 1}">
                            <select name="interval_unit"
                                    ${script?.repeat_enabled ? '' : 'disabled'}
                                    class="bg-dark-800 border border-dark-600 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500 disabled:cursor-not-allowed">
                                <option value="seconds" ${script?.interval_unit === 'seconds' ? 'selected' : ''}>segundos</option>
                                <option value="minutes" ${script?.interval_unit === 'minutes' ? 'selected' : ''}>minutos</option>
                                <option value="hours" ${script?.interval_unit === 'hours' ? 'selected' : ''}>horas</option>
                                <option value="days" ${script?.interval_unit === 'days' ? 'selected' : ''}>dias</option>
                            </select>
                        </div>

                        <div>
                            <label class="block text-xs font-medium text-dark-300 mb-2">Dias de la semana</label>
                            <div id="weekdays-container" class="flex gap-2">
                                ${['L', 'M', 'X', 'J', 'V', 'S', 'D'].map((day, i) => `
                                    <div class="weekday-btn ${allDays || weekdays.includes(i) ? 'active' : ''} ${script?.repeat_enabled ? '' : 'pointer-events-none'}" data-day="${i}">${day}</div>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                </div>
            </fieldset>

            <!-- Acciones -->
            <div class="flex items-center gap-3 pt-4 border-t border-dark-700">
                ${!isNew ? `
                    <button type="button" id="btn-activate" onclick="activateScript(${script.id})"
                            class="${canActivate
                                ? 'px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-medium transition-colors'
                                : 'px-4 py-2 bg-dark-600 cursor-not-allowed rounded-lg text-sm font-medium text-dark-400'}"
                            ${canActivate ? '' : 'disabled'}
                            title="${!hasScheduling ? 'Configura Inicio Programado o Repeticion para activar' : ''}">
                        Activar
                    </button>
                    <button type="button" id="btn-stop" onclick="deactivateScript(${script.id})"
                            class="${isActive
                                ? 'px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg text-sm font-medium transition-colors'
                                : 'px-4 py-2 bg-dark-600 cursor-not-allowed rounded-lg text-sm font-medium text-dark-400'}"
                            ${isActive ? '' : 'disabled'}>
                        Detener
                    </button>
                ` : ''}
                <button type="submit" id="btn-save"
                        class="${isNew
                            ? 'px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors'
                            : 'px-4 py-2 bg-dark-600 cursor-not-allowed rounded-lg text-sm font-medium text-dark-400'}"
                        ${isNew ? '' : 'disabled'}>
                    ${isNew ? 'Crear Script' : 'Guardar Cambios'}
                </button>
                ${!isNew ? `
                    <button type="button" onclick="deleteScript(${script.id})"
                            class="px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg text-sm font-medium transition-colors ml-auto">
                        Eliminar
                    </button>
                ` : ''}
            </div>

            ${!isNew ? `
                <div class="text-xs text-dark-500 pt-2">
                    Ultima ejecucion: ${script.last_run ? new Date(script.last_run).toLocaleString() : 'Nunca'} |
                    Proxima ejecucion: ${script.next_run ? new Date(script.next_run).toLocaleString() : 'No programada'}
                </div>
            ` : ''}
        </form>
    `;
}

function attachFormHandlers() {
    const form = document.getElementById('script-form');
    const repeatEnabled = form.querySelector('[name="repeat_enabled"]');
    const scheduleConfig = document.getElementById('schedule-config');
    const scheduledStartEnabled = form.querySelector('[name="scheduled_start_enabled"]');
    const scheduledStartConfig = document.getElementById('scheduled-start-config');
    const scheduledStartDatetime = form.querySelector('[name="scheduled_start_datetime"]');
    const intervalValue = form.querySelector('[name="interval_value"]');
    const intervalUnit = form.querySelector('[name="interval_unit"]');
    const weekdaysContainer = document.getElementById('weekdays-container');

    repeatEnabled?.addEventListener('change', (e) => {
        const enabled = e.target.checked;
        scheduleConfig.classList.toggle('opacity-50', !enabled);
        intervalValue.disabled = !enabled;
        intervalUnit.disabled = !enabled;
        weekdaysContainer?.querySelectorAll('.weekday-btn').forEach(btn => {
            btn.classList.toggle('pointer-events-none', !enabled);
        });
        checkForChanges();
        updateActivateButton();
    });

    scheduledStartEnabled?.addEventListener('change', (e) => {
        const enabled = e.target.checked;
        scheduledStartConfig.classList.toggle('opacity-50', !enabled);
        scheduledStartDatetime.disabled = !enabled;
        if (enabled && !scheduledStartDatetime.value) {
            // Set default to current local datetime when enabling
            const now = new Date();
            const year = now.getFullYear();
            const month = String(now.getMonth() + 1).padStart(2, '0');
            const day = String(now.getDate()).padStart(2, '0');
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            scheduledStartDatetime.value = `${year}-${month}-${day}T${hours}:${minutes}`;
        } else if (!enabled) {
            // Clear datetime when disabling
            scheduledStartDatetime.value = '';
        }
        checkForChanges();
        updateActivateButton();
    });

    // Add change listeners for tracked fields
    form.querySelector('[name="path"]')?.addEventListener('input', checkForChanges);
    form.querySelector('[name="interval_value"]')?.addEventListener('input', checkForChanges);
    form.querySelector('[name="interval_unit"]')?.addEventListener('change', checkForChanges);
    form.querySelector('[name="scheduled_start_datetime"]')?.addEventListener('change', checkForChanges);

    document.querySelectorAll('.weekday-btn').forEach(el => {
        el.addEventListener('click', () => {
            el.classList.toggle('active');
            checkForChanges();
        });
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveScript();
    });

    // Initial check
    checkForChanges();
}

function checkForChanges() {
    const form = document.getElementById('script-form');
    const btnSave = document.getElementById('btn-save');
    if (!form || !btnSave || !originalFormData) {
        // New script - always enable save
        if (btnSave) {
            btnSave.disabled = false;
            btnSave.className = 'px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors';
        }
        return;
    }

    const currentData = {
        path: form.querySelector('[name="path"]')?.value || '',
        repeat_enabled: form.querySelector('[name="repeat_enabled"]')?.checked || false,
        interval_value: parseInt(form.querySelector('[name="interval_value"]')?.value) || 1,
        interval_unit: form.querySelector('[name="interval_unit"]')?.value || 'seconds',
        weekdays: getSelectedWeekdays(),
        scheduled_start_enabled: form.querySelector('[name="scheduled_start_enabled"]')?.checked || false,
        scheduled_start_datetime: form.querySelector('[name="scheduled_start_datetime"]')?.value || '',
    };

    const hasChanges =
        currentData.path !== originalFormData.path ||
        currentData.repeat_enabled !== originalFormData.repeat_enabled ||
        currentData.interval_value !== originalFormData.interval_value ||
        currentData.interval_unit !== originalFormData.interval_unit ||
        !arraysEqual(currentData.weekdays, originalFormData.weekdays) ||
        currentData.scheduled_start_enabled !== originalFormData.scheduled_start_enabled ||
        currentData.scheduled_start_datetime !== originalFormData.scheduled_start_datetime;

    btnSave.disabled = !hasChanges;
    btnSave.className = hasChanges
        ? 'px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors'
        : 'px-4 py-2 bg-dark-600 cursor-not-allowed rounded-lg text-sm font-medium text-dark-400';
}

function updateActivateButton() {
    const form = document.getElementById('script-form');
    const btnActivate = document.getElementById('btn-activate');
    if (!form || !btnActivate) return;

    const scheduledStartEnabled = form.querySelector('[name="scheduled_start_enabled"]')?.checked || false;
    const repeatEnabled = form.querySelector('[name="repeat_enabled"]')?.checked || false;
    const hasScheduling = scheduledStartEnabled || repeatEnabled;

    // Get current script to check if already active
    const script = scripts.find(s => s.id === selectedScriptId);
    const isActive = script?.is_active || false;
    const canActivate = !isActive && hasScheduling;

    btnActivate.disabled = !canActivate;
    btnActivate.className = canActivate
        ? 'px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg text-sm font-medium transition-colors'
        : 'px-4 py-2 bg-dark-600 cursor-not-allowed rounded-lg text-sm font-medium text-dark-400';
    btnActivate.title = !hasScheduling ? 'Configura Inicio Programado o Repeticion para activar' : '';
}

function getSelectedWeekdays() {
    const weekdays = [];
    document.querySelectorAll('.weekday-btn.active').forEach(el => {
        weekdays.push(parseInt(el.dataset.day));
    });
    return weekdays.sort();
}

function arraysEqual(a, b) {
    if (a.length !== b.length) return false;
    const sortedA = [...a].sort();
    const sortedB = [...b].sort();
    return sortedA.every((val, i) => val === sortedB[i]);
}

async function saveScript() {
    const form = document.getElementById('script-form');
    const formData = new FormData(form);

    const weekdays = getSelectedWeekdays();

    const scheduledStartDatetime = formData.get('scheduled_start_datetime');

    const data = {
        name: formData.get('name'),
        path: formData.get('path'),
        description: formData.get('description') || null,
        repeat_enabled: formData.get('repeat_enabled') === 'on',
        interval_value: parseInt(formData.get('interval_value')) || null,
        interval_unit: formData.get('interval_unit') || null,
        weekdays: weekdays.length === 7 ? null : weekdays,
        scheduled_start_enabled: formData.get('scheduled_start_enabled') === 'on',
        scheduled_start_datetime: scheduledStartDatetime ? scheduledStartDatetime + ':00' : null,
    };

    try {
        const url = selectedScriptId ? `/api/scripts/${selectedScriptId}` : '/api/scripts';
        const method = selectedScriptId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        if (!response.ok) throw new Error('Failed to save');

        const savedScript = await response.json();
        await loadScripts();

        if (!selectedScriptId) {
            selectScript(savedScript.id);
        } else {
            // Update originalFormData with saved values and disable button
            originalFormData = {
                path: data.path,
                repeat_enabled: data.repeat_enabled,
                interval_value: data.interval_value || 1,
                interval_unit: data.interval_unit || 'seconds',
                weekdays: weekdays.length === 7 ? [0, 1, 2, 3, 4, 5, 6] : weekdays,
                scheduled_start_enabled: data.scheduled_start_enabled,
                scheduled_start_datetime: scheduledStartDatetime || '',
            };
            checkForChanges();
        }
    } catch (error) {
        alert('Error al guardar el script');
    }
}

async function deleteScript(id) {
    if (!confirm('Estas seguro de que quieres eliminar este script?')) return;

    try {
        await fetch(`/api/scripts/${id}`, { method: 'DELETE' });
        selectedScriptId = null;
        detailTitle.textContent = 'Detalle del Script';
        scriptDetail.classList.add('hidden');
        scriptPlaceholder.classList.remove('hidden');
        await loadScripts();
    } catch (error) {
        alert('Error al eliminar el script');
    }
}

async function activateScript(id) {
    try {
        // Enable the script (sets is_active = true, starts scheduler)
        const enableResponse = await fetch(`/api/scripts/${id}/enable`, { method: 'POST' });
        if (!enableResponse.ok) {
            const error = await enableResponse.json();
            throw new Error(error.detail || 'Failed to enable');
        }

        const script = scripts.find(s => s.id === id);
        const hasFutureScheduledStart = script?.scheduled_start_enabled &&
            script?.scheduled_start_datetime &&
            new Date(script.scheduled_start_datetime) > new Date();

        // Only execute immediately if there's NO future scheduled start
        if (!hasFutureScheduledStart) {
            const runResponse = await fetch(`/api/scripts/${id}/run`, { method: 'POST' });
            if (!runResponse.ok && runResponse.status !== 409) {
                // 409 = already running, which is fine
                const error = await runResponse.json();
                throw new Error(error.detail || 'Failed to run');
            }
        }

        // Reload scripts and update UI
        await loadScripts();
        showScriptDetail(id);
    } catch (error) {
        alert('Error al activar: ' + error.message);
    }
}

async function deactivateScript(id) {
    try {
        // First try to stop current execution (may fail if not running, that's ok)
        try {
            await fetch(`/api/scripts/${id}/stop`, { method: 'POST' });
        } catch (e) {
            // Ignore - script might not be running
        }

        // Disable the script (sets is_active = false, stops scheduler)
        const disableResponse = await fetch(`/api/scripts/${id}/disable`, { method: 'POST' });
        if (!disableResponse.ok) {
            const error = await disableResponse.json();
            throw new Error(error.detail || 'Failed to disable');
        }

        // Reload scripts and update UI
        await loadScripts();
        showScriptDetail(id);
    } catch (error) {
        alert('Error al detener: ' + error.message);
    }
}

function updateScriptFilter() {
    logFilterScript.innerHTML = '<option value="">Todos los scripts</option>' +
        scripts.map(s => `<option value="${s.id}">${escapeHtml(s.name)}</option>`).join('');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
