$(document).ready(function() {
    // Initialize date range picker
    $('#daterange').daterangepicker({
        startDate: moment().subtract(30, 'days'),
        endDate: moment(),
        opens: 'left',
        locale: {
            format: 'YYYY-MM-DD'
        }
    });

    // Load symbols
    loadSymbols();

    // Load previous backtests
    loadPreviousBacktests();

    // Handle form submission
    $('#backtestForm').on('submit', function(e) {
        e.preventDefault();
        runBacktest();
    });

    // Toggle symbol select based on multi-symbol checkbox
    $('#multiSymbol').on('change', function() {
        if ($(this).is(':checked')) {
            $('#symbol').prop('disabled', true);
        } else {
            $('#symbol').prop('disabled', false);
        }
    });
});

// Load trading symbols
function loadSymbols() {
    $.ajax({
        url: '/api/symbols',
        type: 'GET',
        success: function(response) {
            if (response.success) {
                const symbolSelect = $('#symbol');
                symbolSelect.empty();
                symbolSelect.append('<option value="" selected disabled>Select a symbol</option>');
                
                response.symbols.forEach(symbol => {
                    symbolSelect.append(`<option value="${symbol}">${symbol}</option>`);
                });
            } else {
                console.error('Failed to load symbols:', response.message);
            }
        },
        error: function(xhr, status, error) {
            console.error('Error loading symbols:', error);
        }
    });
}

// Load previous backtests
function loadPreviousBacktests() {
    $.ajax({
        url: '/api/backtest/results',
        type: 'GET',
        success: function(response) {
            const container = $('#previousBacktests');
            container.empty();
            
            if (response.success) {
                if (response.results.length === 0) {
                    container.html('<p class="text-center py-3">No previous backtests found</p>');
                    return;
                }
                
                response.results.forEach(result => {
                    let resultHtml = '';
                    
                    if (result.type === 'single') {
                        resultHtml = `
                            <div class="list-group-item list-group-item-action result-card" data-filename="${result.filename}">
                                <div class="d-flex w-100 justify-content-between">
                                    <h6 class="mb-1">${result.symbol}</h6>
                                    <small>${formatDate(result.timestamp)}</small>
                                </div>
                                <p class="mb-1">${result.start_date} to ${result.end_date}</p>
                                <small class="d-flex justify-content-between">
                                    <span>Initial: ${result.initial_balance} USDT</span>
                                    <span class="${result.total_profit_pct >= 0 ? 'text-success' : 'text-danger'}">
                                        ${result.total_profit_pct >= 0 ? '+' : ''}${result.total_profit_pct.toFixed(2)}%
                                    </span>
                                </small>
                            </div>
                        `;
                    } else {
                        resultHtml = `
                            <div class="list-group-item list-group-item-action result-card" data-filename="${result.filename}">
                                <div class="d-flex w-100 justify-content-between">
                                    <h6 class="mb-1">Multiple Symbols (${result.symbols.length})</h6>
                                    <small>${formatDate(result.timestamp)}</small>
                                </div>
                                <p class="mb-1">${result.start_date} to ${result.end_date}</p>
                                <small>Initial: ${result.initial_balance} USDT</small>
                            </div>
                        `;
                    }
                    
                    container.append(resultHtml);
                });
                
                // Add click event to result cards
                $('.result-card').on('click', function() {
                    const filename = $(this).data('filename');
                    loadBacktestResult(filename);
                });
            } else {
                container.html(`<p class="text-center py-3 text-danger">Error: ${response.message}</p>`);
            }
        },
        error: function(xhr, status, error) {
            $('#previousBacktests').html(`<p class="text-center py-3 text-danger">Error loading previous backtests</p>`);
            console.error('Error loading previous backtests:', error);
        }
    });
}

// Run backtest
function runBacktest() {
    // Show loading overlay
    $('#loadingOverlay').show();
    $('#loadingMessage').text('Running backtest...');
    
    // Get form data
    const symbol = $('#symbol').val();
    const dateRange = $('#daterange').val().split(' - ');
    const startDate = dateRange[0];
    const endDate = dateRange[1];
    const initialBalance = parseFloat($('#initialBalance').val());
    const multiSymbol = $('#multiSymbol').is(':checked');
    
    // Prepare request data
    const requestData = {
        symbol: symbol,
        start_date: startDate,
        end_date: endDate,
        initial_balance: initialBalance,
        multi: multiSymbol
    };
    
    // Send request
    $.ajax({
        url: '/api/backtest',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(requestData),
        success: function(response) {
            if (response.success) {
                $('#loadingMessage').text('Backtest running in background. This may take a few minutes...');
                
                // Poll for results every 5 seconds
                const pollInterval = setInterval(function() {
                    $.ajax({
                        url: '/api/backtest/results',
                        type: 'GET',
                        success: function(pollResponse) {
                            if (pollResponse.success && pollResponse.results.length > 0) {
                                // Check if the newest result matches our backtest
                                const newestResult = pollResponse.results[0];
                                
                                if (multiSymbol && newestResult.type === 'multi') {
                                    // Load the result
                                    loadBacktestResult(newestResult.filename);
                                    clearInterval(pollInterval);
                                    $('#loadingOverlay').hide();
                                } else if (!multiSymbol && newestResult.type === 'single' && newestResult.symbol === symbol) {
                                    // Load the result
                                    loadBacktestResult(newestResult.filename);
                                    clearInterval(pollInterval);
                                    $('#loadingOverlay').hide();
                                }
                            }
                        }
                    });
                }, 5000);
                
                // Stop polling after 5 minutes (300 seconds)
                setTimeout(function() {
                    clearInterval(pollInterval);
                    $('#loadingOverlay').hide();
                    alert('Backtest is taking longer than expected. Please check the results page later.');
                }, 300000);
            } else {
                $('#loadingOverlay').hide();
                alert('Error running backtest: ' + response.message);
            }
        },
        error: function(xhr, status, error) {
            $('#loadingOverlay').hide();
            alert('Error running backtest. Please try again.');
            console.error('Error running backtest:', error);
        }
    });
}

// Load backtest result
function loadBacktestResult(filename) {
    $('#loadingOverlay').show();
    $('#loadingMessage').text('Loading backtest result...');
    
    $.ajax({
        url: `/api/backtest/result/${filename}`,
        type: 'GET',
        success: function(response) {
            $('#loadingOverlay').hide();
            
            if (response.success) {
                displayBacktestResult(response.data, filename);
            } else {
                alert('Error loading backtest result: ' + response.message);
            }
        },
        error: function(xhr, status, error) {
            $('#loadingOverlay').hide();
            alert('Error loading backtest result. Please try again.');
            console.error('Error loading backtest result:', error);
        }
    });
}

// Display backtest result
function displayBacktestResult(data, filename) {
    // Hide no results message and show results content
    $('#noResults').hide();
    $('#resultsContent').show();
    
    // Check if it's a multi-symbol or single-symbol result
    if (data.comparison) {
        // Multi-symbol result
        $('#resultTitle').text(`Multiple Symbols Backtest (${data.symbols.join(', ')})`);
        $('#singleResults').hide();
        $('#multiResults').show();
        
        // Populate comparison table
        const comparisonBody = $('#comparisonTableBody');
        comparisonBody.empty();
        
        data.comparison.forEach(item => {
            comparisonBody.append(`
                <tr>
                    <td>${item.symbol}</td>
                    <td>${item.total_trades}</td>
                    <td>${(item.win_rate * 100).toFixed(2)}%</td>
                    <td>${item.profit_factor.toFixed(2)}</td>
                    <td>${item.total_profit.toFixed(2)} USDT</td>
                    <td class="${item.total_profit_pct >= 0 ? 'text-success' : 'text-danger'}">
                        ${item.total_profit_pct >= 0 ? '+' : ''}${item.total_profit_pct.toFixed(2)}%
                    </td>
                    <td>${item.max_drawdown_pct.toFixed(2)}%</td>
                    <td>${item.sharpe_ratio.toFixed(2)}</td>
                </tr>
            `);
        });
    } else {
        // Single-symbol result
        $('#resultTitle').text(`${data.symbol} Backtest Results`);
        $('#multiResults').hide();
        $('#singleResults').show();
        
        // Populate metrics
        $('#resultSymbol').text(data.symbol);
        $('#resultPeriod').text(`${data.start_date} to ${data.end_date}`);
        $('#resultInitialBalance').text(`${data.initial_balance.toFixed(2)} USDT`);
        $('#resultFinalBalance').text(`${data.final_balance.toFixed(2)} USDT`);
        $('#resultTotalProfit').text(`${data.total_profit.toFixed(2)} USDT (${data.total_profit_pct >= 0 ? '+' : ''}${data.total_profit_pct.toFixed(2)}%)`);
        $('#resultTotalTrades').text(`${data.total_trades} (${data.winning_trades} wins, ${data.losing_trades} losses)`);
        $('#resultWinRate').text(`${(data.win_rate * 100).toFixed(2)}%`);
        $('#resultProfitFactor').text(data.profit_factor.toFixed(2));
        $('#resultMaxDrawdown').text(`${data.max_drawdown.toFixed(2)} USDT (${(data.max_drawdown_pct * 100).toFixed(2)}%)`);
        $('#resultSharpeRatio').text(data.sharpe_ratio.toFixed(2));
        
        // Set images
        const timestamp = filename.split('_')[1] + '_' + filename.split('_')[2];
        $('#equityCurveImg').attr('src', `/backtest/images/${data.symbol}_${timestamp}_equity.png`);
        $('#drawdownImg').attr('src', `/backtest/images/${data.symbol}_${timestamp}_drawdown.png`);
        
        // Populate trades table
        const tradesBody = $('#tradesTableBody');
        tradesBody.empty();
        
        if (data.trades && data.trades.length > 0) {
            data.trades.forEach((trade, index) => {
                tradesBody.append(`
                    <tr>
                        <td>${index + 1}</td>
                        <td>${formatDateTime(trade.entry_time)}</td>
                        <td class="${trade.side === 'LONG' ? 'text-success' : 'text-danger'}">${trade.side}</td>
                        <td>${trade.entry_price.toFixed(2)}</td>
                        <td>${trade.exit_price.toFixed(2)}</td>
                        <td>${trade.position_size.toFixed(6)}</td>
                        <td class="${trade.pnl >= 0 ? 'text-success' : 'text-danger'}">
                            ${trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)} USDT
                        </td>
                        <td class="${trade.pnl_pct >= 0 ? 'text-success' : 'text-danger'}">
                            ${trade.pnl_pct >= 0 ? '+' : ''}${trade.pnl_pct.toFixed(2)}%
                        </td>
                    </tr>
                `);
            });
        } else {
            tradesBody.append('<tr><td colspan="8" class="text-center">No trades executed</td></tr>');
        }
    }
}

// Helper function to format date from timestamp
function formatDate(timestamp) {
    const date = new Date(timestamp.replace('_', 'T'));
    return date.toLocaleDateString();
}

// Helper function to format date and time
function formatDateTime(dateTimeStr) {
    const date = new Date(dateTimeStr);
    return date.toLocaleString();
}
