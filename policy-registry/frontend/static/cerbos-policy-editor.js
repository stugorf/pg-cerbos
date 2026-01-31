const API = window.API_BASE;

// Default Cerbos resource policy template
const defaultResourcePolicy = `apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: "default"
  resource: "postgres"
  
  rules:
    - actions: ["query"]
      effect: EFFECT_ALLOW
      roles: ["admin", "full_access_user"]
    
    - actions: ["query"]
      effect: EFFECT_ALLOW
      roles: ["postgres_only_user"]
      condition:
        match:
          expr: |
            !R.attr.body.contains("iceberg.")
    
    - actions: ["query"]
      effect: EFFECT_DENY
      roles: ["restricted_user"]
      condition:
        match:
          expr: |
            R.attr.body.matches("(?i).*\\\\b(ssn|SSN|social_security|social_security_number|ssn_number)\\\\b.*")
`;

// Default Cerbos principal policy template
const defaultPrincipalPolicy = `apiVersion: api.cerbos.dev/v1
principalPolicy:
  version: "default"
  principal: "user"
  
  rules:
    - resource: "*"
      actions: ["*"]
      effect: EFFECT_ALLOW
`;

let policyEditor = null;
let currentPolicyPath = null;

// Check authentication on load
window.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('token');
    if (!token) {
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
    
    // Load policies on page load
    await loadPolicies();
    
    // Setup event listeners
    document.getElementById('refresh-policies').onclick = loadPolicies;
    document.getElementById('create-policy-btn').onclick = () => openPolicyModal(null);
    document.getElementById('save-policy-btn').onclick = savePolicy;
    document.getElementById('validate-policy-btn').onclick = validatePolicy;
});

// Initialize Monaco editor
require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' }});
require(['vs/editor/editor.main'], function() {
    policyEditor = monaco.editor.create(document.getElementById('policy-editor-container'), {
        value: defaultResourcePolicy,
        language: 'yaml',
        theme: 'vs',
        minimap: { enabled: true },
        automaticLayout: true
    });
});

// Load and display policies
async function loadPolicies() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = 'auth.html';
        return;
    }
    
    const policyOutput = document.getElementById('policy-output');
    policyOutput.innerHTML = '<div class="loading-message">Loading policies...</div>';
    
    try {
        const res = await fetch(`${API}/cerbos/policies`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!res.ok) {
            if (res.status === 401) {
                window.location.href = 'auth.html';
                return;
            }
            throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        }
        
        const data = await res.json();
        displayPolicies(data.policies || []);
        
    } catch (error) {
        policyOutput.innerHTML = `<div class="error-message">Error loading policies: ${error.message}</div>`;
    }
}

// Display policies in card layout
function displayPolicies(policies) {
    const policyOutput = document.getElementById('policy-output');
    
    if (!policies || policies.length === 0) {
        policyOutput.innerHTML = '<div class="policy-info">No Cerbos policies found. Click "Create New Policy" to add one.</div>';
        return;
    }
    
    let html = `<div class="policies-list">`;
    html += `<h4>Current Policies (${policies.length} total)</h4>`;
    
    policies.forEach(policy => {
        const policyName = policy.path.split('/').pop().replace('.yaml', '').replace('.yml', '');
        const policyType = policy.type || (policy.path.includes('principal') ? 'principal' : 'resource');
        const resourceKind = policy.path.includes('iceberg') ? 'iceberg' : 
                            policy.path.includes('postgres') ? 'postgres' : 'unknown';
        
        // Extract version from content if available
        let version = 'default';
        if (policy.content) {
            const versionMatch = policy.content.match(/version:\s*"([^"]+)"/);
            if (versionMatch) {
                version = versionMatch[1];
            }
        }
        
        html += `
            <div class="policy-item status-published" data-policy-path="${policy.path}">
                <div class="policy-header">
                    <h5>${policyName}</h5>
                    <span class="policy-status status-published">✅ PUBLISHED</span>
                </div>
                <div class="policy-details">
                    <p><strong>Path:</strong> <code>${policy.path}</code></p>
                    <p><strong>Type:</strong> ${policyType.charAt(0).toUpperCase() + policyType.slice(1)} Policy</p>
                    ${policyType === 'resource' ? `<p><strong>Resource:</strong> ${resourceKind}</p>` : ''}
                    <p><strong>Version:</strong> ${version}</p>
                </div>
                <div class="policy-actions">
                    <button class="btn btn-small btn-primary view-policy-btn" data-policy-path="${policy.path}">View Policy</button>
                    <button class="btn btn-small btn-secondary edit-policy-btn" data-policy-path="${policy.path}">Edit Policy</button>
                    <button class="btn btn-small btn-danger delete-policy-btn" data-policy-path="${policy.path}">Delete</button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    policyOutput.innerHTML = html;
    
    // Attach event listeners
    document.querySelectorAll('.view-policy-btn').forEach(btn => {
        btn.onclick = () => viewPolicy(btn.dataset.policyPath);
    });
    
    document.querySelectorAll('.edit-policy-btn').forEach(btn => {
        btn.onclick = () => editPolicy(btn.dataset.policyPath);
    });
    
    document.querySelectorAll('.delete-policy-btn').forEach(btn => {
        btn.onclick = () => deletePolicy(btn.dataset.policyPath);
    });
}

// View policy (read-only)
async function viewPolicy(path) {
    const token = localStorage.getItem('token');
    
    try {
        const res = await fetch(`${API}/cerbos/policies/${encodeURIComponent(path)}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        }
        
        const policy = await res.json();
        const policyName = path.split('/').pop();
        const policyType = policy.content.includes('resourcePolicy') ? 'Resource' : 
                          policy.content.includes('principalPolicy') ? 'Principal' : 'Unknown';
        
        const modalContent = document.getElementById('view-modal-content');
        modalContent.innerHTML = `
            <div class="policy-content-viewer">
                <div class="policy-info">
                    <p><strong>Path:</strong> <code>${policy.path}</code></p>
                    <p><strong>Type:</strong> ${policyType} Policy</p>
                </div>
                <div class="policy-code">
                    <h4>Policy Content:</h4>
                    <pre><code>${escapeHtml(policy.content)}</code></pre>
                </div>
            </div>
        `;
        
        document.getElementById('view-modal-title').textContent = `View Policy: ${policyName}`;
        document.getElementById('view-modal').style.display = 'block';
        
    } catch (error) {
        alert(`Error loading policy: ${error.message}`);
    }
}

// Edit policy
async function editPolicy(path) {
    const token = localStorage.getItem('token');
    
    try {
        const res = await fetch(`${API}/cerbos/policies/${encodeURIComponent(path)}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        }
        
        const policy = await res.json();
        currentPolicyPath = path;
        
        // Determine policy type and resource kind
        const isResourcePolicy = policy.content.includes('resourcePolicy');
        const isPrincipalPolicy = policy.content.includes('principalPolicy');
        let resourceKind = 'postgres';
        
        if (isResourcePolicy) {
            const resourceMatch = policy.content.match(/resource:\s*"([^"]+)"/);
            if (resourceMatch) {
                resourceKind = resourceMatch[1];
            }
        }
        
        // Set form values
        document.getElementById('modal-policy-path').value = path;
        document.getElementById('modal-policy-type').value = isPrincipalPolicy ? 'principal' : 'resource';
        document.getElementById('modal-resource-kind').value = resourceKind;
        
        // Set editor content
        if (policyEditor) {
            policyEditor.setValue(policy.content);
        }
        
        document.getElementById('modal-title').textContent = `Edit Policy: ${path.split('/').pop()}`;
        document.getElementById('policy-validation-output').innerHTML = '';
        document.getElementById('policy-modal').style.display = 'block';
        
    } catch (error) {
        alert(`Error loading policy: ${error.message}`);
    }
}

// Create new policy
function openPolicyModal(path) {
    currentPolicyPath = path || null;
    
    // Reset form
    document.getElementById('modal-policy-path').value = path || '';
    document.getElementById('modal-policy-type').value = 'resource';
    document.getElementById('modal-resource-kind').value = 'postgres';
    
    // Set default template
    if (policyEditor) {
        const policyType = document.getElementById('modal-policy-type').value;
        policyEditor.setValue(policyType === 'principal' ? defaultPrincipalPolicy : defaultResourcePolicy);
    }
    
    // Update resource kind when policy type changes
    document.getElementById('modal-policy-type').onchange = function() {
        if (policyEditor) {
            const template = this.value === 'principal' ? defaultPrincipalPolicy : defaultResourcePolicy;
            policyEditor.setValue(template);
        }
    };
    
    // Update resource kind in editor when changed
    document.getElementById('modal-resource-kind').onchange = function() {
        if (policyEditor && document.getElementById('modal-policy-type').value === 'resource') {
            const content = policyEditor.getValue();
            const updated = content.replace(/resource:\s*"[^"]+"/, `resource: "${this.value}"`);
            policyEditor.setValue(updated);
        }
    };
    
    document.getElementById('modal-title').textContent = path ? `Edit Policy: ${path.split('/').pop()}` : 'Create New Policy';
    document.getElementById('policy-validation-output').innerHTML = '';
    document.getElementById('policy-modal').style.display = 'block';
}

// Validate policy
async function validatePolicy() {
    if (!policyEditor) return;
    
    const content = policyEditor.getValue();
    const token = localStorage.getItem('token');
    const output = document.getElementById('policy-validation-output');
    
    output.innerHTML = '<div class="loading-message">Validating...</div>';
    
    try {
        const res = await fetch(`${API}/cerbos/policies/validate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ content })
        });
        
        const result = await res.json();
        
        if (result.valid) {
            output.innerHTML = '<div class="success-message">✅ Policy is valid!</div>';
        } else {
            output.innerHTML = `<div class="error-message">❌ Validation errors:<br>${result.errors.join('<br>')}</div>`;
        }
    } catch (error) {
        output.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
    }
}

// Save policy
async function savePolicy() {
    if (!policyEditor) return;
    
    const content = policyEditor.getValue();
    const path = document.getElementById('modal-policy-path').value;
    const token = localStorage.getItem('token');
    
    if (!path) {
        alert('Please enter a policy path');
        return;
    }
    
    // Validate first
    await validatePolicy();
    const validationOutput = document.getElementById('policy-validation-output').innerHTML;
    if (validationOutput.includes('❌')) {
        alert('Please fix validation errors before saving');
        return;
    }
    
    try {
        let res;
        if (currentPolicyPath) {
            // Update existing policy
            res = await fetch(`${API}/cerbos/policies/${encodeURIComponent(currentPolicyPath)}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ content })
            });
        } else {
            // Create new policy
            res = await fetch(`${API}/cerbos/policies`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ path, content })
            });
        }
        
        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`HTTP ${res.status}: ${errorText}`);
        }
        
        alert('Policy saved successfully! Cerbos will automatically reload policies.');
        closePolicyModal();
        await loadPolicies();
        
    } catch (error) {
        alert(`Error saving policy: ${error.message}`);
    }
}

// Delete policy
async function deletePolicy(path) {
    if (!confirm(`Are you sure you want to delete the policy "${path}"?`)) {
        return;
    }
    
    const token = localStorage.getItem('token');
    
    try {
        const res = await fetch(`${API}/cerbos/policies/${encodeURIComponent(path)}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${await res.text()}`);
        }
        
        alert('Policy deleted successfully!');
        await loadPolicies();
        
    } catch (error) {
        alert(`Error deleting policy: ${error.message}`);
    }
}

// Close modals
function closePolicyModal() {
    document.getElementById('policy-modal').style.display = 'none';
    currentPolicyPath = null;
}

function closeViewModal() {
    document.getElementById('view-modal').style.display = 'none';
}

// Utility function
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
