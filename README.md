# FPL AI Assistant 🏆

Intelligent FPL manager tool using **GPT-4o** for optimal squads, transfers & insights.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://fantasy-ai.streamlit.app)

## ✨ Features
- **Live FPL data**
- **Optimized 15-Man Squad** (Based on Current Squad Only)
- **Captain & Vice-Captain**
- **Best Starting XI**
- **Bench Order**
- **Transfer Recommendations (0–3 Moves)**
- **Key Insights for This Squad**
- **Streamlit UI** (sidebar settings, download MD)

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
```
1. Optimized 15-Man Squad (Based on Current Squad Only)
- Raya — GK — ARS — £6.0 — 2.8: Reliable starter with potential for clean sheets.
- Dúbravka — GK — BUR — £4.0 — 2.0: Budget-friendly backup option.
- J. Timber — DEF — ARS — £6.5 — 2.4: Upgradeable due to form and price.
- Cucurella — DEF — CHE — £6.2 — 4.0: Consistent starter with attacking potential.
- Richards — DEF — CRY — £4.6 — 4.8: Good form and favorable fixtures.
- Gudmundsson — DEF — LEE — £3.9 — 1.4: Priority sell due to low form and points.
- Alderete — DEF — SUN — £4.1 — 1.0: Budget defender, but low form.
- Eze — MID — ARS — £7.8 — 5.2: High potential with attacking returns.
- Minteh — MID — BHA — £6.3 — 3.8: Upgradeable for better form options.
- B. Fernandes — MID — MUN — £9.0 — 4.4: Consistent performer with set-piece duties.
- Anderson — MID — NFO — £5.4 — 6.0: In good form and offers value.
- Semenyo — MID — BOU — £7.6 — 1.6: Priority sell due to poor form.
- Haaland — FWD — MCI — £15.0 — 4.8: Essential with high goal involvement.
- Thiago — FWD — BRE — £6.9 — 6.6: In form and offers good value.
- Mateta — FWD — CRY — £8.0 — 2.2: Upgradeable due to low form.

2. Captain & Vice-Captain
- Captain: Haaland — Strong goal-scoring form, secure minutes, favorable fixture.
- Vice-Captain: B. Fernandes — Consistent returns, set-piece duties, and good fixture.

3. Best Starting XI
Formation: 3-5-2

1. GK: Raya
2. DEF: Cucurella, Richards, Alderete
3. MID: Eze, B. Fernandes, Anderson, Minteh, Semenyo
4. FWD: Haaland, Thiago

4. Bench Order
1. Dúbravka: Backup keeper.
2. J. Timber: Rotation risk and low form.
3. Mateta: Low form and minutes.
4. Gudmundsson: Least likely to contribute.

5. Transfer Recommendations (0–3 Moves)
- Players Out: Semenyo, Gudmundsson
- Replacement Options:
    1. Saka (MID, ARS, £10.1): High form and attacking returns.
    2. Muñoz (DEF, CRY, £6.1): Excellent form and attacking potential.
- Net Cost: £0.0M (requires budget adjustment, consider downgrading another player)

6. Key Insights for This Squad
- Form Streaks: Anderson and Thiago are in good form.
- Fixture Clusters: Favorable fixtures for CRY and ARS players.
- Rotation Risks: J. Timber and Mateta have uncertain minutes.
- Injury Flags: Monitor any late injury news.
- Underpriced Assets: Anderson offers good value for his form.
- Structural Weakness: Defense needs strengthening; consider upgrading Gudmundsson.
```
