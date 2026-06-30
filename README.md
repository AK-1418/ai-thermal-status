# AI Thermal Public Status Monitor

Read-only GitHub Pages monitor for Alan's local Virtual Office.

Public URL:

```text
https://ak-1418.github.io/ai-thermal-status/
```

Safety rules:

- Local Virtual Office remains the live source of truth.
- GitHub Pages displays a sanitized snapshot only.
- Local PC publishes every 2 minutes when public state meaningfully changes.
- Display refreshes every 2 minutes.
- Current viewer time updates in the browser and does not require a new commit.
- Last snapshot synced shows the last published snapshot time.
- Snapshot age is calculated in the browser from `generated_at_epoch_ms`.
- Status is considered stale after 6 minutes.
- Refresh Display only reloads `status_snapshot.json`.
- No remote control.
- No write-back to the local PC.
- No local backend calls from GitHub Pages.
- No private repo folders, raw logs, customer data, optimizer outputs, credentials, or full Markdown bodies are published.

Public files are limited to:

- `.nojekyll`
- `README.md`
- `index.html`
- `status_snapshot.json`
