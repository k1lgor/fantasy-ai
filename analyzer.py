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


def generate_squad_recommendation(team_id: int, model: str = "gpt-4o") -> str:
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

    prompt = f"""You are an elite Fantasy Premier League strategist.

Your task is to generate **optimal recommendations specifically for the user's current squad**, using all provided data.
Focus on maximizing total expected points while respecting budget, squad rules, and available transfers.

**CRITICAL: Pay special attention to injured and flagged players. Always provide specific replacement options.**

### OUTPUT (Markdown)

---

## 1. **Injury & Availability Report**
- **MANDATORY SECTION**: List ALL players with injury concerns, fitness doubts, or availability issues.
- For each flagged player, include:
  - Status code (a=available, d=doubtful, i=injured, u=unavailable, s=suspended, n=not in squad)
  - Chance of playing percentage (if available)
  - Latest news/injury update
  - **URGENCY LEVEL**: Critical (must transfer), High (transfer recommended), Medium (monitor), Low (likely to play)

---

## 2. **Potential Replacements for Current Squad**
- **MANDATORY SECTION**: For EACH position (GK, DEF, MID, FWD), show the top replacement options available.
- For injured/flagged players, provide **specific ranked alternatives** with:
  - Player name, team, price
  - Price difference vs current player
  - Form analysis (recent performances)
  - **Fixture difficulty analysis (next 5 games)** - highlight easy/difficult runs
  - Why they're a good replacement
- Even for healthy players, show potential upgrades/sideways moves if they improve the squad.
- Format: **Position → Current Player(s) → Replacement Options (ranked 1-3)**

---

## 3. **Optimized 15-Man Squad (Based on Current Squad Only)**
- Evaluate the user's existing 15 players.
- Identify who should *remain*, who is *upgradeable*, and who is a *priority sell*.
- **Highlight injured/unavailable players clearly** with their status.
- Present the optimized final squad after applying 0–5 recommended transfers.
- Format each player as: **Name — Position — Team — Price — Form — Status — Reasoning (1 sentence)**.
- Respect squad constraints (2 GK, 5 DEF, 5 MID, 3 FWD) and the user's bank + transfer limits.

---

## 4. **Captain & Vice-Captain**
- Recommend the strongest captain and vice-captain *from the user's optimized squad*.
- **Ensure both are fit and likely to play**.
- Justify with form, fixture quality, xGI/xCS potential, and minutes security.

---

## 5. **Best Starting XI**
- Select the optimal formation among:
  **3-4-3, 3-5-2, 4-4-2, 4-5-1, 5-3-2, 5-4-1**
- **Exclude injured/doubtful players from the starting XI**.
- Prioritize maximum expected points, fixture difficulty, and rotation risk.
- Clearly list XI in order from GK → FWD.

---

## 6. **Bench Order**
- Rank all four bench players with a short justification (fitness, fixture, rotation probability).
- **Flag any bench players who are injured/unavailable**.

---

## 7. **Transfer Recommendations (0–5 Moves)**
- **PRIORITY: Address injured/unavailable players first**.
- Base all decisions on the user's existing squad.
- Inputs:
  - Free Transfers: **{data["team"].get("free_transfers", 1)}**
  - Bank: **£{data["team"].get("bank", 0) / 10:.1f}M**
  - Extra transfers cost -4 each.
- Provide:
  1. **Players Out** (injured/flagged players FIRST, then underperformers)
  2. **Specific Replacement Options** (ranked with exact names from the available players list)
  3. **Net cost**, total spend, and whether it fits the bank.
- Judge players using:
  - **INJURY STATUS** (most important)
  - **NEXT 5 FIXTURES** (analyze fixture difficulty - use the provided fixture data showing opponent, home/away, and difficulty rating)
  - last 5 GWs form
  - fixture difficulty (home/away + opponent)
  - expected minutes
  - goals/assists/saves/clean sheets
  - ppm (value)
  - rotation risk
  - long-term upside based on fixture run

---

## 8. **Key Insights for This Squad**
Provide a concise yet detailed bullet list summarizing:
- **Injury concerns and their impact**
- Form streaks (hot/cold players)
- Fixture clusters (strong/weak patches)
- Any rotation risks
- Underpriced or undervalued assets in the squad
- Spots where the team is structurally weak or imbalanced

---

### DATA PROVIDED
- Current GW: {data["current_gw"]}
- Next GW: {data["next_gw"]}
- Team Info: {team_str}
- Current Squad: {current_players_str}
- Injured/Flagged Players: {injured_str}
- Next 5 Fixtures by Team: {fixtures_sum_str}
- Top Replacement Options by Position: {top_players_str}

**FIXTURE DATA FORMAT:**
Each team has up to 5 upcoming fixtures with:
- gw: gameweek number
- opp: opponent team short name
- home: true if home game, false if away
- diff: opponent difficulty (1=easiest, 5=hardest)

**PLAYER STATUS CODES:**
- a = available
- d = doubtful
- i = injured
- u = unavailable
- s = suspended
- n = not in squad

**CRITICAL: Analyze the next 5 fixtures for each team when making transfer recommendations. Players with easier upcoming fixtures (lower diff ratings, home games) should be prioritized over those with difficult runs.**

**Your output must be concise, direct, and highly actionable. Always provide specific player names for replacements, not generic suggestions.**
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4000,
    )

    return response.choices[0].message.content
