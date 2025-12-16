import json
import os

import openai
import streamlit as st
from dotenv import load_dotenv

from fpl_data import fetch_squad_analysis_data

load_dotenv()


def get_openai_client() -> openai.OpenAI:
    """Initialize OpenAI client from .env or Streamlit secrets."""
    api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set (.env or Streamlit secrets)")
    return openai.OpenAI(api_key=api_key)


def generate_squad_recommendation(team_id: int, model: str = "gpt-5.2") -> str:
    """
    Fetch FPL data and use GPT-4o to generate squad recommendations.

    Args:
        team_id: FPL manager team ID
        model: OpenAI model to use

    Returns:
        GPT-generated recommendations as markdown string
    """
    data = fetch_squad_analysis_data(team_id)
    client = get_openai_client()

    # Ultra-minimal data for low token limits
    bootstrap = data["bootstrap"]
    elements = bootstrap["elements"]
    team_map = {t["code"]: t["short_name"] for t in bootstrap["teams"]}

    # Top 10 per position for comprehensive replacement options (1=GK,2=DEF,3=MID,4=FWD)
    pos_players = {}
    for pos in [1, 2, 3, 4]:
        pos_list = sorted(
            [el for el in elements if el["element_type"] == pos],
            key=lambda p: float(p.get("form", "0")),
            reverse=True,
        )[:10]
        pos_players[pos] = [
            {
                "id": p["id"],
                "name": p["web_name"],
                "team": team_map[p["team_code"]],
                "pos": ["GK", "DEF", "MID", "FWD"][p["element_type"] - 1],
                "form": p["form"],
                "points": p["total_points"],
                "cost": p["now_cost"] / 10,
                "ep": p["ep_this"],
                "minutes": p["minutes"],
                "goals": p["goals_scored"],
                "assists": p["assists"],
                "status": p.get("status", "a"),
                "news": p.get("news", ""),
            }
            for p in pos_list
        ]
    top_players_str = json.dumps(pos_players, separators=(",", ":"))

    # Current squad with injury status
    squad_ids = [p["element"] for p in data["picks"]["picks"]]
    current_players = [
        {
            "id": el["id"],
            "name": el["web_name"],
            "team": team_map[el["team_code"]],
            "pos": ["GK", "DEF", "MID", "FWD"][el["element_type"] - 1],
            "form": el["form"],
            "points": el["total_points"],
            "cost": el["now_cost"] / 10,
            "status": el.get("status", "a"),
            "news": el.get("news", ""),
            "chance_of_playing": el.get("chance_of_playing_next_round"),
        }
        for el in elements
        if el["id"] in squad_ids
    ]
    current_cost = sum(p["cost"] for p in current_players)
    current_players_str = json.dumps(current_players, separators=(",", ":"))

    # Build next 5 fixtures per team with difficulty ratings
    team_fixtures = {}
    teams = bootstrap["teams"]
    team_id_map = {t["id"]: t["short_name"] for t in teams}
    team_difficulty = {t["id"]: t.get("strength", 3) for t in teams}

    for fixture in data["fixtures"]:
        event = fixture.get("event")
        if not event:
            continue

        # Home team fixture
        home_id = fixture["team_h"]
        if home_id not in team_fixtures:
            team_fixtures[home_id] = []
        if len(team_fixtures[home_id]) < 5:
            team_fixtures[home_id].append(
                {
                    "gw": event,
                    "opp": team_id_map.get(fixture["team_a"], "?"),
                    "home": True,
                    "diff": team_difficulty.get(fixture["team_a"], 3),
                }
            )

        # Away team fixture
        away_id = fixture["team_a"]
        if away_id not in team_fixtures:
            team_fixtures[away_id] = []
        if len(team_fixtures[away_id]) < 5:
            team_fixtures[away_id].append(
                {
                    "gw": event,
                    "opp": team_id_map.get(fixture["team_h"], "?"),
                    "home": False,
                    "diff": team_difficulty.get(fixture["team_h"], 3),
                }
            )

    # Convert to team short names for readability
    fixtures_by_team = {
        team_id_map.get(team_id, str(team_id)): fixtures
        for team_id, fixtures in team_fixtures.items()
        if team_id in team_id_map
    }
    fixtures_sum_str = json.dumps(fixtures_by_team, separators=(",", ":"))

    bank = data["team"].get("last_deadline_bank", 0) / 10
    squad_value = data["team"].get("last_deadline_value", 1000) / 10
    free_transfers = 1  # Approximate, API limited

    team_str = json.dumps(
        {
            "rank": data["team"].get("rank"),
            "name": data["team"].get("name"),
            "active_chip": data["team"].get("active_chip"),
            "squad_value_M": round(squad_value, 1),
            "bank_M": round(bank, 1),
            "free_transfers": free_transfers,
        },
        separators=(",", ":"),
    )
    picks_str = json.dumps({"picks": data["picks"]["picks"]}, separators=(",", ":"))

    team_str = json.dumps(
        {
            "rank": data["team"].get("rank"),
            "name": data["team"].get("name"),
            "active_chip": data["team"].get("active_chip"),
            "squad_value_M": round(squad_value, 1),
            "bank_M": round(bank, 1),
            "free_transfers": free_transfers,
            "current_cost_M": round(current_cost, 1),
        },
        separators=(",", ":"),
    )

    # Identify injured/flagged players
    injured_players = [
        p
        for p in current_players
        if p["status"] != "a"
        or (p["chance_of_playing"] and p["chance_of_playing"] < 100)
    ]
    injured_str = (
        json.dumps(injured_players, separators=(",", ":"))
        if injured_players
        else "None"
    )

    prompt = f"""You are an elite Fantasy Premier League decision engine.

PRIMARY OBJECTIVE:
Maximize expected total points over the next 5 gameweeks.

SECONDARY OBJECTIVES (tie-breakers, in order):
1. Captaincy upside and ceiling
2. Minutes security
3. Fixture swing exploitation
4. Squad flexibility for future GWs
5. Value preservation (avoid price drops)

RANK-AWARE STRATEGY:
Determine strategic posture from rank:
- Rank < 50k → DEFENSIVE (block EO, minimize variance)
- Rank 50k–500k → BALANCED
- Rank > 500k → AGGRESSIVE (seek differentials, accept variance)
All decisions MUST align with this mode and label risk level.

CAPTAINCY-FIRST PLANNING (CRITICAL):
Before transfers, identify the best captaincy options for the next 3 GWs.
If a transfer significantly improves captaincy EV, it takes priority over all other upgrades.

MINUTES SECURITY MODEL:
Classify players as LOCK / PROBABLE / RISKY / UNRELIABLE.
Avoid starting more than one RISKY player.
Never captain RISKY or UNRELIABLE players.

FIXTURE WINDOW ANALYSIS:
Identify teams whose fixtures improve or worsen after 2–3 GWs.
Prefer early entry into strong runs and timely exits before difficulty spikes.
Label players as BUY NOW / HOLD / SELL SOON.

TRANSFER DISCIPLINE:
For each recommended transfer, explicitly justify:
- What happens if the manager does nothing
- Downside risk of the move
- GW horizon where the transfer pays back
Reject sideways or low-EV transfers.

OWNERSHIP HEURISTICS:
Infer ownership archetypes (high / medium / low).
In AGGRESSIVE mode, prioritize low-EO differentials with upside.

### OUTPUT (STRICT MARKDOWN)

---

## 1. Injury & Availability Report
List ALL flagged players with status, chance of playing, news, and URGENCY LEVEL.

---

## 2. Captaincy Outlook (Next 3 GWs)
Rank top captain and vice-captain options from the squad.
Explain upside, fixture quality, and minutes security.

---

## 3. Transfer Recommendations (0–5 Moves)
Priority order:
1. Injured/unavailable players
2. Captaincy EV upgrades
3. Fixture swing exploitation

Include players OUT / IN, net cost, bank fit, and EV justification.

---

## 4. Optimized 15-Man Squad
Show final squad after transfers.
Highlight priority sells and structural weaknesses.

---

## 5. Best Starting XI & Formation
Select optimal formation.
Exclude injured/doubtful players.

---

## 6. Bench Order
Rank bench by auto-sub priority and reliability.

---

## 7. Key Insights & Risks
Summarize:
- Injury impact
- Fixture swings
- Rotation risk
- Differentials

---

## 8. Final Decision Summary (MANDATORY TABLE)
Transfers | Captain | Formation | Key Risk | Expected Outcome

---

## 9. Contingency Plan
If a recommended player is benched or injured pre-deadline, provide emergency pivots.

---

### DATA PROVIDED
- Current GW: {data["current_gw"]}
- Next GW: {data["next_gw"]}
- Team Info: {team_str}
- Current Squad: {current_players_str}
- Injured/Flagged Players: {injured_str}
- Next 5 Fixtures by Team: {fixtures_sum_str}
- Top Replacement Options by Position: {top_players_str}

Fixture difficulty: 1=easiest, 5=hardest. Prefer lower difficulty and home games.

Make firm decisions. Avoid hedging language. If options are close, explain why.
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_completion_tokens=4000,
    )

    return response.choices[0].message.content
