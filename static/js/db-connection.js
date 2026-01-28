/**
 * Database Connection Module
 * Manages database session, cookies, and automatic header injection
 */

// Global session object
window.DB_SESSION = {
    sessionKey: null,
    db: null,
    user: null,
    serverPort: null
};

// ==================== Cookie Helpers ====================

function setCookie(name, value, days = 7) {
    const expires = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
}

function getCookie(name) {
    const match = document.cookie.split('; ').find(row => row.startsWith(name + '='));
    return match ? decodeURIComponent(match.split('=')[1]) : null;
}

function deleteCookie(name) {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
}

// ==================== Session Management ====================

/**
 * Initialize session from cookies on page load
 */
function initFromCookies() {
    DB_SESSION.sessionKey = getCookie('session_key');
    DB_SESSION.db = getCookie('connected_db');
    DB_SESSION.user = getCookie('connected_user');
    DB_SESSION.serverPort = getCookie('server_port') || 'http://localhost:7239';

    console.log('DB_SESSION initialized from cookies:', {
        hasSessionKey: !!DB_SESSION.sessionKey,
        db: DB_SESSION.db,
        user: DB_SESSION.user
    });
}

/**
 * Save session to cookies
 */
function saveSessionToCookies(sessionKey, db, user, serverPort) {
    DB_SESSION.sessionKey = sessionKey;
    DB_SESSION.db = db;
    DB_SESSION.user = user;
    DB_SESSION.serverPort = serverPort;

    setCookie('session_key', sessionKey);
    setCookie('connected_db', db);
    setCookie('connected_user', user);
    setCookie('server_port', serverPort);
}

/**
 * Clear session cookies
 */
function clearSessionCookies() {
    DB_SESSION.sessionKey = null;
    DB_SESSION.db = null;
    DB_SESSION.user = null;

    deleteCookie('session_key');
    deleteCookie('connected_db');
    deleteCookie('connected_user');
}

// ==================== AJAX Header Injection ====================

// Intercept jQuery AJAX requests to add session key header
if (typeof $ !== 'undefined') {
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (DB_SESSION.sessionKey) {
                xhr.setRequestHeader('X-APL-SessionKey', DB_SESSION.sessionKey);
            }
        }
    });
}

// Callback for 401 errors (to show connection modal)
let on401Callback = null;

/**
 * Set callback for 401 errors
 * @param {Function} callback - Function to call on 401 error
 */
function setOn401Callback(callback) {
    on401Callback = callback;
}

/**
 * Handle session invalidation (401 error)
 * Clears cookies and triggers callback
 */
function handleSessionInvalid() {
    console.log('Session invalid - clearing cookies and triggering reconnect');
    clearSessionCookies();
    if (on401Callback) {
        on401Callback();
    }
}

// Intercept fetch API to add session key header and handle 401 responses
const originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
    if (DB_SESSION.sessionKey) {
        options.headers = options.headers || {};
        if (options.headers instanceof Headers) {
            options.headers.set('X-APL-SessionKey', DB_SESSION.sessionKey);
        } else {
            options.headers['X-APL-SessionKey'] = DB_SESSION.sessionKey;
        }
    }
    return originalFetch.call(this, url, options).then(response => {
        // Check for 401 with session error
        if (response.status === 401) {
            // Clone response to read body without consuming it
            response.clone().json().then(data => {
                if (data.error_description &&
                    (data.error_description.includes('сессии не действителен') ||
                     data.error_description.includes('session') ||
                     data.error_description.includes('SessionKey'))) {
                    handleSessionInvalid();
                }
            }).catch(() => {
                // If can't parse JSON, still handle as potential session error
                handleSessionInvalid();
            });
        }
        return response;
    });
};

// ==================== API Functions ====================

/**
 * Connect to database
 * @param {Object} formData - Connection parameters
 * @returns {Promise<Object>} - Connection result
 */
async function connectToDb(formData) {
    try {
        // Use original fetch to avoid adding old session key
        const response = await originalFetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (data.connected && data.session_key) {
            saveSessionToCookies(
                data.session_key,
                data.db,
                data.user,
                formData.server_port
            );
            console.log('Connected to DB:', data.db);
        }

        return data;
    } catch (error) {
        console.error('Connection error:', error);
        return { connected: false, message: error.message };
    }
}

/**
 * Disconnect from database
 * @returns {Promise<Object>} - Disconnection result
 */
async function disconnectFromDb() {
    try {
        if (DB_SESSION.sessionKey) {
            await fetch('/api/disconnect', { method: 'POST' });
        }
        clearSessionCookies();
        console.log('Disconnected from DB');
        return { disconnected: true };
    } catch (error) {
        console.error('Disconnect error:', error);
        clearSessionCookies();
        return { disconnected: false, message: error.message };
    }
}

/**
 * Check connection status from server
 * @returns {Promise<Object>} - Status object
 */
async function checkConnectionStatus() {
    try {
        const response = await fetch('/api/status');
        return await response.json();
    } catch (error) {
        console.error('Status check error:', error);
        return { connected: false, message: error.message };
    }
}

/**
 * Load database list from server
 * @returns {Promise<Array>} - List of databases
 */
async function loadDbList() {
    try {
        const response = await originalFetch('/api/dblist');
        const data = await response.json();
        return data.databases || [];
    } catch (error) {
        console.error('Error loading DB list:', error);
        return [];
    }
}

/**
 * Get connection status text for UI
 * @returns {string} - Status text
 */
function getConnectionStatusText() {
    if (DB_SESSION.sessionKey && DB_SESSION.db && DB_SESSION.user) {
        return `DB: ${DB_SESSION.db} User: ${DB_SESSION.user}`;
    }
    return 'DB Status: Disconnected';
}

/**
 * Check if connected
 * @returns {boolean}
 */
function isConnected() {
    return !!DB_SESSION.sessionKey;
}

// ==================== UI Helpers ====================

/**
 * Update status element with current connection status
 * @param {string} selector - CSS selector for status element
 */
function updateStatusUI(selector) {
    const el = document.querySelector(selector);
    if (el) {
        el.textContent = getConnectionStatusText();
    }
}

/**
 * Populate DB select with databases
 * @param {string} selector - CSS selector for select element
 * @param {string} defaultDb - Default database to select
 */
async function populateDbSelect(selector, defaultDb) {
    const select = document.querySelector(selector);
    if (!select) return;

    const databases = await loadDbList();
    select.innerHTML = '';

    if (databases.length > 0) {
        databases.forEach(db => {
            const option = document.createElement('option');
            option.value = db;
            option.textContent = db;
            if (db === defaultDb) option.selected = true;
            select.appendChild(option);
        });
    } else {
        // Fallback
        const option = document.createElement('option');
        option.value = defaultDb || 'pss_moma_08_07_2025';
        option.textContent = defaultDb || 'pss_moma_08_07_2025';
        select.appendChild(option);
    }
}

/**
 * Pre-fill connection form from cookies
 * @param {Object} selectors - Object with form field selectors
 */
function prefillConnectionForm(selectors) {
    if (selectors.serverPort) {
        const el = document.querySelector(selectors.serverPort);
        if (el && DB_SESSION.serverPort) el.value = DB_SESSION.serverPort;
    }
    if (selectors.user) {
        const el = document.querySelector(selectors.user);
        if (el && DB_SESSION.user) el.value = DB_SESSION.user;
    }
}

// ==================== Initialize ====================

// Initialize from cookies when script loads
initFromCookies();

// Export functions for global access
window.dbConnection = {
    connect: connectToDb,
    disconnect: disconnectFromDb,
    checkStatus: checkConnectionStatus,
    loadDbList: loadDbList,
    isConnected: isConnected,
    getStatusText: getConnectionStatusText,
    updateStatusUI: updateStatusUI,
    populateDbSelect: populateDbSelect,
    prefillForm: prefillConnectionForm,
    initFromCookies: initFromCookies,
    clearSession: clearSessionCookies,
    setOn401Callback: setOn401Callback,
    handleSessionInvalid: handleSessionInvalid
};
