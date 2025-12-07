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

    # Top 5 per position (1=GK,2=DEF,3=MID,4=FWD)
    pos_players = {}
    for pos in [1, 2, 3, 4]:
        pos_list = sorted(
            [el for el in elements if el["element_type"] == pos],
            key=lambda p: float(p.get("form", "0")),
            reverse=True,
        )[:5]
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
            }
            for p in pos_list
        ]
    top_players_str = json.dumps(pos_players, separators=(",", ":"))

    # Current squad minimal
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
        }
        for el in elements
        if el["id"] in squad_ids
    ]
    current_players_str = json.dumps(current_players, separators=(",", ":"))

    # Fixtures compact
    fixtures_summary = {
        str(f["team_h"]): {
            "opp": team_map.get(f["team_a"], str(f["team_a"])),
            "home": True,
        }
        for f in data["fixtures"]
    } | {
        str(f["team_a"]): {
            "opp": team_map.get(f["team_h"], str(f["team_h"])),
            "home": False,
        }
        for f in data["fixtures"]
    }
    fixtures_sum_str = json.dumps(fixtures_summary, separators=(",", ":"))

    team_str = json.dumps(
        {
            k: v
            for k, v in data["team"].items()
            if k in ["rank", "entry_name", "active_chip", "player_name"]
        },
        separators=(",", ":"),
    )
    picks_str = json.dumps({"picks": data["picks"]["picks"]}, separators=(",", ":"))

    prompt = f"""You are an elite Fantasy Premier League strategist.

Your task is to generate **optimal recommendations specifically for the user’s current squad**, using all provided data.
Focus on maximizing total expected points while respecting budget, squad rules, and available transfers.

### OUTPUT (Markdown)

---

## 1. **Optimized 15-Man Squad (Based on Current Squad Only)**
- Evaluate the user’s existing 15 players.
- Identify who should *remain*, who is *upgradeable*, and who is a *priority sell*.
- Present the optimized final squad after applying 0–3 recommended transfers.
- Format each player as: **Name — Position — Team — Price — Form — Reasoning (1 sentence)**.
- Respect squad constraints (2 GK, 5 DEF, 5 MID, 3 FWD) and the user's bank + transfer limits.

---

## 2. **Captain & Vice-Captain**
- Recommend the strongest captain and vice-captain *from the user's optimized squad*.
- Justify with form, fixture quality, xGI/xCS potential, and minutes security.

---

## 3. **Best Starting XI**
- Select the optimal formation among:
  **3-4-3, 3-5-2, 4-4-2, 4-5-1, 5-3-2, 5-4-1**
- Prioritize maximum expected points, fixture difficulty, and rotation risk.
- Clearly list XI in order from GK → FWD.

---

## 4. **Bench Order**
- Rank all four bench players with a short justification (fitness, fixture, rotation probability).

---

## 5. **Transfer Recommendations (0–3 Moves)**
- Base all decisions on the user's existing squad.
- Inputs:
  - Free Transfers: **{data['team'].get('free_transfers', 1)}**
  - Bank: **£{data['team'].get('bank', 0)/10:.1f}M**
  - Extra transfers cost -4 each.
- Provide:
  1. **Players Out** (highest priority first)
  2. **Replacement Options** (ranked)
  3. **Net cost**, total spend, and whether it fits the bank.
- Judge players using:
  - last 5 GWs form
  - fixture difficulty (home/away + opponent)
  - expected minutes
  - goals/assists/saves/clean sheets
  - ppm (value)
  - injury/rotation risk
  - long-term upside (3–5 GWs)

---

## 6. **Key Insights for This Squad**
Provide a concise yet detailed bullet list summarizing:
- Form streaks (hot/cold players)
- Fixture clusters (strong/weak patches)
- Any rotation risks
- Any injury flags
- Underpriced or undervalued assets in the squad
- Spots where the team is structurally weak or imbalanced

---

### DATA PROVIDED
- Current GW: {data['current_gw']}
- Next GW: {data['next_gw']}
- Team Info: {team_str}
- Current Squad: {current_players_str}
- Fixtures Summary: {fixtures_sum_str}
- Top Players by Form: {top_players_str}

**Your output must be concise, direct, and highly actionable.**
"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4000,
    )

    return response.choices[0].message.content
