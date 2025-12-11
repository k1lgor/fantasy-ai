# FPL AI Assistant 🏆

Intelligent FPL manager tool using **GPT-4o** for optimal squads, transfers & insights. Automatically tracks injuries, analyzes fixture difficulty over 5 gameweeks, and provides specific, actionable transfer recommendations.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://fantasy-ai.streamlit.app)

## ✨ Features

- **Live FPL data** with injury tracking and availability status
- **5-Game Fixture Analysis** - Analyzes next 5 fixtures per team with difficulty ratings
- **Injury & Availability Report** - Automatic detection of injured/doubtful players with urgency levels
- **Potential Replacements** - Specific ranked alternatives for each position with fixture analysis
- **Optimized 15-Man Squad** (Based on Current Squad Only)
- **Captain & Vice-Captain** recommendations
- **Best Starting XI** with optimal formation
- **Bench Order** prioritization
- **Transfer Recommendations (0–5 Moves)** - Prioritizes injuries and fixture difficulty
- **Key Insights** - Form, fixtures, rotation risks, and structural analysis
- **Streamlit UI** (sidebar settings, download MD)

## 🧠 How It Works

### Injury Tracking

- Automatically detects injured, doubtful, and unavailable players in your squad
- Provides status codes (available, doubtful, injured, unavailable, suspended)
- Shows chance of playing percentages and latest injury news
- Assigns urgency levels: Critical, High, Medium, Low

### Fixture Analysis

- Fetches and analyzes the **next 5 gameweeks** of fixtures
- Calculates difficulty ratings for each opponent (1=easiest, 5=hardest)
- Considers home/away advantage in recommendations
- Prioritizes players with favorable fixture runs

### Transfer Recommendations

The AI prioritizes transfers based on:

1. **Injury Status** (most important)
2. **Next 5 Fixtures** (difficulty analysis)
3. Recent form (last 5 gameweeks)
4. Expected minutes and rotation risk
5. Goals, assists, clean sheets
6. Price per million value

### Replacement Suggestions

For each position (GK, DEF, MID, FWD), the AI provides:

- Top 10 players ranked by form
- Specific alternatives for injured/underperforming players
- Price comparisons and budget impact
- Fixture difficulty analysis for each option

## 🚀 Quick Start (Local)

1. **Clone**

```
git clone https://github.com/k1lgor/fantasy-ai.git
cd fantasy-ai
```

2. **Install (uv recommended)**

```
uv venv
uv pip install -r requirements.txt
```

3. **API Key**

```
cp .env.example .env
# Add OPENAI_API_KEY=sk-...
```

4. **Run**

```
uv run streamlit run app.py
```

5. **Use**

- Team ID: **6589598** (default)
- Generate → Copy recs

## ☁️ Deploy to Streamlit Cloud

1. Push to **GitHub** (all files)
2. [share.streamlit.io](https://share.streamlit.io) → New app → GitHub repo
3. **Settings** → Advanced → Secrets:

```
OPENAI_API_KEY = sk-your-key
```

4. App live! Share URL.

## 📱 UI

- Sidebar: Team ID, GPT model (4o/mini)
- Generate button → Markdown recs + download/code

## 🔧 Files

- [`app.py`](app.py) - Streamlit UI
- [`fpl_data.py`](fpl_data.py) - FPL API
- [`analyzer.py`](analyzer.py) - GPT prompts/data summary
- [`requirements.txt`](requirements.txt) - Deps

## 🛠 Customize

- Prompts: `analyzer.py`
- Data: `fpl_data.py`
- UI: `app.py`

## ⚠️ Limits

- OpenAI costs (~$0.01/use)
- FPL API rate limits
- AI suggestions, verify!

## Example Output

See [DEMO.md](DEMO.md)
