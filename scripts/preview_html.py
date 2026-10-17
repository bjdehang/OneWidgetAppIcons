#!/usr/bin/env python3
"""Write a static HTML list preview for the apps and games charts."""

import json
from pathlib import Path


def _items(entries, icons_by_id):
    items = []
    for entry in entries:
        icon = icons_by_id.get(entry["id"]) or {}
        items.append({
            "id": entry["id"],
            "name": entry["name"],
            "developer": entry["developer"],
            "kind": entry["kind"],
            "cnRank": entry["cnRank"],
            "usRank": entry["usRank"],
            "icon": icon.get("path") or "",
            "url": entry["platforms"]["apple"]["url"],
        })
    return items


def _html_text(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def style_buttons(styles):
    """One button per registered style. Original is selected on first load."""
    default = "original" if any(style["id"] == "original" for style in styles) else styles[0]["id"]
    buttons = []
    for style in styles:
        pressed = "true" if style["id"] == default else "false"
        buttons.append(
            f'<button type="button" id="style-{_html_text(style["id"])}" '
            f'data-style="{_html_text(style["id"])}" aria-pressed="{pressed}">'
            f'{_html_text(style["name"])}</button>'
        )
    return "\n    ".join(buttons), default


def render_preview(apps_document, games_document, icons_by_id, styles=None, styled_icons=None):
    """Return one HTML page. The top switches list and icon style."""
    if not styles:
        styles = [{"id": "original", "name": "Standard (原版)"}]
    buttons, default_style = style_buttons(styles)
    payload = {
        "defaultStyle": default_style,
        "styledIcons": styled_icons or {},
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
  .switch { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
  .switch-label { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
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
  <div class="switch" role="tablist" aria-label="榜单">
    <button type="button" id="show-apps" aria-pressed="true">应用</button>
    <button type="button" id="show-games" aria-pressed="false">游戏</button>
  </div>
  <p class="switch-label">图标风格</p>
  <div class="switch" id="style-switch" role="tablist" aria-label="图标风格">
    __STYLE_BUTTONS__
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
let currentStyle = DATA.defaultStyle;

function iconFor(item) {
  if (currentStyle === "original") return item.icon || "";
  const table = DATA.styledIcons[currentStyle] || {};
  return table[item.id] || "";
}

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
  document.querySelectorAll("#style-switch button").forEach(function (button) {
    button.setAttribute("aria-pressed", button.getAttribute("data-style") === currentStyle ? "true" : "false");
  });
  let published = 0;
  for (const item of list.items) {
    if (iconFor(item)) published += 1;
  }
  summary.textContent = list.count + " 款 · 中区实际收录前 " + list.used.cn + "（请求 " + list.requested + "）· 美区实际收录前 " + list.used.us + "（请求 " + list.requested + "）";
  if (published === 0) summary.textContent += " · 此风格尚未发布图标";
  note.textContent = list.note;
  rows.replaceChildren();
  for (const item of list.items) {
    const haystack = (item.name + " " + item.developer).toLowerCase();
    if (query && !haystack.includes(query)) continue;
    const tr = document.createElement("tr");
    const iconCell = document.createElement("td");
    const iconPath = iconFor(item);
    if (iconPath) {
      const img = document.createElement("img");
      img.className = "icon";
      img.alt = "";
      img.src = iconPath;
      img.addEventListener("error", function () {
        const blank = document.createElement("div");
        blank.className = "placeholder";
        img.replaceWith(blank);
      });
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
document.querySelectorAll("#style-switch button").forEach(function (button) {
  button.addEventListener("click", function () {
    currentStyle = button.getAttribute("data-style");
    render();
  });
});
filter.addEventListener("input", render);
render();
</script>
</body>
</html>
""".replace("__DATA__", data).replace("__STYLE_BUTTONS__", buttons)


def _styled_icons(root, styles):
    """Published drawings from assets.json, keyed by style id then unified id."""
    path = root / "metadata" / "assets.json"
    assets = []
    if path.is_file():
        assets = json.loads(path.read_text(encoding="utf-8")).get("assets", [])
    allowed = {style["id"] for style in styles if style["id"] != "original"}
    found = {style_id: {} for style_id in allowed}
    for asset in assets:
        style_id = asset.get("styleId")
        app_id = asset.get("appId")
        icon_path = asset.get("path")
        if style_id in found and app_id and icon_path:
            found[style_id][app_id] = icon_path
    return found


def write_preview(root):
    root = Path(root)
    apps_document = json.loads((root / "metadata" / "apps.json").read_text(encoding="utf-8"))
    games_document = json.loads((root / "metadata" / "games.json").read_text(encoding="utf-8"))
    styles_path = root / "metadata" / "styles.json"
    styles = None
    if styles_path.is_file():
        styles = json.loads(styles_path.read_text(encoding="utf-8")).get("styles")
    icons_path = root / "metadata" / "official-icons.json"
    icons = []
    if icons_path.is_file():
        icons = json.loads(icons_path.read_text(encoding="utf-8")).get("icons", [])
    html = render_preview(
        apps_document,
        games_document,
        {icon["id"]: icon for icon in icons},
        styles=styles,
        styled_icons=_styled_icons(root, styles or []),
    )
    (root / "preview.html").write_text(html, encoding="utf-8")
    return root / "preview.html"
