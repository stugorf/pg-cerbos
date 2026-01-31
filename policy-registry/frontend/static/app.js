const API = window.API_BASE;

require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' }});
require(['vs/editor/editor.main'], function() {
  const defaultRego = `package envoy.authz

default allow = {"allowed": false, "headers": {}}

# Example override: allow analysts to query postgres
allow = {"allowed": true, "headers": {"x-authz":"opa-ui"}} {
  input.attributes.request.http.method == "POST"
  startswith(input.parsed_path, ["v1","statement"])
  lower(input.attributes.request.http.headers["x-role"]) == "analyst_eu"
}`;

  const editor = monaco.editor.create(document.getElementById('editor'), {
    value: defaultRego, language: 'rego', theme: 'vs'
  });

  document.getElementById('refresh').onclick = async () => {
    const res = await fetch(`${API}/policies`);
    const js = await res.json();
    document.getElementById('out').textContent = JSON.stringify(js, null, 2);
  };

  document.getElementById('publish').onclick = async () => {
    const name = document.getElementById('name').value || 'ui_policy';
    const path = document.getElementById('path').value || 'envoy/authz.rego';
    const rego_text = editor.getValue();
    const create = await fetch(`${API}/policies`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, path, rego_text, published: false})
    });
    const {id} = await create.json();
    await fetch(`${API}/policies/${id}/publish`, {method: 'POST'});
    document.getElementById('out').textContent = `Published policy ${id}. OPA will pull within ~5s.`;
  };
});