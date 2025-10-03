// WebSocket client for real-time updates

let ws = null;
let connectionStatus = 'disconnected';
let reconnectTimeout = null;
let eventHandlers = {};

export function initializeWebSocket() {
    connectWebSocket();
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Extract review ID from URL path (e.g., /review/abc123/view)
    const reviewId = window.location.pathname.split('/')[2];
    const wsUrl = `${protocol}//${window.location.host}/review/${reviewId}/ws`;

    console.log('Connecting to WebSocket:', wsUrl);

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket connected');
            updateConnectionStatus('connected');

            // Clear any pending reconnect timeout
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout);
                reconnectTimeout = null;
            }
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('WebSocket message received:', data);
                handleEvent(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateConnectionStatus('error');
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            updateConnectionStatus('disconnected');

            // Attempt to reconnect after 5 seconds
            reconnectTimeout = setTimeout(() => {
                console.log('Attempting to reconnect WebSocket...');
                connectWebSocket();
            }, 5000);
        };
    } catch (error) {
        console.error('Error creating WebSocket:', error);
        updateConnectionStatus('error');

        // Attempt to reconnect after 5 seconds
        reconnectTimeout = setTimeout(() => {
            console.log('Attempting to reconnect WebSocket...');
            connectWebSocket();
        }, 5000);
    }
}

function updateConnectionStatus(status) {
    connectionStatus = status;

    // Update status indicator in the UI
    const statusIndicator = document.getElementById('connection-status');
    if (statusIndicator) {
        statusIndicator.textContent = status === 'connected' ? '' : '(not connected)';
        statusIndicator.className = `connection-status ${status}`;
    }
}

function handleEvent(event) {
    const eventType = event.type;

    // Call registered handlers for this event type
    if (eventHandlers[eventType]) {
        eventHandlers[eventType].forEach(handler => {
            try {
                handler(event);
            } catch (error) {
                console.error(`Error in event handler for ${eventType}:`, error);
            }
        });
    }

    // Call global handlers
    if (eventHandlers['*']) {
        eventHandlers['*'].forEach(handler => {
            try {
                handler(event);
            } catch (error) {
                console.error('Error in global event handler:', error);
            }
        });
    }
}

export function onEvent(eventType, handler) {
    if (!eventHandlers[eventType]) {
        eventHandlers[eventType] = [];
    }
    eventHandlers[eventType].push(handler);
}

export function offEvent(eventType, handler) {
    if (eventHandlers[eventType]) {
        eventHandlers[eventType] = eventHandlers[eventType].filter(h => h !== handler);
    }
}

export function getConnectionStatus() {
    return connectionStatus;
}

export function closeWebSocket() {
    if (ws) {
        ws.close();
        ws = null;
    }
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
    }
}
