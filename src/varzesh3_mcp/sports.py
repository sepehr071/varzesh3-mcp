"""Varzesh3 tools: scores, matches, leagues and tables, teams, players, transfers, news, videos, search."""

from __future__ import annotations

import asyncio
import html
import re
from typing import Annotated, Any, Literal

from pydantic import Field

from .http import API, SEARCH, ApiError, fetch
from .registry import tool

STATUS = {0: "scheduled", 1: "scheduled", 2: "live", 4: "postponed", 5: "cancelled", 6: "incomplete", 7: "finished"}
TABLE = r"/(standing(/live)?|multi-standing)$"
FORM = {1: "W", 2: "L", 3: "D"}  # recentMatches.resultType
SPORT = {1: "football", 2: "futsal", 4: "basketball"}  # livescore league `sport` code
# A league of each sport; its view lists the sibling leagues of that sport.
SEED_LEAGUE = {"football": 6, "futsal": 27, "basketball": 32, "volleyball": 33, "handball": 4}
# Section names of /v1.0/contents/{Section} (the site's other-sports pages).
SECTIONS = (
    "Volleyball Basketball Wrestling Handball Tennis AutoRacing Squash Skiing Skate Sailing Badminton Bodybuilding "
    "WheelchairBasketball Basketball3 Boccia Boxing Bowling Baseball Billiards Paralympic Padel Taekwondo TableTennis "
    "Shooting Archery Jujutsu Judo Athletics Cycling Rowing Gymnastics Mountaineering Triathlon HorseRiding Chess "
    "Fencing Swim Diving CanoeSprint Karate Kabaddi Kurash Goalball Golf Motorcycling Surfing Hockey MixedMartialArts "
    "WaterPolo BeachVolleyball SittingVolleyball Esports"
).split()
CARD = {1: "yellow", 2: "second_yellow", 3: "red"}  # event cardType
PENALTY = {1: "scored", 2: "saved", 3: "missed"}  # event penaltyResult
EVENT = {1: "goal", 2: "card", 3: "penalty", 4: "substitution", 5: "var", 6: "shootout_penalty"}  # event eventType
TEAM_STAT = {  # /stats/teams boxes, by `type`
    1: "wins",
    2: "home wins",
    3: "away wins",
    4: "losses",
    5: "home losses",
    6: "away losses",
    7: "points per match",
    8: "home points per match",
    9: "away points per match",
    11: "clean sheets",
    12: "goals scored per match",
    13: "goals conceded per match",
    15: "shots on target",
    16: "saves per match",
    18: "red cards",
    19: "yellow cards",
    20: "average possession %",
    23: "corners",
    24: "youngest average age",
    25: "oldest average age",
    26: "comebacks",
}
TEAM_RANKING = {  # full team rankings: slug of /stats/teams/advanced/{slug} -> field of each team row
    "wins": "wins",
    "losses": "losses",
    "clean_sheets": "cleanSheets",
    "corners": "corners",
    "possession": "possession",
    "comebacks": "comebacks",
    "youngest": "averageAge",
    "oldest": "averageAge",
}
PLAYER_KEYS = {
    "appearances": "appearances",
    "goals": "goals",
    "assists": "assists",
    "clean_sheets": "cleanSheets",
    "yellow": "yellowCards",
    "red": "redCards",
    "penalties_scored": "turnedToGoalPenalties",
    "penalties_taken": "penalties",
    "minutes": "appearanceMinutes",
    "hat_tricks": "hatTricks",
    "fastest_goal_minute": "fastestGoalTime",
    "average_rating": "averageScores",
}
STATS = {
    "goals": "goals",
    "assists": "assists",
    "goals_and_assists": "goals-assists",
    "clean_sheets": "clean-sheets",
    "yellow_cards": "yellow-cards",
    "red_cards": "red-cards",
    "minutes": "appearance-minutes",
    "penalties": "penalties",
    "fastest_goals": "fastest-goals",
    "hat_tricks": "hattricks",
    "average_rating": "average-scores",
}

LeagueId = Annotated[
    int,
    Field(
        description="League id from v3_league, e.g. 6 (Iranian Pro League), 3 (Premier League).",
        ge=1,
    ),
]
Sport = Annotated[
    Literal["football", "futsal", "basketball", "volleyball", "handball"],
    Field(description="Ids are per sport."),
]
SeasonId = Annotated[int | None, Field(description="Season id from v3_league; default current.", ge=1)]
TeamId = Annotated[int, Field(description="Team id from v3_search or v3_standings, e.g. 6 (Perspolis).", ge=1)]
Take = Annotated[int, Field(description="Items to return.", ge=1, le=30)]
Skip = Annotated[int, Field(description="Items to skip.", ge=0, le=500)]


def _st(m: dict) -> str:
    return STATUS.get(m.get("status"), m.get("statusTitle") or str(m.get("status")))


def _score(g: dict | None) -> str | None:
    return f"{g['host']}-{g['guest']}" if g and g.get("host") is not None and g.get("guest") is not None else None


def _tid(team: dict | None) -> int | None:
    """Team id: list endpoints put a match id in `id`, so the link is the reliable source."""
    team = team or {}
    m = re.search(r"/team/(\d+)", team.get("link") or "")
    return int(m.group(1)) if m else (team.get("id") or None)


def _row(m: dict, date: str | None = None) -> dict:
    """One match line shared by every list tool."""
    h, g = m.get("host") or {}, m.get("guest") or {}
    league = m.get("league") or {}
    return {
        "id": m.get("id"),
        "date": date or m.get("date"),
        "time": m.get("time"),
        "status": _st(m),
        "minute": m.get("liveTime"),
        "home": h.get("name"),
        "home_id": _tid(h),
        "away": g.get("name"),
        "away_id": _tid(g),
        "score": _score(m.get("goals") or m.get("points") or m.get("matchPoints")),
        "penalties": _score(m.get("penalties")),
        "stage": m.get("title"),
        "league": league.get("name") or league.get("title"),
        "video_id": (m.get("video") or {}).get("id"),
        "sets": [s for i in range(1, 6) if (s := _score(m.get(f"setPoints{i}")))],
        "quarters": [s for i in range(1, 5) if (s := _score(m.get(f"quarterPoints{i}")))],
    }


def _text(s: str | None, cap: int = 6000) -> str:
    s = re.sub(r"</p>|<br\s*/?>", "\n", s or "", flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()[:cap]


def _news_item(n: dict) -> dict:
    return {
        "id": n.get("id"),
        "title": n.get("title"),
        "summary": n.get("shortDescription"),
        "published": n.get("persianPublishedOn"),
        "views": n.get("viewCountHumanReadable"),
        "comments": n.get("commentCount"),
    }


def _video_item(v: dict) -> dict:
    return {
        "id": v.get("id"),
        "title": v.get("title"),
        "duration": v.get("duration"),
        "views": v.get("viewCountHumanReadable"),
        "published": v.get("persianPublishedOn"),
        "url": f"https://video.varzesh3.com/video/{v.get('id')}",
    }


async def _league_view(league_id: int, sport: str = "football") -> dict:
    return await fetch(f"{API}/v2.0/{sport}/leagues/{league_id}")


def _sport_of(lg: dict) -> str | None:
    m = re.match(r"/(\w+)/", lg.get("link") or "")
    return m[1] if m and m[1] in SEED_LEAGUE else SPORT.get(lg.get("sport"))


def _tags(tags: list[dict]) -> list[dict]:
    out = []
    for t in tags:
        m = re.search(r"/(team|league|person|player)/(\d+)", t.get("link") or "")
        out.append({"name": t.get("title"), "kind": m.group(1) if m else None, "id": int(m.group(2)) if m else None})
    return out


def _player_row(p: dict, rank: int) -> dict:
    return {
        "rank": rank,
        "id": p.get("id"),
        "name": p.get("name"),
        "team": p.get("teamName"),
        "team_id": p.get("teamId"),
    } | {k: p[v] for k, v in PLAYER_KEYS.items() if p.get(v)}


def _tab_href(view: dict, pattern: str) -> str | None:
    for tab in view.get("tabs", []):
        for link in tab.get("_links") or []:
            if re.search(pattern, link.get("href", "")):
                return link["href"]
    return None


def _season_path(view: dict, pattern: str, season_id: int | None) -> str:
    """The league tab link matching `pattern`, moved to `season_id` when one is given."""
    href = _tab_href(view, pattern)
    if not href:
        raise ApiError(f"League {view.get('id')} has no such data for its current season.")
    return re.sub(r"/seasons/\d+", f"/seasons/{season_id}", href) if season_id else href


def _table(teams: list[dict]) -> list[dict]:
    return [
        {
            "rank": t.get("rank") or i,  # basketball rows have no rank field, they come in table order
            "team": t.get("name"),
            "team_id": t.get("id"),
            "played": t.get("played"),
            "won": t.get("wins"),
            "drawn": t.get("draws"),
            "lost": t.get("losses"),
            "gf": t.get("goalFor"),
            "ga": t.get("goalAgainst"),
            "gd": t.get("goalDifference"),
            "points": t.get("points"),
            "sets_won": t.get("setWins"),
            "sets_lost": t.get("setLosses"),
            "points_for": t.get("totalPointsScored"),
            "points_against": t.get("totalPointsConceded"),
            "form": "".join(FORM.get(r.get("resultType"), "?") for r in t.get("recentMatches") or []),
            "live": t.get("hasLiveMatch") or None,
        }
        for i, t in enumerate(teams, 1)
    ]


@tool("Scores of a day")
async def v3_scores(
    day: Annotated[int, Field(description="0 today, -1 yesterday, 1 tomorrow.", ge=-2, le=2)] = 0,
    sport: Annotated[
        Literal["all", "football", "futsal", "basketball", "volleyball", "handball"],
        Field(description="Sport filter."),
    ] = "all",
    league_id: Annotated[int | None, Field(description="Only this league (id from v3_league).", ge=1)] = None,
    team: Annotated[
        str | None,
        Field(
            description="Persian team-name text, e.g. پرسپولیس.",
            max_length=60,
        ),
    ] = None,
    live_only: Annotated[bool, Field(description="Only matches in play.")] = False,
    max_matches: Annotated[int, Field(description="Cap across all leagues.", ge=1, le=200)] = 60,
) -> dict:
    """Get the live scores, results and fixtures of one day across leagues.

    Every match has an id for v3_match. Filter by league_id or team to keep it short. Scores are "home-away";
    status: scheduled, live, finished, postponed, cancelled or incomplete (played, no final result yet).
    Basketball scores are points; volleyball rows carry sets, basketball quarters. day=0 switches to the new
    Jalali day some hours after midnight Tehran time.
    """
    data = await fetch(f"{API}/v2.0/livescore/{'today' if day == 0 else day}")
    leagues, left, total = [], max_matches, 0
    for lg in data:
        if sport != "all" and _sport_of(lg) != sport:
            continue
        if league_id and lg.get("id") != league_id:
            continue
        rows = []
        for d in lg.get("dates", []):
            for m in d.get("matches", []):
                if live_only and not m.get("isLive"):
                    continue
                if team and team not in (m.get("host") or {}).get("name", "") + "|" + (m.get("guest") or {}).get(
                    "name", ""
                ):
                    continue
                rows.append(_row(m, d.get("date")))
        total += len(rows)
        if rows and left > 0:
            leagues.append(
                {
                    "league_id": lg["id"],
                    "league": lg.get("title"),
                    "sport": _sport_of(lg),
                    "matches": rows[:left],
                }
            )
            left -= len(rows[:left])
    out: dict[str, Any] = {"day": day, "matches_found": total, "leagues": leagues}
    if total > max_matches:
        out["truncated"] = f"Showing {max_matches} of {total}; filter by league_id or team, or raise max_matches."
    return out


def _lineup(side: dict) -> dict:
    def p(x: dict) -> str:
        return f"{x.get('shirtNumber', '')} {x.get('name')}{' (c)' if x.get('isCaptain') else ''}{' *MOTM' if x.get('isManOfTheMatch') else ''}".strip()

    return {
        "formation": side.get("formation"),
        "coach": (side.get("coach") or {}).get("name"),
        "lines": [[p(x) for x in ln.get("players", [])] for ln in side.get("formationLines", [])],
        "bench": [p(x) for x in side.get("benchedPlayers", [])],
        "missing": [x.get("name") if isinstance(x, dict) else x for x in side.get("missingPlayers", [])],
    }


def _event(e: dict) -> dict:
    kind = EVENT.get(e.get("eventType"), "event")
    row: dict[str, Any] = {
        "minute": e.get("time") or None,
        "team": "home" if e.get("side") == 0 else "away",
        "type": kind,
    }
    if kind == "goal":
        row |= {
            "player": e.get("strickerName"),
            "player_id": e.get("strikerId"),
            "assist": e.get("assisterName"),
            "score": _score(e.get("matchResult")),
        }
        if e.get("goalType"):
            row["own_goal"] = True  # goalType != 0 draws the own-goal icon on the site
    elif kind == "card":
        row |= {
            "player": e.get("offendingPlayerName"),
            "player_id": e.get("offendingPlayerId"),
            "card": CARD.get(e.get("cardType")) or ("red" if "قرمز" in (e.get("description") or "") else "yellow"),
        }
    elif kind in ("penalty", "shootout_penalty"):
        row |= {
            "player": e.get("kickerName"),
            "player_id": e.get("kickerId"),
            "result": PENALTY.get(e.get("penaltyResult")),
            "score": _score(e.get("matchResult")),
        }
    elif kind == "substitution":
        row |= {"in": e.get("incomingPlayerName"), "out": e.get("outgoingPlayerName")}
        if not row["in"]:
            row["text"] = e.get("description")
    elif kind == "var":
        row |= {"player": e.get("playerName"), "decision": e.get("decisionTitle")}
    else:
        row["text"] = e.get("description")
    if e.get("videoId"):
        row["video_id"] = e["videoId"]
    return row


@tool("Match detail")
async def v3_match(
    match_id: Annotated[int, Field(description="Match id from v3_scores or a list tool.", ge=1)],
    sport: Annotated[
        Literal["football", "futsal", "basketball", "volleyball", "handball"],
        Field(description="Sport of the match."),
    ] = "football",
    prediction: Annotated[bool, Field(description="Football only: add the fans' poll (percent shares).")] = False,
) -> dict:
    """Get one match: score, status, goals, cards, penalties, substitutions, lineups, referee, stadium, summary video.

    Use it after v3_scores or a list tool gave a match id. Lineups appear only close to kick-off. No per-match
    possession or shot statistics. Basketball gives quarter points, volleyball set scores, plus both teams' last matches.
    """
    d = await fetch(f"{API}/v2.0/{sport}/matches/{match_id}")
    league = d.get("league") or {}
    out: dict[str, Any] = {
        "id": d.get("id"),
        "title": d.get("title"),
        "date": d.get("date"),
        "time": d.get("time"),
        "status": _st(d),
        "live": d.get("isLive"),
        "home": (d.get("host") or {}).get("name"),
        "home_id": (d.get("host") or {}).get("id"),
        "away": (d.get("guest") or {}).get("name"),
        "away_id": (d.get("guest") or {}).get("id"),
        "league": league.get("title"),
        "season": league.get("season"),
        "week": d.get("week"),
        "home_rank": d.get("hostRank"),
        "away_rank": d.get("guestRank"),
        "news": [{"id": n["id"], "title": n["title"]} for n in (d.get("news") or {}).get("items", [])[:5]],
    }
    video = d.get("video") or {}
    out["video"] = {"id": video["id"], "title": video.get("title")} if video.get("id") else None
    if sport in ("basketball", "volleyball", "handball"):
        out["score"] = _score(d.get("matchPoints") or d.get("goals"))
        out["quarters"] = [q for i in (1, 2, 3, 4) if (q := _score(d.get(f"quarterPoints{i}")))]
        out["sets"] = [q for i in range(1, 6) if (q := _score(d.get(f"setPoints{i}")))]
        rel = d.get("relatedMatchCollection") or {}
        out["home_recent"] = [_row(m) for m in rel.get("host", [])]
        out["away_recent"] = [_row(m) for m in rel.get("guest", [])]
        return out
    lineup = d.get("lineup") or {}
    out |= {
        "score": _score(d.get("goals")),
        "referee": d.get("referee"),
        "stadium": d.get("stadium"),
        "events": [_event(e) for e in d.get("events", [])],
        "home_lineup": _lineup(lineup["host"]) if lineup.get("host") else None,
        "away_lineup": _lineup(lineup["guest"]) if lineup.get("guest") else None,
        "home_next": _row_next(d.get("hostNextMatch")),
        "away_next": _row_next(d.get("guestNextMatch")),
    }
    if prediction and sport == "football":
        try:
            p = await fetch(f"{API}/api/prediction/{match_id}/varzesh3")
        except ApiError as e:
            if e.status != 404:
                raise
            out["prediction"] = "No prediction poll for this match."
        else:
            r = p.get("resultStats") or {}
            out["prediction"] = {
                "home_win_pct": r.get("host"),
                "draw_pct": r.get("drew"),
                "away_win_pct": r.get("guest"),
                "popular_scores": [
                    {"score": _score(x.get("goals")), "pct": x.get("percent")} for x in p.get("scoreStats", [])
                ],
            }
    return out


def _row_next(m: dict | None) -> str | None:
    if not m:
        return None
    return f"{m.get('id')}: {(m.get('host') or {}).get('name')} - {(m.get('guest') or {}).get('name')}, {m.get('date')} {m.get('time')}"


@tool("Leagues and seasons")
async def v3_league(
    league_id: Annotated[int | None, Field(description="Omit to list main leagues.", ge=1)] = None,
    sport: Sport = "football",
) -> dict:
    """List the football leagues with their ids, or get one league's current season id and past seasons with winners.

    Call it without league_id to find an id (Iranian Pro League 6, Premier League 3, La Liga 2, Serie A 4). Any
    league_id from v3_scores works too (55 Portuguese, 35 Turkish). Past seasons are football only. Other sports:
    sport="futsal" (league 27), "volleyball" (33), "basketball" (32; NBA 209) or "handball" (4).
    """
    if league_id is None:
        if sport != "football":
            view = await _league_view(SEED_LEAGUE[sport], sport)
            return {"sport": sport, "leagues": [{"id": x["id"], "name": x["title"]} for x in view.get("leagues", [])]}
        data = await fetch(f"{API}/v2.0/football/leagues")
        return {"leagues": [{"id": x["id"], "name": x["name"]} for x in data]}
    view = await _league_view(league_id, sport)
    try:
        archive = await fetch(f"{API}/v2.0/{sport}/leagues/{league_id}/archive")
    except ApiError as e:
        if e.status != 404:
            raise
        archive = {}  # only football has past-season lists
    m = re.search(r"/seasons/(\d+)", _tab_href(view, r"/seasons/\d+") or "")
    return {
        "id": view.get("id"),
        "name": view.get("name"),
        "current_season_id": int(m.group(1)) if m else None,
        "pages": [t.get("title") for t in view.get("tabs", [])],
        "updated": view.get("persianLastModified"),
        "seasons": [
            {
                "season_id": s.get("id"),
                "title": s.get("title"),
                "status": s.get("statusTitle"),
                "winner": (s.get("winner") or {}).get("title"),
            }
            for s in archive.get("seasons", [])[:15]
        ],
    }


@tool("League table")
async def v3_standings(
    league_id: LeagueId,
    season_id: SeasonId = None,
    stage: Annotated[
        Literal["table", "knockout"],
        Field(description="knockout = cup bracket."),
    ] = "table",
    sport: Sport = "football",
) -> dict:
    """Get a league table (rank, played, won, drawn, lost, goals, points, form), group tables or a cup bracket.

    Groups (World Cup) return one table per group; cups need stage="knockout". form is the last five results
    W/D/L, oldest first. Zones are in `zones`. Volleyball adds sets and points for/against.
    """
    view = await _league_view(league_id, sport)
    has_table = _tab_href(view, TABLE)
    if stage == "knockout" or not has_table:
        d = await fetch(_season_path(view, r"/playoffs$", season_id))
        out = {"league": view.get("name"), "rounds": [_tier(t) for t in d.get("tiers", [])]}
        if stage == "table":
            out["note"] = "This competition has no table, only a bracket."
        return out
    path = _season_path(view, TABLE, season_id)
    d = await fetch(path)
    out: dict[str, Any] = {"league": view.get("name"), "season_id": int(re.search(r"/seasons/(\d+)", path).group(1))}
    if "standings" in d:
        out["groups"] = [{"group": g.get("title"), "table": _table(g.get("teams", []))} for g in d["standings"]]
        zones = d.get("qualificationRules")
    else:
        out["table"] = _table(d.get("teams", []))
        zones = d.get("qualificationRules")
        out["notes"] = d.get("footnotes")
    out["zones"] = [z.get("title") for z in zones or []]
    return out


def _tier(t: dict) -> dict:
    ties = []
    for n in t.get("nodes", []):
        legs = [x for x in (n.get("firstMatch"), n.get("secondMatch")) if x]
        first = legs[0] if legs else {}
        ties.append(
            {
                "home": (first.get("host") or {}).get("name"),
                "away": (first.get("guest") or {}).get("name"),
                "legs": [
                    {"match_id": x.get("id"), "score": _score(x.get("goals")), "date": x.get("startOn")} for x in legs
                ],
                "winner_id": n.get("winnerId"),
            }
        )
    return {"round": t.get("title"), "ties": ties}


@tool("League fixtures and results")
async def v3_league_matches(
    league_id: LeagueId,
    which: Annotated[
        Literal["current", "upcoming", "results"],
        Field(description="current = rounds around today; results = played, newest last."),
    ] = "current",
    season_id: SeasonId = None,
    skip: Annotated[
        int,
        Field(
            description="Matches to skip: back in time for results, ahead for upcoming.",
            ge=0,
            le=500,
        ),
    ] = 0,
    sport: Sport = "football",
) -> dict:
    """Get a league's matches round by round: scores of played rounds and dates of coming ones.

    Start with which="current", then page with "upcoming" or "results" and skip=9 (about a round). Each match has an id for v3_match.
    """
    view = await _league_view(league_id, sport)
    path = _season_path(view, r"/matches$", season_id)
    if which != "current":
        path = path.removesuffix("/matches") + ("/fixtures" if which == "upcoming" else "/results")
    d = await fetch(path, {"skip": skip} if which != "current" else None)
    rounds = [
        {
            "round": r.get("round"),
            "days": [
                {"date": day.get("date") or None, "matches": [_row(m) for m in day.get("matches", [])]}
                for day in r.get("dates", [])
            ],
        }
        for r in d.get("items", [])
    ]
    return {"league": view.get("name"), "rounds": rounds, "has_more": d.get("hasMore"), "has_earlier": d.get("hasPrev")}


@tool("Top players of a league")
async def v3_top_players(
    league_id: LeagueId,
    stat: Annotated[
        Literal[tuple(STATS)],
        Field(description="goals = top scorers; clean_sheets = goalkeepers."),
    ] = "goals",
    season_id: SeasonId = None,
    limit: Annotated[int, Field(description="Best first.", ge=1, le=30)] = 10,
    sport: Annotated[Literal["football", "futsal"], Field(description="futsal: top scorers only.")] = "football",
) -> dict:
    """Get the best players of a football (or futsal) league by one statistic, e.g. top scorers or most assists.

    Each player has an id for v3_player, team and season counters (a missing counter is zero). For one team use v3_team_players.
    """
    view = await _league_view(league_id, sport)
    if sport == "futsal":
        d = await fetch(_season_path(view, r"/topscorers$", season_id))
        items = d[0].get("items", []) if d else []
        return {
            "league": view.get("name"),
            "stat": "goals",
            "players": [
                {"rank": i, "id": p.get("id"), "name": p.get("name"), "team": p.get("teamName"), "goals": p.get("stat")}
                for i, p in enumerate(items[:limit], 1)
            ],
        }
    path = _season_path(view, r"/stats/players/advanced$", season_id)
    d = await fetch(f"{path}/{STATS[stat]}")
    players = [_player_row(p, i) for i, p in enumerate(d.get("players", [])[:limit], 1)]
    return {"league": view.get("name"), "stat": stat, "players": players}


@tool("Team page")
async def v3_team(
    team_id: TeamId,
    squad: Annotated[bool, Field(description="Include the squad.")] = True,
    transfers: Annotated[bool, Field(description="Include transfers in and out.")] = False,
    sport: Annotated[Literal["football", "futsal"], Field(description="futsal: form only.")] = "football",
) -> dict:
    """Get a football team's page: name, followers, recent form, squad by position and optionally transfers.

    form is the last three results W/D/L, newest first, for all, home and away. For matches use v3_team_matches, for news v3_news(scope="team").
    """
    t = await fetch(f"{API}/v2.0/{sport}/teams/{team_id}")
    form = t.get("recentForm") or {}
    out: dict[str, Any] = {
        "id": t.get("id"),
        "name": t.get("name"),
        "followers": t.get("followerCount"),
        "form": {
            k: "".join(FORM.get(r.get("resultType"), "?") for r in form.get(k, [])) for k in ("all", "home", "away")
        },
    }
    if sport != "football":
        out["note"] = "Squad and transfers exist only for football teams."
        return out
    if squad:
        sq = await fetch(f"{API}/v2.0/football/teams/{team_id}/squad")
        out["squad"] = [
            {
                "role": g.get("role"),
                "players": [
                    f"{p.get('shirtNumber', '')} {p.get('name')} ({p.get('age')})".strip() for p in g.get("players", [])
                ],
            }
            for g in sq
        ]
    if transfers:
        tr = await fetch(f"{API}/v2.0/football/teams/{team_id}/transfers")

        def mv(x: dict) -> str:
            return f"{x.get('name')} ({x.get('transferTypeTitle')}, {(x.get('team') or {}).get('name')})"

        out["transfers_in"] = [mv(x) for x in tr.get("incomings", [])]
        out["transfers_out"] = [mv(x) for x in tr.get("outgoings", [])]
    return out


@tool("Team matches")
async def v3_team_matches(
    team_id: TeamId,
    which: Annotated[
        Literal["results", "upcoming"],
        Field(description="results are newest first."),
    ] = "results",
    limit: Annotated[int, Field(ge=1, le=24)] = 10,
    sport: Annotated[Literal["football", "futsal"], Field(description="Sport of the team.")] = "football",
) -> dict:
    """Get a football team's latest results or upcoming matches across all competitions.

    Each match has an id for v3_match.
    """
    d = await fetch(f"{API}/v2.0/{sport}/teams/{team_id}/{'results' if which == 'results' else 'fixtures'}")
    items = d.get("items", [])
    items = list(reversed(items))[:limit] if which == "results" else items[:limit]  # the site lists oldest first
    return {"team_id": team_id, "matches": [_row(m) for m in items]}


@tool("News")
async def v3_news(
    scope: Annotated[
        Literal["latest", "most_read", "most_commented", "team", "league", "player", "match", "section"],
        Field(description="team, league, player, match need `id`; section needs `section`."),
    ] = "latest",
    id: Annotated[
        int | None,
        Field(description="Id for scope team, league, player or match.", ge=1),
    ] = None,
    take: Take = 10,
    skip: Skip = 0,
    sport: Annotated[
        Literal["football", "futsal", "basketball", "volleyball", "handball"],
        Field(description="Sport of the id."),
    ] = "football",
    section: Annotated[
        str | None,
        Field(
            description="For scope=section: sport page such as Wrestling, Tennis, Boxing, Chess, Esports (about 50).",
            max_length=30,
        ),
    ] = None,
) -> dict:
    """Get Varzesh3 news headlines with a short summary: latest, most read, most commented, or about a team, league, player, match or sport.

    Call v3_article with a news id for the whole story. scope="section" returns ~60 newest news and videos mixed (type tells which).
    """
    if scope == "section":
        name = next((x for x in SECTIONS if x.lower() == (section or "").lower().replace(" ", "")), None)
        if not name:
            raise ApiError("scope=section needs section, one of: " + ", ".join(SECTIONS))
        items = (await fetch(f"{API}/v1.0/contents/{name}"))[skip : skip + take]
        return {
            "scope": scope,
            "section": name,
            "items": [
                {
                    "type": "video" if x.get("mediaType") == 2 else "news",
                    "id": x.get("id"),
                    "title": x.get("title"),
                    "published_utc": x.get("publishedOn"),
                }
                for x in items
            ],
        }
    paths = {
        "latest": "news/archive",
        "most_read": "news/archive/most-visited",
        "most_commented": "news/archive/most-commented",
    }
    if scope in ("team", "league", "player", "match"):
        if not id:
            raise ApiError(f"scope={scope} needs id (use v3_search or v3_league to find it).")
        path = f"{sport}/{scope}s/{id}/news"
    else:
        path = paths[scope]
    d = await fetch(f"{API}/v1.0/{path}", {"skip": skip, "take": take})
    return {"scope": scope, "news": [_news_item(n) for n in d.get("items", [])], "has_more": d.get("hasMore")}


@tool("News story")
async def v3_article(news_id: Annotated[int, Field(description="News id from v3_news or v3_search.", ge=1)]) -> dict:
    """Read one news story: title, publish time, full text (up to 6000 characters), tags and the match it is about."""
    d = await fetch(f"{API}/v1.0/news/{news_id}")
    return {
        "id": d.get("id"),
        "title": d.get("title"),
        "summary": d.get("shortDescription"),
        "published": d.get("persianPublishedOn"),
        "views": d.get("viewCountHumanReadable"),
        "comments": d.get("commentCount"),
        "match_id": d.get("matchId"),
        "tags": _tags(d.get("tags", [])),
        "text": _text(d.get("body")),
        "url": d.get("link"),
    }


@tool("Videos")
async def v3_videos(
    scope: Annotated[
        Literal["latest", "team", "league", "match", "player"],
        Field(description="team, league, match, player need `id`."),
    ] = "latest",
    id: Annotated[
        int | None,
        Field(description="Id for scope team, league, match or player.", ge=1),
    ] = None,
    take: Take = 10,
    skip: Skip = 0,
    sport: Annotated[
        Literal["football", "futsal", "basketball", "volleyball", "handball"],
        Field(description="Sport of the id."),
    ] = "football",
) -> dict:
    """Get Varzesh3 videos (goals, match summaries, interviews): latest, or about one team, league, match or player.

    Each video has a page url on video.varzesh3.com.
    """
    if scope == "latest":
        d = await fetch(f"{API}/v1.0/videos", {"skip": skip, "take": take})
        items = d.get("items", [])
    elif not id:
        raise ApiError(f"scope={scope} needs id.")
    elif scope == "match":
        tabs = await fetch(f"{API}/v1.0/{sport}/matches/{id}/videos/tabs")
        items = (tabs[0].get("items", []) if tabs else [])[skip : skip + take]
        d = {}
    else:
        d = await fetch(f"{API}/v1.0/{sport}/{scope}s/{id}/videos", {"skip": skip, "take": take})
        items = d.get("items", [])
    return {"scope": scope, "videos": [_video_item(v) for v in items], "has_more": d.get("hasMore")}


@tool("Search")
async def v3_search(
    query: Annotated[
        str,
        Field(
            description="Persian name or keyword, e.g. پرسپولیس.",
            min_length=1,
            max_length=80,
        ),
    ],
    limit: Annotated[int, Field(description="Per kind.", ge=1, le=10)] = 5,
) -> dict:
    """Search Varzesh3 for teams, people, leagues, news and videos by name; the way to turn a name into an id.

    Use it first when the user names a team or player: `entities` carry the ids. Persian only; English names usually find nothing.
    """
    d = await fetch(SEARCH, {"q": query})
    return {
        "entities": [
            {"kind": t.get("tagType"), "id": t.get("refId"), "name": t.get("title"), "sport": t.get("sport")}
            for t in d.get("tags", [])[:limit]
        ],
        "news": [_news_item(n) for n in d.get("news", [])[:limit]],
        "videos": [_video_item(v) for v in d.get("videos", [])[:limit]],
    }


@tool("Player profile")
async def v3_player(
    player_id: Annotated[
        int,
        Field(description="Player id from v3_top_players, v3_team_players, v3_match or v3_search.", ge=1),
    ],
    sport: Annotated[Literal["football", "futsal"], Field(description="Sport of the player.")] = "football",
) -> dict:
    """Get a player's profile (team, position, shirt number, age, country) with his latest news and videos.

    No career or season statistics here: use v3_team_players or v3_top_players.
    """
    p = await fetch(f"{API}/v2.0/{sport}/players/{player_id}")
    out: dict[str, Any] = {
        "id": p.get("id"),
        "name": p.get("name"),
        "team": (p.get("team") or {}).get("name"),
        "team_id": _tid(p.get("team")),
        "position": p.get("role"),
        "shirt_number": p.get("shirtNumber"),
        "age": p.get("age"),
        "country": p.get("country"),
        "career": p.get("career"),
    }
    try:
        g = await fetch(f"{API}/v2.0/{sport}/players/{player_id}/at-a-glance")
    except ApiError as e:
        if e.status != 404:
            raise
        g = {}
    out["news"] = [_news_item(n) for n in g.get("news", [])[:5]]
    out["videos"] = [_video_item(v) for v in g.get("videos", [])[:5]]
    out["tags"] = _tags(g.get("tags", []))
    return out


TEAM_PLAYER_STATS = {
    k: STATS[k]
    for k in ("goals", "assists", "goals_and_assists", "clean_sheets", "penalties", "yellow_cards", "red_cards")
} | {"average_rating": STATS["average_rating"]}


@tool("Players of a team")
async def v3_team_players(
    team_id: TeamId,
    stat: Annotated[
        Literal[tuple(TEAM_PLAYER_STATS)],
        Field(description="Statistic to rank by."),
    ] = "goals",
    league_id: Annotated[
        int | None, Field(description="Competition (league id); default the team's main league.", ge=1)
    ] = None,
    season_id: SeasonId = None,
) -> dict:
    """Get the season statistics of one football team's players: goals, assists, appearances, minutes, cards.

    Defaults to the current season of the team's main league; `competitions` lists others to pass as league_id.
    Players with zero in the chosen stat may be missing.
    """
    base = f"{API}/v2.0/football/teams/{team_id}/stats"
    comps = await fetch(f"{base}/leagues")
    if not comps:
        raise ApiError("This team has no statistics.")
    comp = next((c for c in comps if c["id"] == league_id), None) if league_id else comps[0]
    if not comp:
        raise ApiError("The team has no stats for that league; pick one of: " + ", ".join(str(c["id"]) for c in comps))
    seasons = await fetch(f"{base}/leagues/{comp['id']}/seasons")
    season = next((x for x in seasons if x["id"] == season_id), None) if season_id else seasons[0]
    if not season:
        raise ApiError("No such season; seasons: " + ", ".join(f"{x['id']} ({x['title']})" for x in seasons))
    d = await fetch(f"{base}/{TEAM_PLAYER_STATS[stat]}", {"seasonId": season["id"]})
    return {
        "team_id": team_id,
        "competition": comp["title"],
        "season": season["title"],
        "season_id": season["id"],
        "stat": stat,
        "players": [_player_row(p, i) for i, p in enumerate(d.get("players", []), 1)],
        "competitions": [{"league_id": c["id"], "name": c["title"]} for c in comps],
    }


@tool("Head to head")
async def v3_head_to_head(
    team_id: TeamId,
    opponent_id: TeamId,
    depth: Annotated[
        int,
        Field(description="Pages of 24 matches to scan (5 is about 4 seasons).", ge=1, le=10),
    ] = 5,
    limit: Annotated[int, Field(description="Newest first.", ge=1, le=30)] = 10,
) -> dict:
    """Get the past meetings of two football teams with a won/drawn/lost summary for team_id.

    No upstream head-to-head page: this scans the last depth*24 matches of team_id (all competitions) for the
    opponent; raise depth to look further back. Each meeting has an id for v3_match.
    """
    pages = await asyncio.gather(
        *(fetch(f"{API}/v2.0/football/teams/{team_id}/results", {"skip": i * 24}) for i in range(depth))
    )
    seen: dict[int, dict] = {}
    for pg in pages:
        for m in pg.get("items", []):
            seen[m["id"]] = m
    dates = [m.get("date") or "" for m in seen.values()]
    meetings = sorted(
        (m for m in seen.values() if opponent_id in (_tid(m.get("host")), _tid(m.get("guest")))),
        key=lambda m: (m.get("date") or "", m.get("time") or ""),
        reverse=True,
    )
    w = d = lo = gf = ga = 0
    for m in meetings:
        g = m.get("goals") or {}
        home = _tid(m.get("host")) == team_id
        mine, theirs = (g.get("host"), g.get("guest")) if home else (g.get("guest"), g.get("host"))
        if mine is None or theirs is None:
            continue
        gf, ga = gf + mine, ga + theirs
        w, d, lo = w + (mine > theirs), d + (mine == theirs), lo + (mine < theirs)
    return {
        "team_id": team_id,
        "opponent_id": opponent_id,
        "summary": {"played": w + d + lo, "won": w, "drawn": d, "lost": lo, "gf": gf, "ga": ga},
        "scanned": f"{len(seen)} matches of team {team_id}, {min(dates, default='?')} to {max(dates, default='?')}",
        "meetings": [_row(m) for m in meetings[:limit]],
    }


@tool("Transfers")
async def v3_transfers(
    market: Annotated[
        Literal["iran", "euro"], Field(description="iran = Iranian Pro League, euro = European clubs.")
    ] = "iran",
    team_id: Annotated[int | None, Field(description="Only this team.", ge=1)] = None,
    direction: Annotated[Literal["all", "in", "out"], Field(description="Arrivals or departures.")] = "all",
    loans: Annotated[
        Literal["all", "only", "exclude"], Field(description="only = loans, exclude = permanent only.")
    ] = "all",
    window_id: Annotated[int | None, Field(description="Id from `windows`; default latest.", ge=1)] = None,
    limit: Annotated[int, Field(description="Cap across all teams.", ge=1, le=300)] = 60,
) -> dict:
    """Get the football transfer list of a window, club by club: players signed and players who left.

    Filter by team_id to keep it short. `windows` lists earlier windows for window_id.
    """
    d = await fetch(f"{API}/v2.0/football/transfers/{market}" + (f"/{window_id}" if window_id else ""))
    teams, left, total = [], limit, 0
    for t in d.get("teams", []):
        if team_id and t.get("id") != team_id:
            continue
        row: dict[str, Any] = {"team": t.get("name"), "team_id": t.get("id")}
        for label in ("in", "out"):
            if direction not in ("all", label):
                continue
            moves = [
                {
                    "player": x.get("name"),
                    "id": x.get("id"),
                    "move": x.get("description"),
                    "loan": True if x.get("transferType") == 2 else None,
                }
                for x in t.get(label) or []
                if loans == "all" or (x.get("transferType") == 2) == (loans == "only")
            ]
            total += len(moves)
            row[label] = moves[: max(left, 0)]
            left -= len(row[label])
        if row.get("in") or row.get("out"):
            teams.append(row)
    out: dict[str, Any] = {
        "title": d.get("title"),
        "updated": d.get("lastModified"),
        "moves_found": total,
        "teams": teams,
        "windows": [{"window_id": a.get("id"), "title": a.get("title")} for a in d.get("archive", [])[:8]],
        "news": [{"id": n.get("id"), "title": n.get("title")} for n in d.get("news", [])[:5]],
    }
    if total > limit:
        out["truncated"] = f"Showing {limit} of {total} moves; filter by team_id, direction or loans, or raise limit."
    return out


@tool("TV schedule")
async def v3_tv_schedule(
    query: Annotated[
        str | None,
        Field(description="Persian text in name or competition.", max_length=60),
    ] = None,
    max_items: Annotated[int, Field(ge=1, le=100)] = 40,
) -> dict:
    """Get the live broadcast schedule (جدول پخش زنده) of sports matches for the next days, with start times and stream links.

    match_id (when linked to a football match) goes to v3_match.
    """
    d = await fetch(f"{API}/v1.0/live")
    days, left = [], max_items
    for day in d.get("conductors", []):
        rows = []
        for x in day.get("items", []):
            if query and query not in (x.get("title") or "") + "|" + (x.get("subtitle") or ""):
                continue
            m = re.search(r"/match/(\d+)", x.get("matchLink") or "")
            rows.append(
                {
                    "time": x.get("startTime"),
                    "competition": x.get("subtitle"),
                    "title": x.get("title"),
                    "match_id": int(m[1]) if m else None,
                    "stream": x.get("liveStreamSource"),
                }
            )
        if rows and left > 0:
            days.append({"date": day.get("date"), "broadcasts": rows[:left]})
            left -= len(rows[:left])
    return {"days": days}


@tool("League statistics")
async def v3_league_stats(
    league_id: LeagueId,
    ranking: Annotated[
        Literal[tuple(TEAM_RANKING)] | None,
        Field(description="Full team ranking instead of the top-3 boxes."),
    ] = None,
    season_id: SeasonId = None,
) -> dict:
    """Get a football league's season statistics: goals per match, cards per match, goal timing, streak notes and team rankings.

    Without ranking you get the top 3 teams in each category. For players use v3_top_players.
    """
    view = await _league_view(league_id)
    base = _season_path(view, r"/records$", season_id).removesuffix("/records")
    if ranking:
        d = await fetch(f"{base}/stats/teams/advanced/{'cleansheets' if ranking == 'clean_sheets' else ranking}")
        field = TEAM_RANKING[ranking]
        return {
            "league": view.get("name"),
            "ranking": ranking,
            "teams": [
                {
                    "rank": i,
                    "team": t.get("name"),
                    "team_id": t.get("id"),
                    "value": t.get(field),
                    "played": t.get("play"),
                }
                for i, t in enumerate(d.get("teams", []), 1)
            ],
        }
    side, boxes, records = await asyncio.gather(
        fetch(f"{base}/sidebar-stats"), fetch(f"{base}/stats/teams"), fetch(f"{base}/records")
    )
    return {
        "league": view.get("name"),
        "goals": side.get("goalCount"),
        "goals_per_match": side.get("goalPerMatch"),
        "minutes_per_goal": side.get("minutesPerGoal"),
        "yellow_cards_per_match": side.get("yellowCardPerMatch"),
        "red_cards_per_match": side.get("redCardPerMatch"),
        "goal_timing": [f"{x.get('label')}: {x.get('count')} ({x.get('percent')}%)" for x in side.get("goalStats", [])],
        "team_leaders": {
            TEAM_STAT.get(b.get("type"), b.get("title")): [
                f"{t.get('name')} {t.get('stat')}" for t in b.get("items", [])[:3]
            ]
            for b in boxes
        },
        "streaks": [r.get("message") for r in records],
    }
