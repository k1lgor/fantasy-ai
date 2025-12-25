from typing import Any, Dict

import requests

BASE_URL = "https://fantasy.premierleague.com/api/"


def get_bootstrap() -> Dict[str, Any]:
    """Fetch bootstrap-static data with players, teams, events."""
    response = requests.get(f"{BASE_URL}bootstrap-static/")
    response.raise_for_status()
    return response.json()


def get_fixtures(event: int) -> list:
    """Fetch fixtures for a specific gameweek."""
    response = requests.get(f"{BASE_URL}fixtures/?event={event}")
    response.raise_for_status()
    return response.json()


def get_user_team(team_id: int) -> Dict[str, Any]:
    """Fetch user team data."""
    response = requests.get(f"{BASE_URL}entry/{team_id}/")
    response.raise_for_status()
    return response.json()


def get_user_history(team_id: int) -> Dict[str, Any]:
    """Fetch user history including chip usage."""
    response = requests.get(f"{BASE_URL}entry/{team_id}/history/")
    response.raise_for_status()
    return response.json()


def get_player_history(player_id: int) -> Dict[str, Any]:
    """Fetch detailed player history and summaries."""
    response = requests.get(f"{BASE_URL}element-summary/{player_id}/")
    response.raise_for_status()
    return response.json()


def get_user_picks(team_id: int, event: int) -> Dict[str, Any]:
    """Fetch user current picks/squad for a gameweek."""
    response = requests.get(f"{BASE_URL}entry/{team_id}/event/{event}/picks/")
    response.raise_for_status()
    return response.json()


def get_next_gameweek(bootstrap: Dict[str, Any]) -> int:
    """Determine the next gameweek from bootstrap events."""
    events = bootstrap["events"]
    # Find first unfinished event
    for event in events:
        if not event["finished"]:
            return event["id"]
    # Fallback to last event +1 (new season)
    return events[-1]["id"] + 1


def fetch_squad_analysis_data(team_id: int) -> Dict[str, Any]:
    """
    Fetch comprehensive data for squad analysis:
    - Next gameweek
    - Bootstrap (players, teams)
    - Fixtures for next 5 GWs
    - User team data
    - User history (chips)
    """
    bootstrap = get_bootstrap()
    next_gw = get_next_gameweek(bootstrap)

    # Fetch fixtures for next 5 gameweeks
    all_fixtures = []
    for gw in range(next_gw, min(next_gw + 5, 39)):  # Max GW is 38
        try:
            gw_fixtures = get_fixtures(gw)
            all_fixtures.extend(gw_fixtures)
        except Exception:
            break  # Stop if no more fixtures available

    team = get_user_team(team_id)
    current_gw = next(
        (e["id"] for e in bootstrap["events"] if e["is_current"]),
        bootstrap["events"][0]["id"] if bootstrap["events"] else 1,
    )
    picks = get_user_picks(team_id, current_gw)
    history = get_user_history(team_id)

    # Fetch detailed history for the current 15-man squad
    squad_ids = [p["element"] for p in picks["picks"]]
    squad_history = {}
    for player_id in squad_ids:
        try:
            player_summary = get_player_history(player_id)
            # Last 5 games only to save tokens/processing
            squad_history[player_id] = player_summary.get("history", [])[-5:]
        except Exception:
            squad_history[player_id] = []

    return {
        "next_gw": next_gw,
        "current_gw": current_gw,
        "picks": picks,
        "bootstrap": bootstrap,
        "fixtures": all_fixtures,
        "team": team,
        "history": history,
        "squad_history": squad_history,
    }
