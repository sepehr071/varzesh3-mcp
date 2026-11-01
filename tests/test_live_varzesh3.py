import pytest

pytestmark = [pytest.mark.live, pytest.mark.anyio]

PERSEPOLIS = 6
NASAJI_PERSEPOLIS = 497496  # 2026-10-31, final 0-1


async def test_live_scores_today(client):
    r = (await client.call_tool("v3_scores", {})).structured_content
    assert r["leagues"] and r["matches_found"] > 0
    m = r["leagues"][0]["matches"][0]
    assert m["id"] and m["home"] and m["away"] and m["status"]


async def test_live_scores_other_day(client):
    r = (await client.call_tool("v3_scores", {"day": -1, "league_id": 6})).structured_content
    assert r["leagues"] is not None


async def test_live_match(client):
    r = (await client.call_tool("v3_match", {"match_id": NASAJI_PERSEPOLIS})).structured_content
    assert (r["home"], r["away"], r["score"], r["status"]) == ("نساجی مازندران", "پرسپولیس", "0-1", "finished")
    assert any(e["type"] == "goal" and e["player"] == "محمدمهدی محبی" for e in r["events"])
    assert r["home_lineup"]["lines"] and r["referee"]


async def test_live_leagues_and_league(client):
    r = (await client.call_tool("v3_league", {})).structured_content
    assert {"id": 6, "name": "لیگ برتر ایران"} in r["leagues"]
    r = (await client.call_tool("v3_league", {"league_id": 6})).structured_content
    assert r["current_season_id"] and len(r["seasons"]) > 3


async def test_live_standings(client):
    r = (await client.call_tool("v3_standings", {"league_id": 6})).structured_content
    assert len(r["table"]) == 18 and r["table"][0]["rank"] == 1
    pts = [t["points"] for t in r["table"]]
    assert pts[0] == max(pts)


async def test_live_standings_groups_and_knockout(client):
    r = (await client.call_tool("v3_standings", {"league_id": 28})).structured_content
    assert len(r["groups"]) == 12
    r = (await client.call_tool("v3_standings", {"league_id": 22, "stage": "knockout"})).structured_content
    assert r["rounds"][0]["ties"]


async def test_live_league_matches(client):
    r = (await client.call_tool("v3_league_matches", {"league_id": 3})).structured_content
    assert r["rounds"] and r["rounds"][0]["days"][0]["matches"]
    r = (await client.call_tool("v3_league_matches", {"league_id": 6, "which": "results"})).structured_content
    assert any(m["score"] for rd in r["rounds"] for d in rd["days"] for m in d["matches"])


async def test_live_top_players(client):
    r = (await client.call_tool("v3_top_players", {"league_id": 6, "limit": 5})).structured_content
    goals = [p["goals"] for p in r["players"]]
    assert len(goals) == 5 and goals == sorted(goals, reverse=True) and goals[0] > 0


async def test_live_team(client):
    r = (await client.call_tool("v3_team", {"team_id": PERSEPOLIS, "transfers": True})).structured_content
    assert r["name"] == "پرسپولیس" and r["squad"] and r["transfers_in"]
    r = (await client.call_tool("v3_team_matches", {"team_id": PERSEPOLIS, "limit": 5})).structured_content
    assert len(r["matches"]) == 5 and all(m["score"] for m in r["matches"])
    r = (await client.call_tool("v3_team_matches", {"team_id": PERSEPOLIS, "which": "upcoming"})).structured_content
    assert r["matches"]


async def test_live_news_article_videos_search(client):
    news = (await client.call_tool("v3_news", {"take": 3})).structured_content
    assert len(news["news"]) == 3
    art = (await client.call_tool("v3_article", {"news_id": news["news"][0]["id"]})).structured_content
    assert art["text"] and "<" not in art["text"]
    r = (await client.call_tool("v3_news", {"scope": "team", "id": PERSEPOLIS, "take": 3})).structured_content
    assert r["news"]
    r = (await client.call_tool("v3_videos", {"scope": "match", "id": NASAJI_PERSEPOLIS})).structured_content
    assert r["videos"]
    r = (await client.call_tool("v3_videos", {"take": 3})).structured_content
    assert len(r["videos"]) == 3
    r = (await client.call_tool("v3_search", {"query": "پرسپولیس"})).structured_content
    assert any(e["kind"] == "Team" and e["id"] == PERSEPOLIS for e in r["entities"])


async def test_live_player_and_team_players(client):
    r = (await client.call_tool("v3_player", {"player_id": 110789})).structured_content
    assert r["name"] == "پیام نیازمند" and r["team_id"] == PERSEPOLIS
    r = (await client.call_tool("v3_team_players", {"team_id": PERSEPOLIS})).structured_content
    assert r["players"] and r["players"][0]["id"] and r["players"][0]["goals"] > 0


async def test_live_head_to_head(client):
    r = (
        await client.call_tool("v3_head_to_head", {"team_id": PERSEPOLIS, "opponent_id": 4, "depth": 3})
    ).structured_content
    assert r["summary"]["played"] >= 2 and r["meetings"]


async def test_live_transfers_tv_stats(client):
    r = (await client.call_tool("v3_transfers", {"team_id": PERSEPOLIS})).structured_content
    assert r["teams"] and r["windows"]
    r = (await client.call_tool("v3_tv_schedule", {})).structured_content
    assert r["days"] and r["days"][0]["broadcasts"][0]["time"]
    r = (await client.call_tool("v3_league_stats", {"league_id": 6})).structured_content
    assert r["goals_per_match"] and "wins" in r["team_leaders"]
    r = (await client.call_tool("v3_league_stats", {"league_id": 6, "ranking": "possession"})).structured_content
    assert len(r["teams"]) == 18


async def test_live_other_sports_and_events(client):
    r = (await client.call_tool("v3_standings", {"league_id": 33, "sport": "volleyball"})).structured_content
    assert r["groups"] and r["groups"][0]["table"][0]["sets_won"] is not None
    r = (await client.call_tool("v3_match", {"match_id": 176339, "sport": "volleyball"})).structured_content
    assert r["score"] == "2-3" and len(r["sets"]) == 5
    r = (await client.call_tool("v3_standings", {"league_id": 27, "sport": "futsal"})).structured_content
    assert len(r["table"]) > 8
    r = (await client.call_tool("v3_news", {"scope": "section", "section": "Wrestling", "take": 3})).structured_content
    assert len(r["items"]) == 3
    r = (await client.call_tool("v3_match", {"match_id": 441601, "prediction": True})).structured_content
    assert any(e["type"] == "var" for e in r["events"]) and any(e["type"] == "penalty" for e in r["events"])
