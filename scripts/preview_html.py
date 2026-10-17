#!/usr/bin/env python3
"""Write a static HTML list preview for the apps and games charts."""

import json
from pathlib import Path


def _items(entries, icons_by_id):
    items = []
    for entry in entries:
        icon = icons_by_id.get(entry["id"]) or {}
        items.append({
            "name": entry["name"],
            "developer": entry["developer"],
            "kind": entry["kind"],
            "cnRank": entry["cnRank"],
            "usRank": entry["usRank"],
            "icon": icon.get("path") or "",
            "url": entry["platforms"]["apple"]["url"],
        })
    return items


def render_preview(apps_document, games_document, icons_by_id):
    """Return one HTML page. The top switches between the two lists."""
    payload = {
        "apps": {
            "note": apps_document["chart"]["note"],
            "count": apps_document["selection"]["count"],
            "used": apps_document["chart"]["usedDepth"],
            "requested": apps_document["chart"]["requestedDepth"],
            "items": _items(apps_document["apps"], icons_by_id),
        },
        "games": {
            "note": games_document["chart"]["note"],
            "count": games_document["selection"]["count"],
            "used": games_document["chart"]["usedDepth"],
            "requested": games_document["chart"]["requestedDepth"],
            "items": _items(games_document["apps"], icons_by_id),
        },
    }
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    return """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>应用与游戏榜单</title>
<style>
  :root {
    color-scheme: light;
    --paper: #f3efe6;
    --ink: #1d1a16;
    --muted: #5e584f;
    --line: #ddd4c6;
    --accent: #0d6a4f;
    --accent-ink: #f4fbf7;
    --row: #fffdf8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font: 15px/1.45 "Iowan Old Style", "Palatino Linotype", Palatino, "Songti SC", "Noto Serif SC", serif;
  }
  header {
    position: sticky;
    top: 0;
    z-index: 2;
    background: rgba(243, 239, 230, 0.96);
    border-bottom: 1px solid var(--line);
    padding: 18px 20px 14px;
  }
  h1 { margin: 0 0 6px; font-size: 22px; font-weight: 650; letter-spacing: 0; }
  .switch { display: flex; gap: 8px; margin: 12px 0; }
  .switch button {
    appearance: none;
    border: 1px solid var(--ink);
    background: transparent;
    color: var(--ink);
    border-radius: 999px;
    padding: 6px 16px;
    font: inherit;
    cursor: pointer;
  }
  .switch button[aria-pressed="true"] { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
  .meta, .note { margin: 0; color: var(--muted); font-size: 13px; }
  .note { max-width: 78rem; }
  label.search { display: block; margin-top: 10px; color: var(--muted); font-size: 13px; }
  input[type="search"] {
    display: block;
    width: min(28rem, 100%);
    margin-top: 4px;
    border: 1px solid var(--line);
    background: var(--row);
    color: var(--ink);
    border-radius: 8px;
    padding: 8px 10px;
    font: inherit;
  }
  main { padding: 0 12px 32px; }
  table { width: 100%; border-collapse: collapse; background: var(--row); }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: middle; }
  th { font-size: 12px; color: var(--muted); font-weight: 650; }
  td.rank, th.rank { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; width: 5.5rem; }
  .icon {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    object-fit: cover;
    background: #e7e0d4;
    display: block;
  }
  .placeholder {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    background: #e7e0d4;
  }
  a { color: inherit; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .kind { color: var(--muted); font-size: 13px; }
  @media (max-width: 720px) {
    th.developer, td.developer { display: none; }
    .icon, .placeholder { width: 44px; height: 44px; }
  }
</style>
</head>
<body>
<header>
  <h1>应用与游戏榜单</h1>
  <div class="switch" role="tablist">
    <button type="button" id="show-apps" aria-pressed="true">应用</button>
    <button type="button" id="show-games" aria-pressed="false">游戏</button>
  </div>
  <p class="meta" id="summary"></p>
  <p class="note" id="note"></p>
  <label class="search">筛选名称或开发者
    <input id="filter" type="search" placeholder="输入名称">
  </label>
</header>
<main>
  <table>
    <thead>
      <tr>
        <th>图标</th>
        <th>名称</th>
        <th class="developer">开发者</th>
        <th>类型</th>
        <th class="rank">中区排名</th>
        <th class="rank">美区排名</th>
      </tr>
    </thead>
    <tbody id="rows"></tbody>
  </table>
</main>
<script id="chart-data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("chart-data").textContent);
const rows = document.getElementById("rows");
const summary = document.getElementById("summary");
const note = document.getElementById("note");
const filter = document.getElementById("filter");
const buttons = {
  apps: document.getElementById("show-apps"),
  games: document.getElementById("show-games")
};
let current = "apps";

function rankText(value) {
  return value == null ? "—" : String(value);
}

function kindText(value) {
  return value === "game" ? "游戏" : "应用";
}

function render() {
  const list = DATA[current];
  const query = filter.value.trim().toLowerCase();
  buttons.apps.setAttribute("aria-pressed", current === "apps" ? "true" : "false");
  buttons.games.setAttribute("aria-pressed", current === "games" ? "true" : "false");
  summary.textContent = list.count + " 款 · 中区实际收录前 " + list.used.cn + "（请求 " + list.requested + "）· 美区实际收录前 " + list.used.us + "（请求 " + list.requested + "）";
  note.textContent = list.note;
  rows.replaceChildren();
  for (const item of list.items) {
    const haystack = (item.name + " " + item.developer).toLowerCase();
    if (query && !haystack.includes(query)) continue;
    const tr = document.createElement("tr");
    const iconCell = document.createElement("td");
    if (item.icon) {
      const img = document.createElement("img");
      img.className = "icon";
      img.alt = "";
      img.src = item.icon;
      iconCell.append(img);
    } else {
      const blank = document.createElement("div");
      blank.className = "placeholder";
      iconCell.append(blank);
    }
    const nameCell = document.createElement("td");
    const link = document.createElement("a");
    link.href = item.url;
    link.textContent = item.name;
    nameCell.append(link);
    const developerCell = document.createElement("td");
    developerCell.className = "developer";
    developerCell.textContent = item.developer;
    const kindCell = document.createElement("td");
    kindCell.className = "kind";
    kindCell.textContent = kindText(item.kind);
    const cnCell = document.createElement("td");
    cnCell.className = "rank";
    cnCell.textContent = rankText(item.cnRank);
    const usCell = document.createElement("td");
    usCell.className = "rank";
    usCell.textContent = rankText(item.usRank);
    tr.append(iconCell, nameCell, developerCell, kindCell, cnCell, usCell);
    rows.append(tr);
  }
}

buttons.apps.addEventListener("click", function () { current = "apps"; render(); });
buttons.games.addEventListener("click", function () { current = "games"; render(); });
filter.addEventListener("input", render);
render();
</script>
</body>
</html>
""".replace("__DATA__", data)


def write_preview(root):
    root = Path(root)
    apps_document = json.loads((root / "metadata" / "apps.json").read_text(encoding="utf-8"))
    games_document = json.loads((root / "metadata" / "games.json").read_text(encoding="utf-8"))
    icons_path = root / "metadata" / "official-icons.json"
    icons = []
    if icons_path.is_file():
        icons = json.loads(icons_path.read_text(encoding="utf-8")).get("icons", [])
    html = render_preview(apps_document, games_document, {icon["id"]: icon for icon in icons})
    (root / "preview.html").write_text(html, encoding="utf-8")
    return root / "preview.html"
