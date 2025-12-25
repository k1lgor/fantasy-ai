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
    Fetch FPL data and use GPT-5 to generate squad recommendations.

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
                "ppg": p["points_per_game"],
                "cost": p["now_cost"] / 10,
                "ep": p["ep_this"],
                "minutes": p["minutes"],
                "starts": p.get("starts", 0),
                "goals": p["goals_scored"],
                "assists": p["assists"],
                "xg": p.get("expected_goals", "0"),
                "xa": p.get("expected_assists", "0"),
                "xgi90": p.get("expected_goal_involvements_per_90", "0"),
                "xgc90": p.get("expected_goals_conceded_per_90", "0"),
                "ict": p["ict_index"],
                "threat": p["threat"],
                "creativity": p["creativity"],
                "status": p.get("status", "a"),
                "news": p.get("news", ""),
            }
            for p in pos_list
        ]
    top_players_str = json.dumps(pos_players, separators=(",", ":"))

    # Current squad with injury status
    squad_ids = [p["element"] for p in data["picks"]["picks"]]
    squad_history = data.get("squad_history", {})
    current_players = [
        {
            "id": el["id"],
            "name": el["web_name"],
            "team": team_map[el["team_code"]],
            "pos": ["GK", "DEF", "MID", "FWD"][el["element_type"] - 1],
            "form": el["form"],
            "points": el["total_points"],
            "ppg": el["points_per_game"],
            "cost": el["now_cost"] / 10,
            "status": el.get("status", "a"),
            "news": el.get("news", ""),
            "chance_of_playing": el.get("chance_of_playing_next_round"),
            "ict": el.get("ict_index"),
            "xg": el.get("expected_goals", "0"),
            "xa": el.get("expected_assists", "0"),
            "xgi90": el.get("expected_goal_involvements_per_90", "0"),
            "xgc90": el.get("expected_goals_conceded_per_90", "0"),
            "minutes": el.get("minutes", 0),
            "starts": el.get("starts", 0),
            "threat": el.get("threat", "0"),
            "creativity": el.get("creativity", "0"),
            "recent_pts": [h["total_points"] for h in squad_history.get(el["id"], [])][
                -4:
            ],
            "ep": el.get("ep_this"),
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

    # Check for Double Gameweeks (DGW) and Blank Gameweeks (BGW)
    schedule_notes = []
    for team_id, fixtures in team_fixtures.items():
        team_name = team_id_map.get(team_id, f"Team {team_id}")
        gw_counts = {}
        for f in fixtures:
            gw = f["gw"]
            gw_counts[gw] = gw_counts.get(gw, 0) + 1

        for gw, count in gw_counts.items():
            if count > 1:
                schedule_notes.append(
                    f"DGW ALERT: {team_name} plays {count} times in GW{gw}"
                )

    dgw_bgw_str = json.dumps(schedule_notes) if schedule_notes else "None"
    fixtures_sum_str = json.dumps(fixtures_by_team, separators=(",", ":"))

    # Chip Strategy
    chips_used = [c["name"] for c in data.get("history", {}).get("chips", [])]
    all_chips = {"wildcard", "freehit", "bboost", "3xc"}
    remaining_chips = list(all_chips - set(chips_used))
    chips_str = json.dumps(remaining_chips, separators=(",", ":"))

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

### PRIMARY OBJECTIVE:
Maximize expected total points over the next gameweek.
**MANTRA**: "Points are Points." A -4 hit that gains +6 points is a NET GAIN. Do not fear hits.

### SECONDARY OBJECTIVES (tie-breakers, in order):
1. Captaincy upside and ceiling
2. Minutes security
3. Fixture swing exploitation
4. Squad flexibility for future GWs
5. Value preservation (avoid price drops)

### RANK-AWARE STRATEGY:
Determine strategic posture from rank:
- Rank < 50k → DEFENSIVE (block EO, minimize variance)
- Rank 50k–500k → BALANCED
- Rank > 500k → AGGRESSIVE (seek differentials, accept variance)
All decisions MUST align with this mode and label risk level.

### CAPTAINCY-FIRST PLANNING (CRITICAL):
Before transfers, identify the best captaincy options for the next 3 GWs.
If a transfer significantly improves captaincy EV, it takes priority over all other upgrades.

### RUTHLESS FLOP & RISING STAR IDENTIFICATION (STRICT THRESHOLDS):
Analyze `recent_pts` (last 4 matches) and `form` against these strict rules:
- **FLOPS (SELL IMMEDIATELY)**: A player is a total FLOP if they have scored **≤ 7 total points in the last 3 matches** OR **≤ 10 total points in the last 4 matches**.
- **RISING STARS (MUST BUY)**: A player is a RISING STAR if they have scored **≥ 18 total points in the last 3 matches** OR **≥ 24 total points in the last 4 matches**.
- **NO EXCUSES**: If a player is a Flop, sell them immediately even for a hit. Stop chasing "potential" in players who fail the numeric test.

### TRANSFER DISCIPLINE & AGGRESSIVE HIT AUTHORIZATION:
- **FREE TRANSFERS**: You have {free_transfers} free transfer(s).
- **AUTHORIZATION FOR MULTIPLE HITS**: You are **STRONGLY AUTHORIZED AND ENCOURAGED** to suggest **multiple transfers involving hits (-4, -8, or even -12)**.
- **WHEN TO TAKE HITS**:
    1. To remove a FLOP and bring in a RISING STAR (almost always worth -4).
    2. To fix a structural issue (e.g., no playing GK).
    3. To bring in a Captaincy option with significantly higher EV than current options.
- **STRATEGY**: It is mathematically better to take a -8 hit and score 50 points (Net 42) than to save free transfers and score 35 points.
- **For each recommended transfer, explicitly calculate the "Hit vs Payoff"**: e.g., "Taking a -4 here pays off if X scores > 4, which is likely because..."

### PERFORMANCE ANALYSIS & PREDICTION:
- **Sustainable Rise**: `form` > `ppg` AND `xgi90` is high (The perfect buy).
- **Explosive Differentials**: High `xgi90` / `xgc90` but low total points (The sneaky buy).
- **Sneaky Buy**: Low `xgi90` / `xgc90` but high total points (The sneaky buy).
- **Sustainable Decline**: `form` < `ppg` AND `xgi90` is low (The perfect sell).
- **Minutes Trend**: Prioritize players with increasing `starts`.

### CAPTAINCY SIMULATION:
Simulate the top 3 captaincy paths for the next 3 GWs. Choose the one with the highest ceiling.

### ADVANCED STATS UTILIZATION:
Use ICT Index to validate decisions:
- High ICT + Low Points = Teammates finishing poorly or bad luck. Keep/Buy.
- Low ICT + High Points = "Points from Nothing" (Unsustainable). Sell High.

### FIXTURE WINDOW ANALYSIS:
Identify teams whose fixtures improve or worsen after 2–3 GWs.
Prefer early entry into strong runs and timely exits before difficulty spikes.
Label players as BUY NOW / HOLD / SELL SOON.

### OWNERSHIP HEURISTICS:
Infer ownership archetypes (high / medium / low EO).
In AGGRESSIVE mode, prioritize low-EO differentials with upside.

### MINUTES SECURITY MODEL:
Classify players as LOCK / PROBABLE / RISKY / UNRELIABLE.
Avoid starting more than one RISKY player. Never captain RISKY or UNRELIABLE players.

### CHIP STRATEGY (CRITICAL):
You have these chips remaining: {chips_str}.
- If Wildcard is available and squad has 4+ issues (injuries/weak links/poor form), play it.
- If a confirmed Double Gameweek (DGW) is imminent and 3xc/BB is available, plan for it.
- If Free Hit is available, save for blank gameweeks or massive DGWs.
Explicitly recommend ONE strategy: "Save Chips" or "Play [Chip Name]".

### OUTPUT (STRICT MARKDOWN)

---

## 1. Chip Strategy & Schedule
- **Remaining Chips**: {chips_str}
- **Double/Blank GW Alerts**: {dgw_bgw_str}
- **Strategy Code**: [SAVE / WILDCARD / FREE HIT / TC / BB]
- **Reasoning**: One sentence on why this is the best strategy now.

---

## 2. Injury & Availability Report
List ALL flagged players with status, chance of playing, news, and URGENCY LEVEL.

---

## 3. Captaincy Outlook (Next 3 GWs)
Rank top captain and vice-captain options from the squad.
Explain upside, fixture quality, and minutes security.

---

## 4. Transfer Recommendations (0–5 Moves)
**Aggressiveness Level**: [High/Medium/Low] based on rank.
**Hit Budget**: Willingness to take hits this week.

Priority order:
1. Injured/unavailable players
2. **FLOPS OUT / RISING STARS IN**
3. Captaincy EV upgrades
4. Fixture swing exploitation

Include players OUT / IN, net cost, bank fit, and **Estimated Points Gain vs Hit Cost**.

---

## 5. Optimized 15-Man Squad
Show final squad after transfers.
Highlight priority sells and structural weaknesses.

---

## 6. Best Starting XI & Formation
Select optimal formation.
Exclude injured/doubtful players.

---

## 7. Bench Order
Rank bench by auto-sub priority and reliability.

---

## 8. Key Insights & Risks
Summarize:
- Injury impact
- Fixture swings
- Rotation risk
- Differentials

---

## 9. Final Decision Summary (MANDATORY TABLE)
Transfers | Hits | Captain | Formation | Key Risk | Expected Outcome

---

## 10. Contingency Plan
If a recommended player is benched or injured pre-deadline, provide emergency pivots.

---

### DATA PROVIDED
- Current GW: {data["current_gw"]}
- Next GW: {data["next_gw"]}
- Team Info: {team_str}
- Current Squad: {current_players_str}
- Injured/Flagged Players: {injured_str}
- Next 5 Fixtures by Team: {fixtures_sum_str}
- DGW/BGW Alerts: {dgw_bgw_str}
- Remaining Chips: {chips_str}
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
