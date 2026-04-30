"""
SQLMind - Streamlit Conversational Frontend
"""

import json
import requests
import streamlit as st
import pandas as pd

API_BASE = "http://localhost:8000"

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SQLMind - AI Reasoning Engine",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS (Catppuccin & Glassmorphism) ────────────────────────────────────
st.markdown("""
<style>
/* Base theme overrides */
.stApp {
    background-color: #11111b;
    color: #cdd6f4;
    font-family: 'Inter', sans-serif;
}

/* Sidebar overrides */
[data-testid="stSidebar"] {
    background-color: #0b0e15 !important;
    border-right: 1px solid #1e1e2e;
}

[data-testid="stSidebar"] * {
    color: #a6adc8;
}

/* Headers */
h1, h2, h3, h4, h5, h6 {
    color: #cdd6f4 !important;
}

/* Chat Input */
[data-testid="stChatInput"] {
    background-color: #1e1e2e !important;
    border: 1px solid #313244 !important;
}

/* User Chat Message */
[data-testid="chatAvatarIcon-user"] {
    background-color: #89b4fa !important;
}

/* Assistant Chat Message */
[data-testid="chatAvatarIcon-assistant"] {
    background-color: #cba6f7 !important;
}

/* Buttons */
.stButton>button {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    transition: all 0.2s ease;
    border-radius: 8px;
}
.stButton>button:hover {
    background-color: #313244;
    border-color: #89b4fa;
    color: #89b4fa;
}
.stButton>button[kind="primary"] {
    background-color: #89b4fa;
    color: #11111b;
    border: none;
    font-weight: bold;
}
.stButton>button[kind="primary"]:hover {
    background-color: #b4befe;
    color: #11111b;
}

/* Expanders (used for SQL/Trace) */
.streamlit-expanderHeader {
    background-color: #1e1e2e !important;
    border-radius: 8px;
    border: 1px solid #313244;
    color: #cdd6f4 !important;
}
[data-testid="stExpanderDetails"] {
    border: 1px solid #313244;
    border-top: none;
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
    background-color: #181825;
}

/* Dataframe/Tables */
[data-testid="stDataFrame"] {
    background-color: #1e1e2e;
}

/* Trace Step Card */
.step-card {
    background: #1e1e2e;
    border: 1px solid #313244;
    border-left: 3px solid #89b4fa;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 10px;
}
.step-node { font-size: 13px; font-weight: 700; color: #cba6f7; margin-bottom: 4px; text-transform: uppercase; }
.step-label { color: #6c7086; font-size: 11px; text-transform: uppercase; font-weight: 600; margin-top: 8px; }
.step-text  { color: #cdd6f4; font-size: 13px; margin: 2px 0; }
.step-error { color: #f38ba8; font-size: 13px; margin: 2px 0; }

.success-badge { background: rgba(166, 227, 161, 0.2); color: #a6e3a1; border-radius: 4px; padding: 2px 8px; font-size: 12px; font-weight: 600; border: 1px solid #a6e3a1; }
.error-badge { background: rgba(243, 139, 168, 0.2); color: #f38ba8; border-radius: 4px; padding: 2px 8px; font-size: 12px; font-weight: 600; border: 1px solid #f38ba8; }
.retry-badge { background: rgba(250, 179, 135, 0.2); color: #fab387; border-radius: 4px; padding: 2px 8px; font-size: 12px; font-weight: 600; border: 1px solid #fab387; }

/* Hide main menu and footer */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "schema_tables" not in st.session_state:
    st.session_state.schema_tables = []
    # Try to fetch tables on startup
    try:
        res = requests.get(f"{API_BASE}/tables", timeout=5).json()
        st.session_state.schema_tables = res.get("tables", [])
    except:
        pass

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h2 style='color:#cdd6f4;'> SQLMind</h2>", unsafe_allow_html=True)
    st.caption("AI Reasoning Engine")
    
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    
    st.markdown("<h3 style='color:#cdd6f4;'>🗄️ Schema Context</h3>", unsafe_allow_html=True)
    if not st.session_state.schema_tables:
        if st.button("Refresh Schema", use_container_width=True):
            try:
                res = requests.get(f"{API_BASE}/tables", timeout=5).json()
                st.session_state.schema_tables = res.get("tables", [])
                st.rerun()
            except Exception as e:
                st.error("Could not reach API")
    else:
        # Display schema tables neatly
        with st.expander("Active Tables", expanded=True):
            for t in st.session_state.schema_tables:
                st.markdown(f"• `{t}`")
            
    st.divider()
    
    st.markdown("<h3 style='color:#cdd6f4;'>⚙️ Settings</h3>", unsafe_allow_html=True)
    api_url = st.text_input("API URL", value=API_BASE, label_visibility="collapsed")
    
    if st.button("🏥 Health Check", use_container_width=True):
        try:
            res = requests.get(f"{api_url}/health", timeout=5).json()
            if res["database"]:
                st.success("✅ Database connected")
            else:
                st.error("❌ Database unreachable")
        except Exception as e:
            st.error(f"API unreachable: {e}")

# ── Main Chat Interface ────────────────────────────────────────────────────────
# Top bar
st.markdown("<h2 style='text-align:center; color:#cdd6f4;'>SQLMind Dashboard</h2>", unsafe_allow_html=True)

# Empty State
if not st.session_state.messages:
    st.markdown("""
    <div style='text-align: center; margin-top: 80px; margin-bottom: 60px;'>
        <h1 style='color: #89b4fa; font-size: 3rem; font-weight: 700; margin-bottom: 10px;'>How can I help you explore your data?</h1>
        <p style='color: #a6adc8; font-size: 1.1rem;'>Ask questions about your SQLite database in plain English.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 Top Customers by Revenue", use_container_width=True):
            st.session_state.trigger_prompt = "Who are the top 5 customers by total invoice amount?"
            st.rerun()
    with col2:
        if st.button("🎵 Most Popular Genres", use_container_width=True):
            st.session_state.trigger_prompt = "Which genre has the most tracks?"
            st.rerun()
    with col3:
        if st.button("🌍 Revenue by Country", use_container_width=True):
            st.session_state.trigger_prompt = "Show total revenue by country."
            st.rerun()

# Display chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            # Assistant response card
            st.markdown(msg["content"], unsafe_allow_html=True)
            
            # Show Data Table
            if "data" in msg and msg["data"]:
                with st.expander("📊 Data Results", expanded=True):
                    df = pd.DataFrame(msg["data"])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "⬇ Download CSV",
                        data=csv,
                        file_name="query_result.csv",
                        mime="text/csv",
                        key=f"dl_history_{msg.get('id', 0)}"
                    )
                    
            # Show SQL code
            if "sql" in msg and msg["sql"]:
                with st.expander("💻 SQL Code", expanded=False):
                    st.code(msg["sql"], language="sql")
                    
            # Show reasoning trace expander
            if "steps" in msg and msg["steps"]:
                with st.expander(" Reasoning Trace", expanded=False):
                    for i, step in enumerate(msg["steps"]):
                        is_error = "❌" in step.get("observation", "")
                        is_retry = "retry" in step.get("node", "").lower()
                        color_class = "step-error" if is_error else "step-text"
                        st.markdown(f'''
                        <div class="step-card">
                            <div class="step-node">{"🔄 " if is_retry else ""}{i+1}. {step["node"]}</div>
                            <div class="step-label">Thought</div>
                            <div class="step-text">{step["thought"]}</div>
                            <div class="step-label">Action</div>
                            <div class="step-text">{step["action"]}</div>
                            <div class="step-label">Observation</div>
                            <div class="{color_class}">{step["observation"]}</div>
                        </div>
                        ''', unsafe_allow_html=True)

# ── Input Handling ─────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask a question about your data or type / for commands...")

if "trigger_prompt" in st.session_state and st.session_state.trigger_prompt:
    prompt = st.session_state.trigger_prompt
    st.session_state.trigger_prompt = None

if prompt:
    # Append user msg
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Render user msg immediately
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # Process assistant response
    with st.chat_message("assistant"):
        with st.spinner("SQLMind is thinking..."):
            try:
                response = requests.post(
                    f"{api_url}/query",
                    json={"question": prompt},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()
                
                # Render content
                content_prefix = ""
                if data["is_success"]:
                    if data["retry_count"] > 0:
                        content_prefix = f'<span class="retry-badge">🔄 Self-healed ({data["retry_count"]} retries)</span><br><br>'
                    else:
                        content_prefix = f'<span class="success-badge">✅ Success</span><br><br>'
                else:
                    content_prefix = f'<span class="error-badge">❌ Failed ({data["retry_count"]} retries)</span><br><br>'
                
                answer = data.get("final_answer", "Error generating answer.")
                
                # Display text
                st.markdown(content_prefix + answer, unsafe_allow_html=True)
                
                # Data Table
                if data.get("rows"):
                    with st.expander("📊 Data Results", expanded=True):
                        df = pd.DataFrame(data["rows"])
                        st.dataframe(df, use_container_width=True, hide_index=True)
                        csv = df.to_csv(index=False)
                        st.download_button(
                            "⬇ Download CSV",
                            data=csv,
                            file_name="query_result.csv",
                            mime="text/csv",
                            key=f"dl_new_{len(st.session_state.messages)}"
                        )
                
                # SQL Code
                if data.get("generated_sql"):
                    with st.expander("💻 SQL Code", expanded=False):
                        st.code(data["generated_sql"], language="sql")
                        
                # Reasoning Trace
                if data.get("steps"):
                    with st.expander(" Reasoning Trace", expanded=False):
                        for i, step in enumerate(data["steps"]):
                            is_error = "❌" in step.get("observation", "")
                            is_retry = "retry" in step.get("node", "").lower()
                            color_class = "step-error" if is_error else "step-text"
                            st.markdown(f'''
                            <div class="step-card">
                                <div class="step-node">{"🔄 " if is_retry else ""}{i+1}. {step["node"]}</div>
                                <div class="step-label">Thought</div>
                                <div class="step-text">{step["thought"]}</div>
                                <div class="step-label">Action</div>
                                <div class="step-text">{step["action"]}</div>
                                <div class="step-label">Observation</div>
                                <div class="{color_class}">{step["observation"]}</div>
                            </div>
                            ''', unsafe_allow_html=True)
                
                # Append to state
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": content_prefix + answer,
                    "sql": data.get("generated_sql"),
                    "data": data.get("rows"),
                    "steps": data.get("steps"),
                    "id": len(st.session_state.messages)
                })

            except requests.exceptions.ConnectionError:
                err_msg = "❌ Cannot reach the API. Make sure `uvicorn main:app` is running."
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
            except requests.exceptions.HTTPError as e:
                err_msg = f"❌ API error {response.status_code}: {response.json().get('detail', str(e))}"
                st.error(err_msg)
                st.session_state.messages.append({"role": "assistant", "content": err_msg})
