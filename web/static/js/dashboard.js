// Dashboard JavaScript for Binance Trading Bot

// Global variables
let botSettings = {
    mode: 'signal',
    symbols: ['BTCUSDT']
};

// Log initial state
console.log("Dashboard.js loaded");
console.log("Initial bot settings:", botSettings);

// DOM elements - these will be properly initialized in the DOMContentLoaded event
let startBotBtn = null;
let stopBotBtn = null;
let botStatusIndicator = null;
let tradingModeSelect = null;
let symbolsSelect = null;
let saveSettingsBtn = null;

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, initializing dashboard...");

    // Initialize global DOM elements
    startBotBtn = document.getElementById('start-bot-btn');
    stopBotBtn = document.getElementById('stop-bot-btn');
    botStatusIndicator = document.getElementById('bot-status-indicator');
    tradingModeSelect = document.getElementById('trading-mode-select');
    symbolsSelect = document.getElementById('symbols-select');
    saveSettingsBtn = document.getElementById('save-settings-btn');

    // Check if critical elements exist
    if (!startBotBtn || !stopBotBtn) {
        console.error("Start or stop button not found! startBotBtn:", startBotBtn, "stopBotBtn:", stopBotBtn);
        alert("Error: Start or stop button not found. Please refresh the page.");
        return;
    }

    console.log("Setting up event listeners...");

    // Set up event listeners with error handling
    try {
        startBotBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log("Start button clicked");
            startBot();
        });

        stopBotBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log("Stop button clicked");
            stopBot();
        });

        if (saveSettingsBtn) {
            saveSettingsBtn.addEventListener('click', function(e) {
                e.preventDefault();
                console.log("Save settings button clicked");
                saveSettings();
            });
        }

        console.log("Event listeners set up successfully");
    } catch (error) {
        console.error("Error setting up event listeners:", error);
        alert("Error setting up event listeners. Please refresh the page.");
    }

    // Load available symbols
    loadAvailableSymbols();

    // Start periodic status updates
    setInterval(updateDashboard, 5000);

    // Initial dashboard update
    updateDashboard();
});

// Load available trading symbols
function loadAvailableSymbols() {
    console.log("Loading available symbols...");

    // Check if symbolsSelect is initialized
    if (!symbolsSelect) {
        console.error("symbolsSelect is not initialized");
        symbolsSelect = document.getElementById('symbols-select');

        if (!symbolsSelect) {
            console.error("Could not find symbols-select element");
            return;
        }
    }

    fetch('/api/symbols')
        .then(response => {
            console.log("Symbols response status:", response.status);
            return response.json();
        })
        .then(data => {
            console.log("Symbols data:", data);

            if (data.success) {
                // Clear existing options
                symbolsSelect.innerHTML = '';

                // Add new options
                data.symbols.forEach(symbol => {
                    const option = document.createElement('option');
                    option.value = symbol;
                    option.textContent = symbol;
                    symbolsSelect.appendChild(option);
                });

                // Select default symbol
                if (botSettings.symbols.length > 0) {
                    botSettings.symbols.forEach(symbol => {
                        const option = Array.from(symbolsSelect.options).find(opt => opt.value === symbol);
                        if (option) {
                            option.selected = true;
                        }
                    });
                }

                console.log("Symbols loaded successfully");
            } else {
                console.error('Error loading symbols:', data.message);
                // Add default symbol if loading fails
                symbolsSelect.innerHTML = '<option value="BTCUSDT">BTCUSDT</option>';
            }
        })
        .catch(error => {
            console.error('Error fetching symbols:', error);
            symbolsSelect.innerHTML = '<option value="BTCUSDT">BTCUSDT</option>';
        });
}

// Save bot settings
function saveSettings() {
    console.log("Saving bot settings...");

    // Check if tradingModeSelect is initialized
    if (!tradingModeSelect) {
        console.error("tradingModeSelect is not initialized");
        tradingModeSelect = document.getElementById('trading-mode-select');

        if (!tradingModeSelect) {
            console.error("Could not find trading-mode-select element");
            alert("Error: Could not find trading mode selector. Please refresh the page.");
            return;
        }
    }

    // Check if symbolsSelect is initialized
    if (!symbolsSelect) {
        console.error("symbolsSelect is not initialized");
        symbolsSelect = document.getElementById('symbols-select');

        if (!symbolsSelect) {
            console.error("Could not find symbols-select element");
            alert("Error: Could not find symbols selector. Please refresh the page.");
            return;
        }
    }

    try {
        // Get selected trading mode
        botSettings.mode = tradingModeSelect.value;

        // Get selected symbols
        botSettings.symbols = Array.from(symbolsSelect.selectedOptions).map(option => option.value);

        // If no symbols are selected, use default
        if (botSettings.symbols.length === 0) {
            botSettings.symbols = ['BTCUSDT'];
        }

        console.log("Settings saved:", botSettings);

        // Close the modal
        try {
            const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
            if (modal) {
                modal.hide();
            }
        } catch (error) {
            console.error("Error closing modal:", error);
        }

        // Show confirmation
        alert(`Settings saved!\nTrading Mode: ${botSettings.mode}\nSymbols: ${botSettings.symbols.join(', ')}`);
    } catch (error) {
        console.error("Error saving settings:", error);
        alert("Error saving settings. Please try again.");
    }
}

// Start the trading bot
function startBot() {
    console.log("Starting bot with settings:", botSettings);

    // Get the buttons again to ensure we have the correct references
    const startBotBtn = document.getElementById('start-bot-btn');
    const stopBotBtn = document.getElementById('stop-bot-btn');
    const botStatusIndicator = document.getElementById('bot-status-indicator');

    if (!startBotBtn || !stopBotBtn) {
        console.error("Buttons not found!");
        return;
    }

    // Disable start button and enable stop button
    startBotBtn.disabled = true;
    stopBotBtn.disabled = false;

    // Send start request to the server
    fetch('/api/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            mode: botSettings.mode,
            symbols: botSettings.symbols
        })
    })
    .then(response => {
        console.log("Start response status:", response.status);
        return response.json();
    })
    .then(data => {
        console.log("Start response data:", data);

        if (data.success) {
            // Update status indicator
            botStatusIndicator.innerHTML = '<i class="bi bi-circle-fill text-success me-1"></i><span>Running</span>';
            botStatusIndicator.classList.remove('status-stopped');
            botStatusIndicator.classList.add('status-running');

            // Show success message
            alert(data.message);

            // Update dashboard immediately
            updateDashboard();
        } else {
            // Re-enable start button and disable stop button
            startBotBtn.disabled = false;
            stopBotBtn.disabled = true;

            // Show error message
            alert('Error starting bot: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error starting bot:', error);

        // Re-enable start button and disable stop button
        startBotBtn.disabled = false;
        stopBotBtn.disabled = true;

        // Show error message
        alert('Error starting bot: ' + error.message);
    });
}

// Stop the trading bot
function stopBot() {
    console.log("Stopping bot");

    // Get the buttons again to ensure we have the correct references
    const startBotBtn = document.getElementById('start-bot-btn');
    const stopBotBtn = document.getElementById('stop-bot-btn');
    const botStatusIndicator = document.getElementById('bot-status-indicator');

    if (!startBotBtn || !stopBotBtn) {
        console.error("Buttons not found!");
        return;
    }

    // Disable stop button and enable start button
    stopBotBtn.disabled = true;
    startBotBtn.disabled = false;

    // Send stop request to the server
    fetch('/api/stop', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({}) // Send empty JSON object
    })
    .then(response => {
        console.log("Stop response status:", response.status);
        return response.json();
    })
    .then(data => {
        console.log("Stop response data:", data);

        if (data.success) {
            // Update status indicator
            botStatusIndicator.innerHTML = '<i class="bi bi-circle-fill text-danger me-1"></i><span>Stopped</span>';
            botStatusIndicator.classList.remove('status-running');
            botStatusIndicator.classList.add('status-stopped');

            // Show success message
            alert(data.message);

            // Update dashboard immediately
            updateDashboard();
        } else {
            // Re-enable stop button and disable start button
            stopBotBtn.disabled = false;
            startBotBtn.disabled = true;

            // Show error message
            alert('Error stopping bot: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error stopping bot:', error);

        // Re-enable stop button and disable start button
        stopBotBtn.disabled = false;
        startBotBtn.disabled = true;

        // Show error message
        alert('Error stopping bot: ' + error.message);
    });
}

// Update the dashboard with current bot status
function updateDashboard() {
    console.log("Updating dashboard...");

    // Get the buttons again to ensure we have the correct references
    const startBotBtn = document.getElementById('start-bot-btn');
    const stopBotBtn = document.getElementById('stop-bot-btn');
    const botStatusIndicator = document.getElementById('bot-status-indicator');

    if (!startBotBtn || !stopBotBtn || !botStatusIndicator) {
        console.error("Required elements not found!");
        return;
    }

    fetch('/api/status')
        .then(response => {
            console.log("Status response status:", response.status);
            return response.json();
        })
        .then(data => {
            console.log("Status data:", data);

            // Update bot status indicator
            if (data.is_running) {
                console.log("Bot is running");
                botStatusIndicator.innerHTML = '<i class="bi bi-circle-fill text-success me-1"></i><span>Running</span>';
                botStatusIndicator.classList.remove('status-stopped');
                botStatusIndicator.classList.add('status-running');

                // Update buttons
                startBotBtn.disabled = true;
                stopBotBtn.disabled = false;

                console.log("Updated buttons: start disabled, stop enabled");
            } else {
                console.log("Bot is stopped");
                botStatusIndicator.innerHTML = '<i class="bi bi-circle-fill text-danger me-1"></i><span>Stopped</span>';
                botStatusIndicator.classList.remove('status-running');
                botStatusIndicator.classList.add('status-stopped');

                // Update buttons
                startBotBtn.disabled = false;
                stopBotBtn.disabled = true;

                console.log("Updated buttons: start enabled, stop disabled");
            }

            // Update account summary
            updateAccountSummary(data.account_info || {}, data.pnl || {});

            // Update bot information
            updateBotInfo(data);

            // Update positions table
            updatePositionsTable(data.positions || []);

            // Update open orders table
            updateOrdersTable(data.orders || []);

            // Update trades table
            updateTradesTable(data.trades || []);

            console.log("Dashboard updated successfully");
        })
        .catch(error => {
            console.error('Error updating dashboard:', error);
        });
}

// Update account summary section
function updateAccountSummary(accountInfo, pnl) {
    // Update balance information
    document.getElementById('total-balance').textContent = formatCurrency(accountInfo.total_wallet_balance || 0) + ' USDT';
    document.getElementById('available-balance').textContent = formatCurrency(accountInfo.available_balance || 0) + ' USDT';

    // Update PnL information
    const unrealizedPnl = accountInfo.total_unrealized_profit || 0;
    const unrealizedPnlElement = document.getElementById('unrealized-pnl');
    unrealizedPnlElement.textContent = formatCurrency(unrealizedPnl) + ' USDT';
    unrealizedPnlElement.className = unrealizedPnl >= 0 ? 'positive-value' : 'negative-value';

    const dailyPnl = pnl.daily || 0;
    const dailyPnlElement = document.getElementById('daily-pnl');
    dailyPnlElement.textContent = formatPercentage(dailyPnl);
    dailyPnlElement.className = dailyPnl >= 0 ? 'positive-value' : 'negative-value';
}

// Update bot information section
function updateBotInfo(data) {
    // Update trading mode
    const tradingModeElement = document.getElementById('trading-mode');
    if (data.is_running) {
        tradingModeElement.textContent = data.mode === 'grid' ? 'Grid Trading' : 'Signal Trading';
    } else {
        tradingModeElement.textContent = 'Not Running';
    }

    // Update running since
    document.getElementById('running-since').textContent = data.start_time || '-';

    // Update trading symbols
    const symbolsContainer = document.getElementById('trading-symbols');
    if (data.symbols && data.symbols.length > 0) {
        symbolsContainer.innerHTML = '';
        data.symbols.forEach(symbol => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-primary';
            badge.textContent = symbol;
            symbolsContainer.appendChild(badge);
        });
    } else {
        symbolsContainer.innerHTML = '<span class="badge bg-secondary">None</span>';
    }

    // Update active positions count
    document.getElementById('active-positions-count').textContent = data.positions ? data.positions.length : 0;
}

// Update positions table
function updatePositionsTable(positions) {
    const positionsTable = document.getElementById('positions-table');

    if (!positions || positions.length === 0) {
        positionsTable.innerHTML = '<tr><td colspan="6" class="text-center">No open positions</td></tr>';
        return;
    }

    positionsTable.innerHTML = '';

    positions.forEach(position => {
        const positionAmt = parseFloat(position.positionAmt);
        if (positionAmt === 0) return;

        const entryPrice = parseFloat(position.entryPrice);
        const markPrice = parseFloat(position.markPrice || position.entryPrice);
        const pnl = parseFloat(position.unrealizedProfit || 0);
        const pnlPercent = (pnl / (Math.abs(positionAmt) * entryPrice)) * 100;

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${position.symbol}</td>
            <td>${position.positionSide}</td>
            <td>${formatPrice(entryPrice)}</td>
            <td>${formatPrice(markPrice)}</td>
            <td>${formatQuantity(Math.abs(positionAmt))}</td>
            <td class="${pnl >= 0 ? 'positive-value' : 'negative-value'}">
                ${formatCurrency(pnl)} (${formatPercentage(pnlPercent)})
            </td>
        `;

        positionsTable.appendChild(row);
    });
}

// Update orders table
function updateOrdersTable(orders) {
    const ordersTable = document.getElementById('open-orders-table');

    if (!orders || orders.length === 0) {
        ordersTable.innerHTML = '<tr><td colspan="5" class="text-center">No open orders</td></tr>';
        return;
    }

    ordersTable.innerHTML = '';

    orders.forEach(order => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${order.symbol}</td>
            <td>${order.type}</td>
            <td>${order.side}</td>
            <td>${formatPrice(parseFloat(order.price || order.stopPrice || 0))}</td>
            <td>${formatQuantity(parseFloat(order.origQty))}</td>
        `;

        ordersTable.appendChild(row);
    });
}

// Update trades table
function updateTradesTable(trades) {
    const tradesTable = document.getElementById('trades-table');

    if (!trades || trades.length === 0) {
        tradesTable.innerHTML = '<tr><td colspan="6" class="text-center">No recent trades</td></tr>';
        return;
    }

    tradesTable.innerHTML = '';

    trades.forEach(trade => {
        const time = new Date(parseInt(trade.time));
        const formattedTime = time.toLocaleString();

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${formattedTime}</td>
            <td>${trade.symbol}</td>
            <td>${trade.side}</td>
            <td>${formatPrice(parseFloat(trade.price))}</td>
            <td>${formatQuantity(parseFloat(trade.qty))}</td>
            <td>${formatCurrency(parseFloat(trade.commission))} ${trade.commissionAsset}</td>
        `;

        tradesTable.appendChild(row);
    });
}

// Helper function to format currency values
function formatCurrency(value) {
    return value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Helper function to format percentage values
function formatPercentage(value) {
    return value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }) + '%';
}

// Helper function to format price values
function formatPrice(value) {
    return value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 8
    });
}

// Helper function to format quantity values
function formatQuantity(value) {
    return value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 8
    });
}
