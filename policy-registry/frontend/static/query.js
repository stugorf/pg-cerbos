const API = window.API_BASE;

// Check authentication on load
window.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('token');
    if (!token) {
        // Redirect to auth page
        window.location.href = 'auth.html';
        return;
    }
    
    // Get user info
    try {
        const res = await fetch(`${API}/users/me`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (res.ok) {
            const user = await res.json();
            document.getElementById('user-info').textContent = `Logged in as: ${user.email}`;
        }
    } catch (error) {
        console.error('Error fetching user info:', error);
    }
});

// Execute query
document.getElementById('execute-query').onclick = async () => {
    const queryInput = document.getElementById('query-input');
    const query = queryInput.value.trim();
    
    if (!query) {
        showStatus('Please enter a SQL query', 'error');
        return;
    }
    
    const statusDiv = document.getElementById('query-status');
    const resultsTable = document.getElementById('results-table');
    
    // Clear previous results
    resultsTable.innerHTML = '';
    showStatus('Executing query...', 'info');
    
    const token = localStorage.getItem('token');
    if (!token) {
        showStatus('Not authenticated. Please log in.', 'error');
        window.location.href = 'auth.html';
        return;
    }
    
    try {
        const res = await fetch(`${API}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                query: query,
                catalog: query.toLowerCase().includes('iceberg') ? 'iceberg' : 'postgres',
                schema: 'public'
            })
        });
        
        if (!res.ok) {
            const errorData = await res.json();
            showStatus(`Error: ${errorData.detail || res.statusText}`, 'error');
            return;
        }
        
        const result = await res.json();
        
        if (result.success) {
            showStatus(`Query executed successfully. Query ID: ${result.query_id}`, 'success');
            
            // Display results in table
            if (result.data && result.columns) {
                displayResults(result.data, result.columns);
            } else {
                showStatus('Query executed but no data returned', 'info');
            }
        } else {
            showStatus(`Query failed: ${result.error || 'Unknown error'}`, 'error');
        }
        
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
        console.error('Query execution error:', error);
    }
};

// Clear query
document.getElementById('clear-query').onclick = () => {
    document.getElementById('query-input').value = '';
    document.getElementById('results-table').innerHTML = '';
    document.getElementById('query-status').textContent = '';
};

// Display results in table
function displayResults(data, columns) {
    const table = document.getElementById('results-table');
    table.innerHTML = '';
    
    // Create header row
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col.name || col;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Create body
    const tbody = document.createElement('tbody');
    data.forEach(row => {
        const tr = document.createElement('tr');
        row.forEach(cell => {
            const td = document.createElement('td');
            td.textContent = cell !== null && cell !== undefined ? String(cell) : '';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    
    // Add some basic styling
    table.style.width = '100%';
    table.style.borderCollapse = 'collapse';
    table.style.marginTop = '20px';
    
    // Style header
    const headers = table.querySelectorAll('th');
    headers.forEach(th => {
        th.style.border = '1px solid #ddd';
        th.style.padding = '8px';
        th.style.backgroundColor = '#f2f2f2';
        th.style.textAlign = 'left';
    });
    
    // Style cells
    const cells = table.querySelectorAll('td');
    cells.forEach(td => {
        td.style.border = '1px solid #ddd';
        td.style.padding = '8px';
    });
}

// Show status message
function showStatus(message, type) {
    const statusDiv = document.getElementById('query-status');
    statusDiv.textContent = message;
    statusDiv.className = `status-${type}`;
    
    // Add some basic styling
    statusDiv.style.padding = '10px';
    statusDiv.style.margin = '10px 0';
    statusDiv.style.borderRadius = '4px';
    
    if (type === 'error') {
        statusDiv.style.backgroundColor = '#ffebee';
        statusDiv.style.color = '#c62828';
    } else if (type === 'success') {
        statusDiv.style.backgroundColor = '#e8f5e9';
        statusDiv.style.color = '#2e7d32';
    } else {
        statusDiv.style.backgroundColor = '#e3f2fd';
        statusDiv.style.color = '#1565c0';
    }
}

// Allow Enter+Ctrl/Cmd to execute query
document.getElementById('query-input').addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        document.getElementById('execute-query').click();
    }
});
