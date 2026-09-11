"""Relay Admin Dashboard HTML template and helpers."""

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EdgePort Relay Administration</title>
  <style>
    :root {
      --bg: #0b0f17;
      --card: #111827;
      --border: #1f293d;
      --text: #f8fafc;
      --muted: #94a3b8;
      --cyan: #38bdf8;
      --red: #f43f5e;
      --green: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      padding: 30px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    h1 { font-size: 20px; font-weight: 700; color: var(--text); }
    .badge {
      background: rgba(56, 189, 248, 0.15);
      color: var(--cyan);
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .metric-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }
    .metric-label { font-size: 12px; color: var(--muted); text-transform: uppercase; }
    .metric-value { font-size: 24px; font-weight: 700; margin-top: 6px; color: var(--cyan); }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--border); }
    th { background: #162032; font-size: 12px; text-transform: uppercase; color: var(--muted); }
    td { font-size: 13px; font-family: monospace; }
    .btn-disconnect {
      background: rgba(244, 63, 94, 0.15);
      color: var(--red);
      border: 1px solid var(--red);
      padding: 4px 10px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }
    .btn-disconnect:hover { background: var(--red); color: #fff; }
  </style>
</head>
<body>
  <div class="header">
    <h1>EdgePort Relay Server Administration</h1>
    <span class="badge" id="relay-domain">-</span>
  </div>

  <div class="grid">
    <div class="metric-card">
      <div class="metric-label">Active Tunnels</div>
      <div class="metric-value" id="count-tunnels">0</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Server Status</div>
      <div class="metric-value" style="color: var(--green);">Online</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Subdomain</th>
        <th>Client IP</th>
        <th>Basic Auth</th>
        <th>Connected At</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody id="tunnels-body">
      <tr>
        <td colspan="5" style="text-align: center; color: var(--muted);">Loading tunnels...</td>
      </tr>
    </tbody>
  </table>

  <script>
    async function loadStats() {
      try {
        const res = await fetch('/api/admin/tunnels');
        const data = await res.json();
        document.getElementById('count-tunnels').textContent = data.tunnels.length;
        document.getElementById('relay-domain').textContent = data.domain;

        const tbody = document.getElementById('tunnels-body');
        tbody.innerHTML = '';

        if (data.tunnels.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" ' +
            'style="text-align: center; color: var(--muted);">No active client tunnels.</td></tr>';
          return;
        }

        data.tunnels.forEach(t => {
          const row = document.createElement('tr');
          const dateStr = new Date(t.registered_at * 1000).toLocaleTimeString();
          row.innerHTML = `
            <td style="color: var(--cyan); font-weight: 600;">${t.subdomain}</td>
            <td>${t.client_ip}</td>
            <td>${t.has_basic_auth ? 'Enabled' : 'None'}</td>
            <td>${dateStr}</td>
            <td>
              <button class="btn-disconnect" onclick="disconnectTunnel('${t.subdomain}')">
                Disconnect
              </button>
            </td>
          `;
          tbody.appendChild(row);
        });
      } catch (e) {
        console.error(e);
      }
    }

    async function disconnectTunnel(sub) {
      if (!confirm(`Disconnect tunnel for '${sub}'?`)) return;
      await fetch(`/api/admin/tunnels/${sub}/disconnect`, { method: 'POST' });
      loadStats();
    }

    loadStats();
    setInterval(loadStats, 5000);
  </script>
</body>
</html>
"""


def render_admin_html() -> str:
    return ADMIN_HTML
