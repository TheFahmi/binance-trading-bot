// Chart JavaScript for Binance Trading Bot

// Global variables
let tradingViewWidget = null;
let currentSymbol = typeof initialSymbol !== 'undefined' ? initialSymbol : 'BTCUSDT';
let currentInterval = '60'; // Default to 1h
let positions = [];
let signals = [];
let positionMarkers = [];
let signalMarkers = [];
let chartContainer = null;
let positionTooltip = null;
let signalTooltip = null;

// Debug
console.log("Initial symbol set to:", currentSymbol);

// Initialize the chart page
document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const symbolSelector = document.getElementById('symbol-selector');
    const intervalSelector = document.getElementById('interval-selector');
    chartContainer = document.getElementById('tradingview-chart-container');

    // Create tooltip elements
    createTooltips();

    // Load available symbols
    loadAvailableSymbols();

    // Set up event listeners
    symbolSelector.addEventListener('change', function() {
        currentSymbol = this.value;
        updateChart();

        // Update URL with the new symbol for bookmarking/sharing
        const url = new URL(window.location);
        url.searchParams.set('symbol', currentSymbol);
        window.history.pushState({}, '', url);
    });

    intervalSelector.addEventListener('change', function() {
        currentInterval = this.value;
        updateChart();
    });

    // Initialize TradingView widget
    initTradingViewWidget();

    // Start periodic updates
    setInterval(updateBotStatus, 5000);
    setInterval(loadPositionsAndSignals, 10000);

    // Initial updates
    updateBotStatus();
});

// Create tooltip elements
function createTooltips() {
    // Create position tooltip
    positionTooltip = document.createElement('div');
    positionTooltip.className = 'position-tooltip';
    positionTooltip.style.display = 'none';
    document.body.appendChild(positionTooltip);

    // Create signal tooltip
    signalTooltip = document.createElement('div');
    signalTooltip.className = 'signal-tooltip';
    signalTooltip.style.display = 'none';
    document.body.appendChild(signalTooltip);
}

// Load available trading symbols
function loadAvailableSymbols() {
    // Get symbol from URL if available
    const urlParams = new URLSearchParams(window.location.search);
    const symbolParam = urlParams.get('symbol');
    if (symbolParam) {
        currentSymbol = symbolParam;
    }

    fetch('/api/symbols')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const symbolSelector = document.getElementById('symbol-selector');
                symbolSelector.innerHTML = '';

                data.symbols.forEach(symbol => {
                    const option = document.createElement('option');
                    option.value = symbol;
                    option.textContent = symbol;
                    symbolSelector.appendChild(option);
                });

                // Set current symbol
                symbolSelector.value = currentSymbol;

                // If the symbol from URL is not in the list, add it
                if (symbolParam && !data.symbols.includes(symbolParam)) {
                    const option = document.createElement('option');
                    option.value = symbolParam;
                    option.textContent = symbolParam;
                    symbolSelector.appendChild(option);
                    symbolSelector.value = symbolParam;
                }
            }
        })
        .catch(error => {
            console.error('Error loading symbols:', error);
        });
}

// Initialize TradingView widget
function initTradingViewWidget() {
    // Get symbol from URL if available
    const urlParams = new URLSearchParams(window.location.search);
    const symbolParam = urlParams.get('symbol');
    if (symbolParam) {
        currentSymbol = symbolParam;
    }

    console.log("Initializing TradingView widget with symbol:", currentSymbol);

    tradingViewWidget = new TradingView.widget({
        "autosize": true,
        "symbol": "BINANCE:" + currentSymbol,
        "interval": currentInterval,
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "container_id": "tradingview-chart-container",
        "studies": [
            "RSI@tv-basicstudies",
            "MACD@tv-basicstudies",
            "BB@tv-basicstudies"
        ]
    });

    // When the widget is ready, load positions and signals
    tradingViewWidget.onChartReady(function() {
        console.log("Chart is ready for symbol:", currentSymbol);
        loadPositionsAndSignals();
    });
}

// Update the chart with new symbol or interval
function updateChart() {
    console.log("Updating chart to symbol:", currentSymbol, "interval:", currentInterval);

    // Remove existing markers
    clearMarkers();

    // Update the TradingView widget
    if (tradingViewWidget) {
        // The TradingView widget sometimes doesn't update properly with just setSymbol
        // We'll recreate the widget to ensure it updates correctly

        // First, remove the existing widget
        const container = document.getElementById('tradingview-chart-container');
        container.innerHTML = '';

        // Create a new widget
        tradingViewWidget = new TradingView.widget({
            "autosize": true,
            "symbol": "BINANCE:" + currentSymbol,
            "interval": currentInterval,
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "toolbar_bg": "#f1f3f6",
            "enable_publishing": false,
            "hide_side_toolbar": false,
            "allow_symbol_change": true,
            "container_id": "tradingview-chart-container",
            "studies": [
                "RSI@tv-basicstudies",
                "MACD@tv-basicstudies",
                "BB@tv-basicstudies"
            ]
        });

        // When the widget is ready, load positions and signals
        tradingViewWidget.onChartReady(function() {
            console.log("New chart is ready for symbol:", currentSymbol);
            loadPositionsAndSignals();
        });
    } else {
        // If widget doesn't exist yet, just load the data
        loadPositionsAndSignals();
    }
}

// Load positions and signals data
function loadPositionsAndSignals() {
    console.log("Loading positions and signals for symbol:", currentSymbol);

    fetch(`/api/chart-data/${currentSymbol}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log("Received chart data for symbol:", data.symbol);

                // Update positions
                positions = data.positions;
                updatePositionsTable(positions);

                // Update signals
                signals = data.signals;
                updateSignalsTable(signals);

                // Update chart markers
                if (tradingViewWidget) {
                    // Wait for a moment to ensure the chart is ready
                    setTimeout(function() {
                        updateChartMarkers();
                    }, 500);
                }
            }
        })
        .catch(error => {
            console.error('Error loading chart data:', error);
        });
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
        const positionAmt = position.size;
        const entryPrice = position.entry_price;
        const markPrice = entryPrice; // Use entry price as mark price for now
        const pnl = position.pnl;
        const pnlPercent = (pnl / (positionAmt * entryPrice)) * 100;

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${currentSymbol}</td>
            <td>${position.side}</td>
            <td>${entryPrice.toFixed(2)}</td>
            <td>${markPrice.toFixed(2)}</td>
            <td>${positionAmt.toFixed(4)}</td>
            <td class="${pnl >= 0 ? 'positive-value' : 'negative-value'}">
                ${pnl.toFixed(2)} USDT (${pnlPercent.toFixed(2)}%)
            </td>
        `;

        positionsTable.appendChild(row);
    });
}

// Update signals table
function updateSignalsTable(signals) {
    const signalsTable = document.getElementById('signals-table');

    if (!signals || signals.length === 0) {
        signalsTable.innerHTML = '<tr><td colspan="7" class="text-center">No recent signals</td></tr>';
        return;
    }

    signalsTable.innerHTML = '';

    // Sort signals by timestamp (newest first)
    signals.sort((a, b) => b.timestamp - a.timestamp);

    signals.forEach(signal => {
        const time = new Date(signal.timestamp);
        const formattedTime = time.toLocaleString();
        const indicators = signal.indicators;

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${formattedTime}</td>
            <td>${currentSymbol}</td>
            <td class="signal-${signal.type.toLowerCase()}">${signal.type}</td>
            <td>${indicators.rsi.toFixed(2)}</td>
            <td>${indicators.macd_line.toFixed(4)}/${indicators.macd_signal.toFixed(4)}</td>
            <td>${indicators.ema_short.toFixed(2)}/${indicators.ema_long.toFixed(2)}</td>
            <td>${indicators.bb_percent_b ? indicators.bb_percent_b.toFixed(2) : 'N/A'}</td>
        `;

        signalsTable.appendChild(row);
    });
}

// Update chart markers for positions and signals
function updateChartMarkers() {
    // Clear existing markers
    clearMarkers();

    // Get chart dimensions
    const chartRect = chartContainer.getBoundingClientRect();

    // Wait for the chart to be fully loaded
    if (!tradingViewWidget || !tradingViewWidget.chart || !tradingViewWidget.chart()) {
        console.log("Chart not ready yet, waiting...");
        setTimeout(updateChartMarkers, 500);
        return;
    }

    try {
        // Add position markers
        positions.forEach(position => {
            addPositionMarker(position, chartRect);
        });

        // Add signal markers
        signals.forEach(signal => {
            addSignalMarker(signal, chartRect);
        });

        console.log(`Added ${positionMarkers.length} position markers and ${signalMarkers.length} signal markers`);
    } catch (error) {
        console.error("Error updating chart markers:", error);
    }
}

// Add a position marker to the chart
function addPositionMarker(position, chartRect) {
    try {
        const marker = document.createElement('div');
        marker.className = `position-marker ${position.side.toLowerCase()}`;

        // Position the marker on the right edge of the chart
        marker.style.left = `${chartRect.width - 20}px`;

        // Calculate vertical position based on entry price
        const priceRange = tradingViewWidget.chart().priceRange();
        if (!priceRange) {
            console.log("Price range not available");
            return;
        }

        // Check if the entry price is within the visible range
        if (position.entry_price < priceRange.from || position.entry_price > priceRange.to) {
            console.log(`Position entry price ${position.entry_price} is outside visible range [${priceRange.from}, ${priceRange.to}]`);
            return;
        }

        const priceScale = chartRect.height / (priceRange.to - priceRange.from);
        const yPosition = chartRect.height - ((position.entry_price - priceRange.from) * priceScale);

        // Ensure the marker is within the chart bounds
        if (yPosition < 0 || yPosition > chartRect.height) {
            console.log(`Position marker y-position ${yPosition} is outside chart bounds [0, ${chartRect.height}]`);
            return;
        }

        marker.style.top = `${yPosition}px`;

        // Add event listeners for tooltip
        marker.addEventListener('mouseenter', function(e) {
            showPositionTooltip(position, e);
        });

        marker.addEventListener('mouseleave', function() {
            hidePositionTooltip();
        });

        // Add marker to the chart container
        chartContainer.appendChild(marker);
        positionMarkers.push(marker);

    } catch (error) {
        console.error("Error adding position marker:", error);
    }
}

// Add a signal marker to the chart
function addSignalMarker(signal, chartRect) {
    try {
        const marker = document.createElement('div');
        marker.className = `signal-marker ${signal.type.toLowerCase()}`;

        // Calculate horizontal position based on timestamp
        const timeRange = tradingViewWidget.chart().timeRange();
        if (!timeRange) {
            console.log("Time range not available");
            return;
        }

        // Check if the signal timestamp is within the visible range
        if (signal.timestamp < timeRange.from || signal.timestamp > timeRange.to) {
            console.log(`Signal timestamp ${signal.timestamp} is outside visible range [${timeRange.from}, ${timeRange.to}]`);
            return;
        }

        const timeScale = chartRect.width / (timeRange.to - timeRange.from);
        const xPosition = (signal.timestamp - timeRange.from) * timeScale;

        // Ensure the marker is within the chart bounds
        if (xPosition < 0 || xPosition > chartRect.width) {
            console.log(`Signal marker x-position ${xPosition} is outside chart bounds [0, ${chartRect.width}]`);
            return;
        }

        marker.style.left = `${xPosition}px`;

        // Calculate vertical position based on price
        const priceRange = tradingViewWidget.chart().priceRange();
        if (!priceRange) {
            console.log("Price range not available");
            return;
        }

        // Check if the signal price is within the visible range
        if (signal.price < priceRange.from || signal.price > priceRange.to) {
            console.log(`Signal price ${signal.price} is outside visible range [${priceRange.from}, ${priceRange.to}]`);
            return;
        }

        const priceScale = chartRect.height / (priceRange.to - priceRange.from);
        const yPosition = chartRect.height - ((signal.price - priceRange.from) * priceScale);

        // Ensure the marker is within the chart bounds
        if (yPosition < 0 || yPosition > chartRect.height) {
            console.log(`Signal marker y-position ${yPosition} is outside chart bounds [0, ${chartRect.height}]`);
            return;
        }

        marker.style.top = `${yPosition}px`;

        // Add event listeners for tooltip
        marker.addEventListener('mouseenter', function(e) {
            showSignalTooltip(signal, e);
        });

        marker.addEventListener('mouseleave', function() {
            hideSignalTooltip();
        });

        // Add marker to the chart container
        chartContainer.appendChild(marker);
        signalMarkers.push(marker);

    } catch (error) {
        console.error("Error adding signal marker:", error);
    }
}

// Show position tooltip
function showPositionTooltip(position, event) {
    const side = position.side;
    const entryPrice = position.entry_price;
    const size = position.size;
    const pnl = position.pnl;

    positionTooltip.innerHTML = `
        <div><strong>${side} Position</strong></div>
        <div>Entry: ${entryPrice.toFixed(2)}</div>
        <div>Size: ${size.toFixed(4)}</div>
        <div>PnL: ${pnl.toFixed(2)} USDT</div>
    `;

    positionTooltip.style.left = `${event.pageX + 10}px`;
    positionTooltip.style.top = `${event.pageY + 10}px`;
    positionTooltip.style.display = 'block';
}

// Hide position tooltip
function hidePositionTooltip() {
    positionTooltip.style.display = 'none';
}

// Show signal tooltip
function showSignalTooltip(signal, event) {
    const type = signal.type;
    const price = signal.price;
    const time = new Date(signal.timestamp).toLocaleString();
    const indicators = signal.indicators;

    signalTooltip.innerHTML = `
        <div><strong>${type} Signal</strong></div>
        <div>Price: ${price.toFixed(2)}</div>
        <div>Time: ${time}</div>
        <div>RSI: ${indicators.rsi.toFixed(2)}</div>
        <div>MACD: ${indicators.macd_line.toFixed(4)}/${indicators.macd_signal.toFixed(4)}</div>
    `;

    signalTooltip.style.left = `${event.pageX + 10}px`;
    signalTooltip.style.top = `${event.pageY + 10}px`;
    signalTooltip.style.display = 'block';
}

// Hide signal tooltip
function hideSignalTooltip() {
    signalTooltip.style.display = 'none';
}

// Clear all markers from the chart
function clearMarkers() {
    // Remove position markers
    positionMarkers.forEach(marker => {
        if (marker.parentNode) {
            marker.parentNode.removeChild(marker);
        }
    });
    positionMarkers = [];

    // Remove signal markers
    signalMarkers.forEach(marker => {
        if (marker.parentNode) {
            marker.parentNode.removeChild(marker);
        }
    });
    signalMarkers = [];
}

// Update bot status
function updateBotStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            const botStatusIndicator = document.getElementById('bot-status-indicator');

            if (data.is_running) {
                botStatusIndicator.innerHTML = '<i class="bi bi-circle-fill text-success me-1"></i><span>Running</span>';
                botStatusIndicator.classList.remove('status-stopped');
                botStatusIndicator.classList.add('status-running');
            } else {
                botStatusIndicator.innerHTML = '<i class="bi bi-circle-fill text-danger me-1"></i><span>Stopped</span>';
                botStatusIndicator.classList.remove('status-running');
                botStatusIndicator.classList.add('status-stopped');
            }
        })
        .catch(error => {
            console.error('Error updating bot status:', error);
        });
}
