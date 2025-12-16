import streamlit as st

from analyzer import generate_squad_recommendation

st.set_page_config(page_title="FPL AI Assistant", page_icon="⚽", layout="wide")

st.markdown(
    """
<style>
.main-header {font-size: 3rem; color: #1f77b4;}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<h1 class="main-header">⚽ FPL AI Assistant</h1>', unsafe_allow_html=True)
st.markdown("**GPT-5 powered squad suggestions | Live FPL data**")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    team_id = st.text_input(
        "Team ID",
        value="6589598",
        help="fantasy.premierleague.com/entry/{ID}",
    )
    model = st.selectbox("GPT Model", ["gpt-5.2", "gpt-5.1"])

    st.header("📖 Quick Start")
    st.markdown(
        """
    1. Enter FPL ID
    2. Click Generate (~20s)
    """
    )

st.header("🤖 Generate Recommendations")
col1, col2 = st.columns([4, 1])
if col1.button(
    "🎯 Analyze Squad", type="primary", use_container_width=False, key="generate"
):
    with st.spinner("Fetching FPL data & GPT analysis..."):
        try:
            recs = generate_squad_recommendation(team_id, model)
            st.session_state.recs = recs
            st.session_state.team_id = team_id
            st.success("✅ Complete!")
        except Exception as e:
            st.error(f"❌ {e}")
            if "OPENAI_API_KEY" in str(e):
                st.info("Set `OPENAI_API_KEY` in `.env`")

if "recs" in st.session_state:
    st.markdown("### 📊 AI Squad Recommendations")
    st.markdown(st.session_state.recs)

    col_d1, _ = st.columns(2)
    with col_d1:
        st.download_button(
            "💾 Download .md",
            data=st.session_state.recs,
            file_name=f"fpl_recs_team_{st.session_state.team_id}.md",
        )


st.markdown("---")
st.markdown("*BAHUR UTD*")
