# AI Thermal Public Agent Status Mirror

Read-only GitHub Pages mirror for the local AI Thermal Virtual Office.

Public URL:

```text
https://ak-1418.github.io/ai-thermal-status/
```

Purpose:

- Show four public-safe agent rooms in a 2D cartoon office scene.
- Use inline SVG avatars, desks, room labels, and tool identity.
- Show each agent name, role, status, current task short text, and last status update when available.
- Map public status to CSS animation classes.
- Refresh the display from `status_snapshot.json` every 120 seconds.
- Publish from the local PC every 2 minutes only when public state meaningfully changes.

Meaningful public changes include:

- `agents.status`
- `agents.visual_state`
- `agents.current_task_short`

Safety rules:

- GitHub Pages is read-only.
- Refresh Display only reloads `status_snapshot.json`.
- Current viewer time uses the browser clock and is not a heartbeat push.
- Last snapshot synced and Snapshot age are calculated from `generated_at_epoch_ms`.
- No remote control.
- No write-back to the local PC.
- No backend calls from GitHub Pages.
- No private repo folders, raw logs, customer data, optimizer outputs, credentials, internal prompts, or complete markdown note content are published.
- Reference images are private design references and are not published to the public status repo.

Public files are limited to:

- `.nojekyll`
- `README.md`
- `index.html`
- `status_snapshot.json`
