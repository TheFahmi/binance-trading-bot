// Dashboard JavaScript for Binance Trading Bot

// Bot settings
const botSettings = {
    mode: 'signal',
    symbols: ['BTCUSDT']
};

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded');

    // Get button elements
    const startButton = document.getElementById('start-bot-btn');
    const stopButton = document.getElementById('stop-bot-btn');
    const saveSettingsButton = document.getElementById('save-settings-btn');
    const symbolsSelect = document.getElementById('symbols-select');
    const tradingModeSelect = document.getElementById('trading-mode-select');

    // Log button elements to verify they're found
    console.log('Start button:', startButton);
    console.log('Stop button:', stopButton);
    console.log('Save settings button:', saveSettingsButton);
    console.log('Symbols select:', symbolsSelect);

    // Add click event listeners directly to the buttons
    if (startButton) {
        startButton.onclick = function() {
            console.log('Start button clicked');
            startBot();
            return false; // Prevent default action
        };
    } else {
        console.error('Start button not found!');
    }

    if (stopButton) {
        stopButton.onclick = function() {
            console.log('Stop button clicked');
            stopBot();
            return false; // Prevent default action
        };
    } else {
        console.error('Stop button not found!');
    }

    // Add save settings button event listener
    if (saveSettingsButton) {
        saveSettingsButton.onclick = function() {
            console.log('Save settings button clicked');
            saveSettings();
            return false; // Prevent default action
        };
    } else {
        console.error('Save settings button not found!');
    }

    // Load available trading symbols
    loadSymbols();

    // Initial status update
    updateStatus();

    // Set interval for periodic updates
    setInterval(updateStatus, 5000);
});

// Start the bot
function startBot() {
    console.log('Starting bot with settings:', botSettings);

    // Disable start button and enable stop button
    document.getElementById('start-bot-btn').disabled = true;
    document.getElementById('stop-bot-btn').disabled = false;

    // Update status indicator immediately
    document.getElementById('bot-status-indicator').innerHTML =
        '<i class="bi bi-circle-fill text-success me-1"></i><span>Running</span>';

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
    .then(response => response.json())
    .then(data => {
        console.log('Start response:', data);

        if (data.success) {
            // Update status indicator
            document.getElementById('bot-status-indicator').innerHTML =
                '<i class="bi bi-circle-fill text-success me-1"></i><span>Running</span>';

            // Show success message
            alert(data.message);

            // Update dashboard
            updateStatus();
        } else {
            // Re-enable start button and disable stop button
            document.getElementById('start-bot-btn').disabled = false;
            document.getElementById('stop-bot-btn').disabled = true;

            // Show error message
            alert('Error starting bot: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error starting bot:', error);

        // Re-enable start button and disable stop button
        document.getElementById('start-bot-btn').disabled = false;
        document.getElementById('stop-bot-btn').disabled = true;

        // Show error message
        alert('Error starting bot: ' + error.message);
    });
}

// Stop the bot
function stopBot() {
    console.log('Stopping bot...');

    // Disable stop button and enable start button
    document.getElementById('stop-bot-btn').disabled = true;
    document.getElementById('start-bot-btn').disabled = false;

    // Send stop request to the server
    fetch('/api/stop', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
    })
    .then(response => response.json())
    .then(data => {
        console.log('Stop response:', data);

        if (data.success) {
            // Update status indicator
            document.getElementById('bot-status-indicator').innerHTML =
                '<i class="bi bi-circle-fill text-danger me-1"></i><span>Stopped</span>';

            // Show success message
            alert(data.message);

            // Update dashboard
            updateStatus();
        } else {
            // Re-enable stop button and disable start button
            document.getElementById('stop-bot-btn').disabled = false;
            document.getElementById('start-bot-btn').disabled = true;

            // Show error message
            alert('Error stopping bot: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error stopping bot:', error);

        // Re-enable stop button and disable start button
        document.getElementById('stop-bot-btn').disabled = false;
        document.getElementById('start-bot-btn').disabled = true;

        // Show error message
        alert('Error stopping bot: ' + error.message);
    });
}

// Update bot status
function updateStatus() {
    console.log('Updating status...');

    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            console.log('Status data:', data);

            // Update bot status indicator
            const statusIndicator = document.getElementById('bot-status-indicator');
            const startButton = document.getElementById('start-bot-btn');
            const stopButton = document.getElementById('stop-bot-btn');

            if (data.is_running) {
                // Bot is running
                statusIndicator.innerHTML = '<i class="bi bi-circle-fill text-success me-1"></i><span>Running</span>';
                startButton.disabled = true;
                stopButton.disabled = false;
            } else {
                // Bot is stopped
                statusIndicator.innerHTML = '<i class="bi bi-circle-fill text-danger me-1"></i><span>Stopped</span>';
                startButton.disabled = false;
                stopButton.disabled = true;
            }

            // Update account info
            if (data.account_info) {
                document.getElementById('total-balance').textContent =
                    formatNumber(data.account_info.total_wallet_balance || 0) + ' USDT';
                document.getElementById('available-balance').textContent =
                    formatNumber(data.account_info.available_balance || 0) + ' USDT';

                const unrealizedPnl = data.account_info.total_unrealized_profit || 0;
                document.getElementById('unrealized-pnl').textContent =
                    formatNumber(unrealizedPnl) + ' USDT';
            }

            // Update PnL
            if (data.pnl) {
                document.getElementById('daily-pnl').textContent =
                    formatNumber(data.pnl.daily || 0) + '%';
            }

            // Update bot info
            document.getElementById('trading-mode').textContent =
                data.is_running ? (data.mode === 'grid' ? 'Grid Trading' : 'Signal Trading') : 'Not Running';
            document.getElementById('running-since').textContent =
                data.start_time || '-';

            // Update positions count
            document.getElementById('active-positions-count').textContent =
                data.positions ? data.positions.length : 0;
        })
        .catch(error => {
            console.error('Error updating status:', error);
        });
}

// Format number with 2 decimal places
function formatNumber(value) {
    return parseFloat(value).toFixed(2);
}

// Load available trading symbols
function loadSymbols() {
    console.log('Loading available trading symbols...');

    // Get the symbols select element
    const symbolsSelect = document.getElementById('symbols-select');

    if (!symbolsSelect) {
        console.error('Symbols select element not found!');
        return;
    }

    // Clear existing options
    symbolsSelect.innerHTML = '';

    // Add a loading option
    const loadingOption = document.createElement('option');
    loadingOption.textContent = 'Loading symbols...';
    loadingOption.disabled = true;
    loadingOption.selected = true;
    symbolsSelect.appendChild(loadingOption);

    // Fetch available symbols from the API
    fetch('/api/symbols')
        .then(response => {
            console.log('Symbols response status:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('Symbols data:', data);

            // Clear the loading option
            symbolsSelect.innerHTML = '';

            if (data.success && data.symbols && data.symbols.length > 0) {
                // Add each symbol as an option
                data.symbols.forEach(symbol => {
                    const option = document.createElement('option');
                    option.value = symbol;
                    option.textContent = symbol;

                    // Select the option if it's in the current botSettings.symbols
                    if (botSettings.symbols.includes(symbol)) {
                        option.selected = true;
                    }

                    symbolsSelect.appendChild(option);
                });

                console.log(`Loaded ${data.symbols.length} symbols`);
            } else {
                // Add a default option if no symbols were returned
                const defaultOption = document.createElement('option');
                defaultOption.value = 'BTCUSDT';
                defaultOption.textContent = 'BTCUSDT';
                defaultOption.selected = true;
                symbolsSelect.appendChild(defaultOption);

                console.warn('No symbols returned from API, using default');
            }
        })
        .catch(error => {
            console.error('Error loading symbols:', error);

            // Clear the loading option
            symbolsSelect.innerHTML = '';

            // Add a default option if there was an error
            const defaultOption = document.createElement('option');
            defaultOption.value = 'BTCUSDT';
            defaultOption.textContent = 'BTCUSDT';
            defaultOption.selected = true;
            symbolsSelect.appendChild(defaultOption);
        });
}

// Save bot settings
function saveSettings() {
    console.log('Saving bot settings...');

    // Get the trading mode select element
    const tradingModeSelect = document.getElementById('trading-mode-select');

    // Get the symbols select element
    const symbolsSelect = document.getElementById('symbols-select');

    if (!tradingModeSelect || !symbolsSelect) {
        console.error('Trading mode or symbols select element not found!');
        alert('Error: Could not find settings elements');
        return;
    }

    // Update bot settings
    botSettings.mode = tradingModeSelect.value;

    // Get selected symbols
    botSettings.symbols = Array.from(symbolsSelect.selectedOptions).map(option => option.value);

    // If no symbols are selected, use default
    if (botSettings.symbols.length === 0) {
        botSettings.symbols = ['BTCUSDT'];
    }

    console.log('Updated bot settings:', botSettings);

    // Close the modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
    if (modal) {
        modal.hide();
    }

    // Show confirmation
    alert(`Settings saved!\nTrading Mode: ${botSettings.mode}\nSymbols: ${botSettings.symbols.join(', ')}`);
}
