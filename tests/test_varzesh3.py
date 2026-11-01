import pytest
from conftest import fixture

from varzesh3_mcp import http

pytestmark = pytest.mark.anyio

S6 = "/v2.0/football/leagues/6/seasons/903038"
TOOLS = {
    "v3_scores",
    "v3_match",
    "v3_league",
    "v3_standings",
    "v3_league_matches",
    "v3_top_players",
    "v3_team",
    "v3_team_matches",
    "v3_news",
    "v3_article",
    "v3_videos",
    "v3_search",
    "v3_player",
    "v3_team_players",
    "v3_head_to_head",
    "v3_transfers",
    "v3_tv_schedule",
    "v3_league_stats",
}


async def test_all_tools_are_read_only_and_described(client):
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        assert t.annotations.read_only_hint is True, t.name
        assert t.title and t.description.splitlines()[0].endswith("."), t.name
        assert "title" not in str(t.input_schema.get("properties", {}).values()), t.name


async def test_scores_all_and_filters(client, api):
    api["/v2.0/livescore/today"] = fixture("livescore_today.json")
    r = (await client.call_tool("v3_scores", {})).structured_content
    assert [lg["league_id"] for lg in r["leagues"]] == [6, 2, 209] and r["matches_found"] == 18
    first = r["leagues"][0]["matches"][0]
    assert first["home"] and first["score"] and first["status"] in {"finished", "live", "scheduled", "cancelled"}
    assert r["leagues"][2]["sport"] == "basketball" and r["leagues"][2]["matches"][0]["score"] == "50-71"
    r = (await client.call_tool("v3_scores", {"team": "پرسپولیس"})).structured_content
    assert r["matches_found"] == 1 and r["leagues"][0]["matches"][0]["away"] == "پرسپولیس"
    r = (await client.call_tool("v3_scores", {"max_matches": 2})).structured_content
    assert sum(len(lg["matches"]) for lg in r["leagues"]) == 2 and "truncated" in r
    r = (await client.call_tool("v3_scores", {"sport": "basketball", "live_only": True})).structured_content
    assert r["leagues"][0]["league_id"] == 209
    api["/v2.0/livescore/-1"] = fixture("livescore_today.json")
    await client.call_tool("v3_scores", {"day": -1})
    assert api.calls[-1].url.path == "/v2.0/livescore/-1"


async def test_match_football(client, api):
    api["/v2.0/football/matches/497496"] = fixture("match_football.json")
    r = (await client.call_tool("v3_match", {"match_id": 497496})).structured_content
    assert (r["home"], r["away"], r["score"], r["status"]) == ("نساجی مازندران", "پرسپولیس", "0-1", "finished")
    assert r["referee"] and r["stadium"] and r["week"] == 11 and r["video"]["id"] == 567396
    goal = next(e for e in r["events"] if e["type"] == "goal")
    assert goal["player"] == "محمدمهدی محبی" and goal["score"] == "0-1" and goal["team"] == "away"
    assert {e["type"] for e in r["events"]} == {"goal", "card", "substitution"}
    assert all(e["card"] == "yellow" for e in r["events"] if e["type"] == "card")
    assert r["home_lineup"]["formation"] == "4-4-2" and len(r["home_lineup"]["lines"]) == 4
    assert len(r["away_lineup"]["bench"]) == 11 and r["away_lineup"]["coach"]
    assert r["home_next"].startswith("497508:")


async def test_match_basketball(client, api):
    api["/v2.0/basketball/matches/180086"] = fixture("match_basketball.json")
    r = (await client.call_tool("v3_match", {"match_id": 180086, "sport": "basketball"})).structured_content
    assert r["score"] == "50-71" and r["quarters"][0] == "18-27" and r["home"] == "یوتا جاز"
    assert r["home_recent"] and r["home_recent"][0]["score"] == "111-117"


async def test_leagues_and_league(client, api):
    api["/v2.0/football/leagues"] = fixture("leagues.json")
    r = (await client.call_tool("v3_league", {})).structured_content
    assert {"id": 6, "name": "لیگ برتر ایران"} in r["leagues"] and len(r["leagues"]) == 13
    api["/v2.0/football/leagues/6"] = fixture("league_6.json")
    api["/v2.0/football/leagues/6/archive"] = fixture("archive_6.json")
    r = (await client.call_tool("v3_league", {"league_id": 6})).structured_content
    assert r["current_season_id"] == 903038 and r["name"] == "لیگ برتر ایران"
    assert any(s.get("winner") == "تراکتور" for s in r["seasons"])


async def test_standings_table(client, api):
    api["/v2.0/football/leagues/6"] = fixture("league_6.json")
    api[f"{S6}/standing"] = fixture("standing_6.json")
    r = (await client.call_tool("v3_standings", {"league_id": 6})).structured_content
    top = r["table"][0]
    assert r["season_id"] == 903038 and top["rank"] == 1 and top["team"] == "پرسپولیس" and top["points"] == 23
    assert top["played"] == 11 and set(top["form"]) <= set("WDL") and len(r["table"]) == 18
    assert "سقوط به لیگ آزادگان" in r["zones"] and r["notes"]
    api["/v2.0/football/leagues/6/seasons/900952/standing"] = fixture("standing_6.json")
    r = (await client.call_tool("v3_standings", {"league_id": 6, "season_id": 900952})).structured_content
    assert r["season_id"] == 900952


async def test_standings_groups_and_knockout(client, api):
    api["/v2.0/football/leagues/28"] = fixture("league_28.json")
    api["/v2.0/football/leagues/28/seasons/900986/multi-standing"] = fixture("multi_28.json")
    r = (await client.call_tool("v3_standings", {"league_id": 28})).structured_content
    assert (
        len(r["groups"]) == 2 and r["groups"][0]["group"] == "گروه A" and r["groups"][0]["table"][0]["team"] == "مکزیک"
    )
    api["/v2.0/football/leagues/22"] = fixture("league_22.json")
    api["/v2.0/football/leagues/22/seasons/900984/playoffs"] = fixture("playoffs_22.json")
    r = (await client.call_tool("v3_standings", {"league_id": 22})).structured_content
    assert "bracket" in r["note"] and r["rounds"][0]["round"] == "یک شانزدهم" and len(r["rounds"][0]["ties"]) == 16
    tie = r["rounds"][0]["ties"][0]
    assert tie["home"] and tie["legs"][0]["score"] == "0-3" and tie["winner_id"] == 9


async def test_league_matches(client, api):
    api["/v2.0/football/leagues/6"] = fixture("league_6.json")
    api[f"{S6}/matches"] = fixture("matches_6.json")
    api[f"{S6}/results"] = fixture("results_6.json")
    r = (await client.call_tool("v3_league_matches", {"league_id": 6})).structured_content
    assert r["has_more"] is True and r["rounds"][0]["round"] and r["rounds"][0]["days"][0]["matches"][0]["home"]
    r = (
        await client.call_tool("v3_league_matches", {"league_id": 6, "which": "results", "skip": 9})
    ).structured_content
    assert api.calls[-1].url.params["skip"] == "9" and api.calls[-1].url.path == f"{S6}/results"
    assert r["rounds"][0]["days"][0]["matches"][0]["score"]


async def test_top_players(client, api):
    api["/v2.0/football/leagues/6"] = fixture("league_6.json")
    api[f"{S6}/stats/players/advanced/goals"] = fixture("scorers_6.json")
    r = (await client.call_tool("v3_top_players", {"league_id": 6, "limit": 3})).structured_content
    p = r["players"]
    assert len(p) == 3 and p[0]["rank"] == 1 and p[0]["goals"] == 5 and p[0]["team"] and "red" not in p[0]
    await client.call_tool("v3_top_players", {"league_id": 6, "stat": "clean_sheets"})
    assert api.calls[-1].url.path.endswith("/advanced/clean-sheets")


async def test_team_and_matches(client, api):
    api["/v2.0/football/teams/6"] = fixture("team_6.json")
    api["/v2.0/football/teams/6/squad"] = fixture("squad_6.json")
    api["/v2.0/football/teams/6/transfers"] = fixture("transfers_6.json")
    r = (await client.call_tool("v3_team", {"team_id": 6, "transfers": True})).structured_content
    assert r["name"] == "پرسپولیس" and r["followers"] > 1000 and set(r["form"]["all"]) <= set("WDL")
    assert r["squad"][0]["role"] and r["squad"][0]["players"][0][0].isdigit()
    assert r["transfers_in"] and r["transfers_out"]
    api["/v2.0/football/teams/6/results"] = fixture("team_results_6.json")
    api["/v2.0/football/teams/6/fixtures"] = fixture("team_fixtures_6.json")
    r = (await client.call_tool("v3_team_matches", {"team_id": 6, "limit": 3})).structured_content
    dates = [m["date"] for m in r["matches"]]
    assert dates == sorted(dates, reverse=True) and len(dates) == 3  # newest first
    assert (
        r["matches"][0]["home_id"] and r["matches"][0]["away_id"]
    )  # taken from links, the `id` field holds a match id
    r = (await client.call_tool("v3_team_matches", {"team_id": 6, "which": "upcoming"})).structured_content
    assert len(r["matches"]) == 4 and r["matches"][0]["status"] == "scheduled"


async def test_news_article_videos_search(client, api):
    api["/v1.0/news/archive"] = fixture("news_latest.json")
    r = (await client.call_tool("v3_news", {"take": 5})).structured_content
    assert len(r["news"]) == 5 and r["news"][0]["id"] and r["news"][0]["title"] and r["has_more"] is True
    assert api.calls[-1].url.params["take"] == "5"
    api["/v1.0/football/teams/6/news"] = fixture("news_team.json")
    await client.call_tool("v3_news", {"scope": "team", "id": 6})
    assert api.calls[-1].url.path == "/v1.0/football/teams/6/news"
    bad = await client.call_tool("v3_news", {"scope": "league"})
    assert bad.is_error and "needs id" in bad.content[0].text
    api["/v1.0/news/2440996"] = fixture("news_article.json")
    r = (await client.call_tool("v3_article", {"news_id": 2440996})).structured_content
    assert "<" not in r["text"] and len(r["text"]) > 200 and r["match_id"] == 497496
    assert {"kind": "team", "id": 6, "name": "پرسپولیس"} in r["tags"]
    api["/v1.0/videos"] = fixture("videos.json")
    r = (await client.call_tool("v3_videos", {})).structured_content
    assert r["videos"][0]["url"].startswith("https://video.varzesh3.com/video/")
    api["/v1.0/football/matches/497496/videos/tabs"] = [{"title": "همه", "items": fixture("videos.json")["items"]}]
    r = (await client.call_tool("v3_videos", {"scope": "match", "id": 497496, "take": 2})).structured_content
    assert len(r["videos"]) == 2
    api["/v1.0/query"] = fixture("search.json")
    r = (await client.call_tool("v3_search", {"query": "پرسپولیس"})).structured_content
    assert r["entities"][0] == {"kind": "Team", "id": 6, "name": "پرسپولیس", "sport": "Football"}
    assert r["news"] and r["videos"]


async def test_upstream_errors_become_tool_errors(client, api):
    r = await client.call_tool("v3_match", {"match_id": 1})  # no fake route -> 404
    assert r.is_error and "HTTP 404" in r.content[0].text


async def test_match_events_decoded_and_prediction(client, api):
    api["/v2.0/football/matches/441601"] = fixture("match_var_441601.json")
    api["/api/prediction/441601/varzesh3"] = fixture("pred_497496.json")
    r = (await client.call_tool("v3_match", {"match_id": 441601, "prediction": True})).structured_content
    kinds = {e["type"] for e in r["events"]}
    assert {"penalty", "var", "substitution"} <= kinds
    pen = next(e for e in r["events"] if e["type"] == "penalty")
    assert pen["player"] == "ریکاردو آلوز" and pen["result"] == "scored" and pen["score"] == "2-1"
    assert next(e for e in r["events"] if e["type"] == "var")["decision"] == "پنالتی"
    sub = next(e for e in r["events"] if e["type"] == "substitution")
    assert sub["in"] and sub["out"]
    assert any(e.get("card") == "red" for e in r["events"])
    assert r["prediction"]["away_win_pct"] == 82 and r["prediction"]["popular_scores"][0]["score"] == "0-2"
    http._cache.clear()
    api["/v2.0/football/matches/441601"]["events"][0]["eventType"] = 1
    api["/v2.0/football/matches/441601"]["events"][0]["goalType"] = 1
    r = (await client.call_tool("v3_match", {"match_id": 441601})).structured_content
    assert r["events"][0]["own_goal"] is True and "prediction" not in r


async def test_other_sports(client, api):
    api["/v2.0/volleyball/matches/176339"] = fixture("match_volleyball.json")
    r = (await client.call_tool("v3_match", {"match_id": 176339, "sport": "volleyball"})).structured_content
    assert r["score"] == "2-3" and r["sets"] == ["23-25", "25-18", "25-21", "24-26", "13-15"]
    api["/v2.0/volleyball/leagues/33"] = fixture("league_volleyball_33.json")
    r = (await client.call_tool("v3_league", {"sport": "volleyball"})).structured_content
    assert r["leagues"][0] == {"id": 33, "name": "لیگ برتر والیبال"}
    r = (await client.call_tool("v3_league", {"league_id": 33, "sport": "volleyball"})).structured_content
    assert r["current_season_id"] == 906622 and r["seasons"] == []  # no archive for volleyball
    api["/v2.0/volleyball/leagues/33/seasons/906622/multi-standing"] = fixture("multi_volleyball.json")
    r = (await client.call_tool("v3_standings", {"league_id": 33, "sport": "volleyball"})).structured_content
    row = r["groups"][0]["table"][0]
    assert row["rank"] == 1 and row["sets_won"] == 6 and row["points_for"] == 171
    api["/v1.0/contents/Wrestling"] = fixture("contents_wrestling.json")
    r = (await client.call_tool("v3_news", {"scope": "section", "section": "wrestling", "take": 2})).structured_content
    assert r["section"] == "Wrestling" and len(r["items"]) == 2 and r["items"][0]["type"] in {"news", "video"}
    bad = await client.call_tool("v3_news", {"scope": "section", "section": "nope"})
    assert bad.is_error and "Wrestling" in bad.content[0].text
    api["/v1.0/volleyball/leagues/33/news"] = fixture("news_team.json")
    await client.call_tool("v3_news", {"scope": "league", "id": 33, "sport": "volleyball"})
    assert api.calls[-1].url.path == "/v1.0/volleyball/leagues/33/news"


async def test_player_and_team_players(client, api):
    api["/v2.0/football/players/110789"] = fixture("player_110789.json")
    api["/v2.0/football/players/110789/at-a-glance"] = fixture("player_110789_glance.json")
    r = (await client.call_tool("v3_player", {"player_id": 110789})).structured_content
    assert (r["name"], r["team_id"], r["shirt_number"], r["age"]) == ("پیام نیازمند", 6, 1, 31) and r["news"]
    base = "/v2.0/football/teams/6/stats"
    api[f"{base}/leagues"] = fixture("team_stats_leagues.json")
    api[f"{base}/leagues/6/seasons"] = fixture("team_stats_seasons.json")
    api[f"{base}/goals"] = fixture("team_stats_goals.json")
    r = (await client.call_tool("v3_team_players", {"team_id": 6})).structured_content
    assert r["season_id"] == 903038 and r["players"][0]["goals"] > 0 and r["players"][0]["id"]
    assert api.calls[-1].url.params["seasonId"] == "903038"
    bad = await client.call_tool("v3_team_players", {"team_id": 6, "league_id": 999})
    assert bad.is_error and "pick one of" in bad.content[0].text


async def test_head_to_head(client, api):
    from varzesh3_mcp.sports import _tid

    results = fixture("team_results_6.json")
    api["/v2.0/football/teams/6/results"] = results
    m = results["items"][-1]
    opp = next(t for t in (_tid(m["host"]), _tid(m["guest"])) if t != 6)
    r = (await client.call_tool("v3_head_to_head", {"team_id": 6, "opponent_id": opp, "depth": 2})).structured_content
    s = r["summary"]
    assert s["played"] >= 1 and s["won"] + s["drawn"] + s["lost"] == s["played"]
    assert all(opp in (x["home_id"], x["away_id"]) for x in r["meetings"])
    assert len({x["id"] for x in r["meetings"]}) == len(r["meetings"])  # pages repeat in the fake, ids dedupe


async def test_transfers_tv_and_league_stats(client, api):
    api["/v2.0/football/transfers/iran"] = fixture("transfers_iran.json")
    r = (await client.call_tool("v3_transfers", {"team_id": 4})).structured_content
    assert [t["team_id"] for t in r["teams"]] == [4] and r["teams"][0]["out"] and r["windows"][0]["window_id"] == 42
    r = (await client.call_tool("v3_transfers", {"direction": "in", "loans": "only"})).structured_content
    assert all(x["loan"] for t in r["teams"] for x in t.get("in", []))
    r = (await client.call_tool("v3_transfers", {"limit": 1})).structured_content
    assert "truncated" in r
    api["/v1.0/live"] = fixture("live_schedule.json")
    r = (await client.call_tool("v3_tv_schedule", {})).structured_content
    b = r["days"][0]["broadcasts"][0]
    assert b["time"] and b["match_id"] and b["stream"].startswith("https://www.anten.ir/")
    r = (await client.call_tool("v3_tv_schedule", {"query": "zzz"})).structured_content
    assert r["days"] == []
    api["/v2.0/football/leagues/6"] = fixture("league_6.json")
    api[f"{S6}/sidebar-stats"] = fixture("sidebar_stats_6.json")
    api[f"{S6}/stats/teams"] = fixture("team_boxes_6.json")
    api[f"{S6}/records"] = fixture("records_6.json")
    r = (await client.call_tool("v3_league_stats", {"league_id": 6})).structured_content
    assert r["goals_per_match"] == 1.97 and r["team_leaders"]["wins"][0].startswith("پرسپولیس") and r["streaks"]
    api[f"{S6}/stats/teams/advanced/possession"] = fixture("team_possession_6.json")
    r = (await client.call_tool("v3_league_stats", {"league_id": 6, "ranking": "possession"})).structured_content
    assert r["teams"][0] == {"rank": 1, "team": "سپاهان", "team_id": 10, "value": 59.5, "played": 11}


async def test_requests_look_like_the_site_frontend(api):
    api["/v2.0/livescore/today"] = {}
    api["/v1.0/query"] = {}
    await http.fetch(f"{http.API}/v2.0/livescore/today")
    await http.fetch(http.SEARCH, {"q": "x"})
    for r in api.calls:
        h = r.headers
        assert h["accept"] == "*/*" and h["origin"] == "https://www.varzesh3.com"
        assert h["referer"] == "https://www.varzesh3.com/" and h["sec-fetch-site"] == "same-site"
        assert h["sec-fetch-mode"] == "cors" and h["sec-fetch-dest"] == "empty" and h["priority"] == "u=1, i"
