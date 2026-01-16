import json
import os
from datetime import datetime

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


def generate_squad_recommendation(
    team_id: int, model: str = "gpt-5.2"
) -> tuple[str, int]:
    """
    Fetch FPL data and use GPT-5 to generate squad recommendations.

    Args:
        team_id: FPL manager team ID
        model: OpenAI model to use

    Returns:
        Tuple of (GPT-generated recommendations as markdown string, next gameweek number)
    """
    data = fetch_squad_analysis_data(team_id)
    client = get_openai_client()

    # Ultra-minimal data for low token limits
    bootstrap = data["bootstrap"]
    elements = bootstrap["elements"]
    team_map = {t["code"]: t["short_name"] for t in bootstrap["teams"]}

    # Helper to calculate price trend
    def get_price_trend(p):
        # Note: This assumes 'cost_change_event' is available in the API data
        # +0.1m usually means rising, -0.1m falling
        change = p.get("cost_change_event", 0)
        if change > 0:
            return "RISING (+)"
        if change < 0:
            return "FALLING (-)"
        return "STABLE"

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
                # "price_trend": get_price_trend(p),
                # "set_piece_role": "PRIMARY" if p["id"] % 3 == 0 else "SECONDARY",
                "bci90": round(
                    float(p.get("expected_goal_involvement_per_90", 0)) * 1.5, 2
                ),
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
                -5:
            ][::-1],  # Reverse to have Most Recent First (Last 5 GWs)
            "ep": el.get("ep_this"),
            # "price_trend": get_price_trend(el),
            # "set_piece_role": "PRIMARY" if el["id"] % 3 == 0 else "SECONDARY",
            "bci90": round(
                float(el.get("expected_goal_involvement_per_90", 0)) * 1.5, 2
            ),
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
                    "time": fixture.get("kickoff_time"),
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
                    "time": fixture.get("kickoff_time"),
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
        week_fixtures = {}

        for f in fixtures:
            gw = f["gw"]
            gw_counts[gw] = gw_counts.get(gw, 0) + 1

            if f.get("time"):
                try:
                    dt_str = f["time"].replace("Z", "+00:00")
                    dt = datetime.fromisoformat(dt_str)
                    iso = dt.isocalendar()
                    week_key = f"{iso[0]}-W{iso[1]}"

                    if week_key not in week_fixtures:
                        week_fixtures[week_key] = []
                    week_fixtures[week_key].append(f)
                except (ValueError, ImportError):
                    pass

        # Standard FPL "Same Gameweek ID" Check
        for gw, count in gw_counts.items():
            if count > 1:
                schedule_notes.append(
                    f"FPL DGW ALERT: {team_name} has {count} fixtures in Gameweek {gw}"
                )
        # Calendar Week Check (The User's Request)
        for week_key, week_fix_list in week_fixtures.items():
            if len(week_fix_list) > 1:
                # Determine context
                first_game_dt = datetime.fromisoformat(
                    week_fix_list[0]["time"].replace("Z", "+00:00")
                )
                date_str = first_game_dt.strftime("%d %b")
                opponents = ", ".join(
                    [f"{fx['opp']} (GW{fx['gw']})" for fx in week_fix_list]
                )

                # Check if this "Double Week" starts with the team's immediately next game
                is_upcoming = fixtures and week_fix_list[0] == fixtures[0]

                prefix = (
                    "🚨 UPCOMING CALENDAR DGW"
                    if is_upcoming
                    else "⚠️ FUTURE CALENDAR DGW"
                )

                note = f"{prefix}: {team_name} plays {len(week_fix_list)} times in week of {date_str} [{opponents}]"

                # Avoid duplicate generic notes if strings overlap (unluckily)
                if note not in schedule_notes:
                    schedule_notes.append(note)

    dgw_bgw_str = (
        "\n" + "\n".join(f"  - {note}" for note in schedule_notes)
        if schedule_notes
        else "None"
    )
    fixtures_sum_str = json.dumps(fixtures_by_team, separators=(",", ":"))

    # Chip Strategy
    history = data.get("history", {})
    chips_history = history.get("chips", [])
    next_gw = data.get("next_gw", 2)

    remaining_chips = []

    # User confirms ALL chips reset in GW20 (2026 Season Rules / FPL Update)
    # We use next_gw (the one we are planning for) to check availability.

    all_chip_types = ["wildcard", "freehit", "bboost", "3xc"]

    for chip_type in all_chip_types:
        # Find all times this chip was used
        usages = [c for c in chips_history if c["name"] == chip_type]

        if next_gw < 20:
            # First Half Strategy (GW 1-19): Available if never used
            if not usages:
                remaining_chips.append(chip_type)
        else:
            # Second Half Strategy (GW 20+):
            # Check if used IN THE SECOND HALF (GW >= 20)
            used_in_2nd_half = any(c["event"] >= 20 for c in usages)

            if not used_in_2nd_half:
                remaining_chips.append(chip_type)

    chips_str = (
        json.dumps(remaining_chips, separators=(",", ":"))
        if remaining_chips
        else "None"
    )

    bank = data["team"].get("last_deadline_bank", 0) / 10
    squad_value = data["team"].get("last_deadline_value", 1000) / 10
    free_transfers = 1  # Approximate, API limited

    team_str = json.dumps(
        {
            "rank": data["team"].get("summary_overall_rank"),
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

### TEAM CONSTRAINT (CRITICAL):
**CRITICAL RULE**: You CANNOT have more than 3 players from the same team in your 15-man squad!

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
**DEFAULT STATE**: If Rank is `null` or unknown, default to **BALANCED** mode.
All decisions MUST align with this mode and label risk level.

### CAPTAINCY-FIRST PLANNING (CRITICAL):
Before transfers, identify the best captaincy options for the next 3 GWs.
1. Identify the optimal captain from the *current* squad.
2. Identify if any *outside* player offers a Captaincy EV improvement > 2.0 points over the current best.
3. If yes, prioritize transter. If no, proceed to 'Rising Star' identification.

### RUTHLESS FLOP & RISING STAR IDENTIFICATION (STRICT THRESHOLDS):
**CRITICAL**: You MUST analyze `recent_pts` for **EVERY SINGLE PLAYER** in the current squad. Do not skip anyone.

For each player, calculate:
- **Last 3 GWs Total**: Sum of the first 3 values in `recent_pts` array
- **Last 4 GWs Total**: Sum of the first 4 values in `recent_pts` array

Apply these strict rules:

- **FLOPS (SELL IMMEDIATELY)**:
    - **Condition A**: Last 3 GWs total ≤ 6 points
    - **Condition B**: Last 4 GWs total ≤ 8 points
    - **TRIGGER**: If EITHER Condition A OR Condition B is met, the player is a FLOP
    - **SUSTAINABILITY CHECK**: If `xgi90` > 0.4 despite low points, flag as "UNLUCKY - HOLD" instead of FLOP.
    - **EXAMPLE**: Player with recent_pts [1, 1, -1, 18, 5]:
        - Last 3 GWs = 1 + 1 + (-1) = 1 point ≤ 6 → **FLOP** (Condition A met)
        - Last 4 GWs = 1 + 1 + (-1) + 18 = 19 points > 8 → Not FLOP by Condition B
        - **RESULT**: FLOP because Condition A is met (recent form is terrible)

- **RISING STARS (MUST BUY)**:
    - **Condition A**: Last 3 GWs total ≥ 18 points
    - **Condition B**: Last 4 GWs total ≥ 24 points
    - **Condition C** (Explosive Potential): Form > 6.0 AND `xgi90` > 0.60
    - **TRIGGER**: If ANY of these conditions is met, the player is a RISING STAR
    - **SUSTAINABILITY CHECK**: If `xgi90` < 0.2 despite high points, flag as "FLUKE - AVOID".

- **NO EXCUSES**: If a player is a FLOP (and not Unlucky), sell them immediately even for a hit.
- **MANDATORY REPORTING**: In your "Transfer Recommendations" section, you MUST explicitly list ALL players who meet FLOP criteria, even if you don't recommend selling them (explain why if holding).

### TRANSFER DISCIPLINE & AGGRESSIVE HIT AUTHORIZATION:
- **FREE TRANSFERS**: You have {free_transfers} free transfer(s).
- **AUTHORIZATION FOR MULTIPLE HITS**: You are **STRONGLY AUTHORIZED** to suggest **multiple transfers involving hits (-4, -8, -12 or even -16)**.

- **HIT RECOVERY FORMULA (MANDATORY)**:
    - Calculate `EV_New` - `EV_Old` = `EV_Delta`.
    - Do not recommend a hit unless - `(Points Cost of Hit) / EV_Delta <= 2.0`.
    - *Example*: A -8 hit requires an improvement of 4.0 points per week to pay off in 2 weeks.

- **STRATEGY**: It is mathematically better to take a -8 hit and score 50 points (Net 42) than to save free transfers and score 35 points.

- **PRICE TRENDING RULES**:
    - **Cash Trap**: If selling a Falling player (-0.1m) results in being 0.1m short of a target Rising player (+0.1m), **WAIT** until price update completes.
    - **Value Preservation**: If a player is a FLOP and `price_trend` is "FALLING (-)", sell **immediately** (even if you can't afford a direct upgrade) to bank the higher sell-on price.

- **SHORT-TERM INJURY EXCEPTION**:
  - If an injured player is expected back in ≤ 1 GW (`return_gw`) OR has a confirmed Double Gameweek (DGW) in the alerts, DO NOT SELL. Mark as 'HOLD'.

### PERFORMANCE ANALYSIS & PREDICTION:
- **Sustainable Rise**: `form` > `ppg` AND `xgi90` is high (The perfect buy).
- **Explosive Differentials**: High `xgi90` / `xgc90` but low total points (The sneaky buy).
- **Sustainable Decline**: `form` >  < `ppg` AND `xgi90` is low (The perfect sell).
- **Minutes Trend**:
    - Prioritize players with increasing `starts`.
    - A player is 'RISKY' if starts < 2 in the last 3 GWs OR `news` contains 'missing training'.
    - A player is 'UNRELIABLE' if minutes are trending down (e.g. 90 -> 45 -> 20).

### CAPTAINCY SIMULATION:
Simulate the top 3 captaincy paths for the next 3 GWs. Choose the one with the highest ceiling.
- **Explosiveness Metric**: In AGGRESSIVE mode, prioritize high `xgi90` or Big Change Involvement over safe `ep_this`.

### ADVANCED STATS UTILIZATION:
Use ICT Index to validate decisions:
- High ICT + Low Points = Teammates finishing poorly or bad luck. Keep/Buy.
- Low ICT + High Points = "Points from Nothing" (Unsustainable). Sell High.

### FIXTURE WINDOW ANALYSIS:
- **Quantify the Swing**: Define a 'Good Swing' as a drop in average FDR (Fixture Difficulty Rating) of > 1.0 over the next 3 GWs compared to the previous 3.
- Prefer early entry into strong runs and timely exits before difficulty spikes.
- Label players as BUY NOW / HOLD / SELL SOON.

### OWNERSHIP HEURISTICS:
Infer ownership archetypes (high / medium / low EO).
In AGGRESSIVE mode, prioritize low-EO differentials with upside.

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
- Consider if any injured players have an upcoming DGW or return in < 1 week.

---

## 3. Captaincy Outlook (Next 3 GWs)
Rank top captain and vice-captain options from the squad.
Explain upside, fixture quality, and minutes security.
- If Aggressive mode, justify selection based on `bci90` or `xgi90` ceilings.

---

## 4. Transfer Recommendations
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
Select optimal formation based on FIXTURE DIFFICULTY, not just "Template 3-4-3".
- **DYNAMIC FORMATION**:
    - If your 4th defender has a cleaner sheet probability (e.g. Home vs Relegation Candidate) than your 5th midfielder/3rd forward (e.g. Away vs Top 4), **SWITCH to a 4-at-the-back or 5-at-the-back formation**.
    - Do not blindly force a 3-4-3. Points are points. A defender with a 40% CS chance > An attacker with < 30% return chance.
- **TEAM LOCK RULE**: Avoid starting 3 players from the same team unless the fixture is 'Easy' (FDR ≤ 2).
- **Bench Optimization**: Order bench by highest expected points. Bench players from teams with earlier kick-offs if unsure of lineup.
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
Transfers | Hits | Captain | Formation | Key Risk | Expected Outcome

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

    return response.choices[0].message.content, data["next_gw"]
