# AI Thermal 公開代理人狀態鏡像

這是 Alan 本機 AI Thermal Virtual Office 的 GitHub Pages 唯讀監看頁。

公開網址：

```text
https://ak-1418.github.io/ai-thermal-status/
```

用途：

- 顯示四個公開安全的代理人房間。
- 用 2D cartoon office scene 呈現代理人狀態。
- 使用 inline SVG avatar、桌子、房間標籤與工具特徵。
- 顯示每位代理人的名稱、角色、狀態、目前任務摘要，以及可用的最後更新時間。
- 將公開狀態對應到 CSS 動畫。
- 頁面每 120 秒重新讀取 `status_snapshot.json`。
- 本機每 2 分鐘執行 publisher；只有公開狀態有 meaningful change 時才提交更新。

會觸發 meaningful public change 的欄位：

- `agents.status`
- `agents.visual_state`
- `agents.current_task_short`

安全規則：

- GitHub Pages 永遠是唯讀。
- 「刷新畫面」只會重新讀取 `status_snapshot.json`。
- 「目前瀏覽時間」使用瀏覽器時間，不代表 heartbeat push。
- 「最後快照同步」與「快照時間差」由 `generated_at_epoch_ms` 計算。
- 不做遠端控制。
- 不寫回本機。
- 不從 GitHub Pages 呼叫本機後端。
- 不發布 private repo 資料夾、raw logs、customer data、optimizer outputs、credentials、internal prompts 或完整 markdown note content。
- Reference image 只作為 private design reference，不發布到 public status repo。

Public repo 只允許包含：

- `.nojekyll`
- `README.md`
- `index.html`
- `status_snapshot.json`
