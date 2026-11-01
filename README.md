<!-- mcp-name: io.github.sepehr071/varzesh3-mcp -->

<div align="center">

# varzesh3-mcp: Varzesh3 (ورزش سه) Iranian sports MCP server for AI agents

**varzesh3-mcp is an unofficial, read-only MCP server that gives AI agents the data of Varzesh3 (varzesh3.com), the biggest Iranian sports site.**<br>
Its 18 tools read live scores, match details with goals, cards and lineups, league tables, fixtures and results, top scorers,<br>
player profiles and team statistics, head-to-head, transfers, the TV schedule, news stories and videos, in football, with futsal,<br>
volleyball, basketball and handball leagues and news for other sports. No API key or account is needed.<br>
It works in Claude, Cursor, Copilot and any other MCP client.

[![PyPI](https://img.shields.io/pypi/v/varzesh3-mcp?color=2563eb)](https://pypi.org/project/varzesh3-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/varzesh3-mcp/blob/main/LICENSE)

[For AI agents](#for-ai-agents) · [Quick start](#quick-start) · [What it can do](#what-it-can-do) · [Tools](#tools) · [FAQ](#faq) · [فارسی](#فارسی)

</div>

---

## For AI agents

- **What:** unofficial MCP server (model context protocol) for varzesh3.com: scores of a day across leagues, one match (events, lineups, referee, stadium, summary video), league tables (also groups and cup brackets), round-by-round fixtures and results, top scorers and other player rankings, team pages (form, squad, transfers), a team's results and next matches, news (latest, most read, by team or league), news story text, videos and search.
- **Install:** `uvx varzesh3-mcp` or `claude mcp add varzesh3 -- uvx varzesh3-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none, no API key or account. Optional `VARZESH3_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored.
- **Access:** read-only. It cannot log in, comment, vote or follow, so no confirmation is needed before calling any tool.
- **Tools:** 18, all prefixed `v3_`. Typical sequences: `v3_search` (a name) -> `v3_team` / `v3_team_matches` / `v3_news`; `v3_scores` -> `v3_match`; `v3_league` -> `v3_standings` / `v3_top_players`; `v3_head_to_head`; `v3_team_players` -> `v3_player`; `v3_transfers`.
- **Use when:** the user asks for today's or yesterday's scores, a team's last results or next match, the Iranian Pro League (or any big league) table, top scorers, who plays for a team, a transfer list, or the latest sports news in Persian.
- **Do not use when:** the user wants per-match possession or shot statistics (Varzesh3 has none; team season averages are in `v3_league_stats`), betting odds, or player career statistics.
- **Output:** compact JSON. Dates are Persian (Jalali) as the site shows them, times are Tehran time, scores are "home-away". Names and news are Persian.
- **Machine-readable:** [`server.json`](https://github.com/sepehr071/varzesh3-mcp/blob/main/server.json).

## What it can do

- **Scores of a day** (yesterday, today, tomorrow, plus two days either side) for all leagues, football, futsal and NBA, filtered by league, team or live only
- **Match detail**: goals with scorers and assists, cards, substitutions, lineups by formation line, bench, coaches, referee, stadium and the summary video
- **League tables** with form, group tables (World Cup, Asian cups) and knockout brackets (Hazfi Cup), for the current or a past season
- **Fixtures and results** round by round, and a **team's** last results or upcoming matches
- **Player rankings**: top scorers, assists, clean sheets, yellow and red cards, minutes, hat tricks, average rating
- **Team page**: recent form, squad by position with numbers and ages, transfers in and out
- **News, stories and videos**: latest, most read, by team or league, the full story text, goal and summary videos
- **Search** a Persian name to get the team id the other tools need
- **Read-only by design**: no login, no posting

Example prompts:

- "What is the result of Perspolis today?"
- "Show the Persian Gulf Pro League table."
- "Top 5 scorers of the Premier League."
- "Who played for Esteghlal in the last match, and who scored?"
- <span dir="rtl">جدول لیگ برتر ایران چطوره؟</span>
- <span dir="rtl">آخرین اخبار استقلال را بگو.</span>

## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). No API key or account.

```bash
claude mcp add varzesh3 -- uvx varzesh3-mcp
```

Claude Desktop, Cursor, Windsurf and Gemini CLI use the same block in their MCP config:

```json
{
  "mcpServers": {
    "varzesh3": { "command": "uvx", "args": ["varzesh3-mcp"] }
  }
}
```

VS Code (`.vscode/mcp.json`): `{"servers": {"varzesh3": {"type": "stdio", "command": "uvx", "args": ["varzesh3-mcp"]}}}`.
Codex CLI: `codex mcp add varzesh3 -- uvx varzesh3-mcp`. Anything else: `pip install varzesh3-mcp` and run `varzesh3-mcp`.

## Tools

Team ids come from `v3_search` (or any table), league ids from `v3_league`, match ids from `v3_scores`, `v3_league_matches` and `v3_team_matches`.

| Tool | What it does |
|---|---|
| `v3_scores` | Get the live scores, results and fixtures of one day across leagues, as the Varzesh3 live score page lists them |
| `v3_match` | Get one match: score, status, goals, cards, penalties, substitutions, lineups, referee, stadium, summary video and next matches |
| `v3_league` | List the football leagues with their ids, or get one league's current season id and past seasons with winners |
| `v3_standings` | Get the table of a football league (rank, played, won, drawn, lost, goals, points, recent form), group tables or a cup bracket |
| `v3_league_matches` | Get a football league's matches round by round: scores of played rounds and dates of coming ones |
| `v3_top_players` | Get the best players of a football league by one statistic, e.g. top scorers or most assists |
| `v3_team` | Get a football team's page: name, followers, recent form, squad by position and optionally transfers |
| `v3_team_matches` | Get a football team's latest results or its upcoming matches across all competitions |
| `v3_news` | Get Varzesh3 news headlines with a short summary: latest, most read, most commented, or about a team, league, player, match or sport |
| `v3_article` | Read one news story: title, publish time, full text, tags and the match it is about |
| `v3_videos` | Get Varzesh3 videos (goals, match summaries, interviews): latest, or about one team, league, match or player |
| `v3_league_stats` | Get a football league's season statistics: goals per match, cards per match, goal timing, streak notes and team rankings |
| `v3_team_players` | Get the season statistics of one football team's players: goals, assists, appearances, minutes, cards |
| `v3_player` | Get a player's profile (team, position, shirt number, age, country) with his latest news and videos |
| `v3_head_to_head` | Get the past meetings of two football teams with a won/drawn/lost summary |
| `v3_transfers` | Get the football transfer list of a window, club by club: players signed and players who left |
| `v3_tv_schedule` | Get the live broadcast schedule of sports matches for the next days, with start times and stream links |
| `v3_search` | Search Varzesh3 for teams, people, leagues, news and videos by name; the way to turn a name into an id |

All 18 tools are annotated `readOnlyHint: true`.

## How it works

```text
  AI agent  ──MCP over stdio──▶  varzesh3-mcp (your machine)  ──HTTPS──▶  web-api.varzesh3.com, search-api.varzesh3.com
```

The server calls the same public JSON endpoints varzesh3.com's pages use. Requests present a Chrome TLS and header profile
(through `curl_cffi`), run at most 4 at a time and are cached for 30 seconds. System proxy settings are ignored on purpose;
set `VARZESH3_MCP_PROXY` if your network needs one.

## FAQ

**Does it need an account or key?** No.

**Why do I get HTTP 5xx?** Varzesh3's CDN sometimes refuses a network; set `VARZESH3_MCP_PROXY=http://host:port` to route through another exit.

**Are there match statistics (possession, shots)?** No, the site does not publish them.

**Is it official?** No. It is unaffiliated with Varzesh3, reads only what the public site shows, and is meant for personal and research use. Respect the site's terms.

## فارسی

<div dir="rtl">

**varzesh3-mcp** یک سرور MCP غیررسمی و فقط‌خواندنی برای ورزش سه (varzesh3.com) است. با آن دستیار هوش مصنوعی می‌تواند نتایج زنده، جزئیات بازی (گل‌ها، کارت‌ها، ترکیب)، جدول لیگ‌ها، برنامه و نتایج، آمار بازیکنان، صفحه تیم‌ها، اخبار و ویدیوها را بخواند. نیازی به کلید API یا حساب کاربری نیست.

نصب: `claude mcp add varzesh3 -- uvx varzesh3-mcp`

</div>

---

Made by Sepehr Radmard (سپهر رادمرد): [github.com/sepehr071](https://github.com/sepehr071) · [linkedin.com/in/sepehr-radmard](https://linkedin.com/in/sepehr-radmard). MIT License.
