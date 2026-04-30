import streamlit as st
import requests
import time
import json
import os
from dotenv import load_dotenv

load_dotenv(override=True)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="System Status - SQLMind",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
/* Base theme overrides */
.stApp { background-color: #11111b; color: #cdd6f4; font-family: 'Inter', sans-serif; }
[data-testid="stSidebar"] { background-color: #0b0e15 !important; border-right: 1px solid #1e1e2e; }
[data-testid="stSidebar"] * { color: #a6adc8; }
h1, h2, h3, h4 { color: #cdd6f4 !important; }

/* Hide default streamlit menu */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

/* Status cards */
.status-card {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
}
.status-operational { border-left: 4px solid #a6e3a1; }
.status-degraded { border-left: 4px solid #fab387; }
.status-outage { border-left: 4px solid #f38ba8; }

.status-title { font-size: 18px; font-weight: 600; margin-bottom: 4px; }
.status-subtitle { font-size: 13px; color: #a6adc8; }
.status-badge { float: right; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; }

.badge-op { background: rgba(166, 227, 161, 0.2); color: #a6e3a1; border: 1px solid #a6e3a1; }
.badge-deg { background: rgba(250, 179, 135, 0.2); color: #fab387; border: 1px solid #fab387; }
.badge-out { background: rgba(243, 139, 168, 0.2); color: #f38ba8; border: 1px solid #f38ba8; }

.model-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #313244; }
.model-row:last-child { border-bottom: none; }
</style>
""", unsafe_allow_html=True)

API_BASE = os.getenv("API_URL", "http://localhost:8000")

st.title("📊 System Status")
st.caption("Real-time diagnostics of SQLMind components and upstream OpenRouter models.")
st.divider()

# Check Backend API
api_status = "outage"
db_status = "outage"
chroma_status = "outage"
indexed_tables = 0

try:
    res = requests.get(f"{API_BASE}/health", timeout=5)
    res.raise_for_status()
    data = res.json()
    api_status = "operational"
    if data.get("database"):
        db_status = "operational"
    if data.get("chroma_tables_indexed", 0) > 0:
        chroma_status = "operational"
        indexed_tables = data.get("chroma_tables_indexed")
except Exception:
    pass

# Status Summary
overall_status = "operational"
if api_status == "outage" or db_status == "outage":
    overall_status = "outage"
elif chroma_status == "outage":
    overall_status = "degraded"

if overall_status == "operational":
    st.markdown("""
    <div style="background-color: rgba(166, 227, 161, 0.1); border: 1px solid #a6e3a1; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 30px;">
        <h2 style="color: #a6e3a1 !important; margin: 0;">✅ All Core Systems Operational</h2>
    </div>
    """, unsafe_allow_html=True)
elif overall_status == "degraded":
    st.markdown("""
    <div style="background-color: rgba(250, 179, 135, 0.1); border: 1px solid #fab387; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 30px;">
        <h2 style="color: #fab387 !important; margin: 0;">⚠️ Degraded Performance</h2>
        <p style="color: #fab387; margin-top: 5px;">Some non-critical systems are offline.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="background-color: rgba(243, 139, 168, 0.1); border: 1px solid #f38ba8; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 30px;">
        <h2 style="color: #f38ba8 !important; margin: 0;">❌ Partial System Outage</h2>
        <p style="color: #f38ba8; margin-top: 5px;">Critical components are currently offline.</p>
    </div>
    """, unsafe_allow_html=True)

col1, col2 = st.columns([1, 1.2])

with col1:
    st.markdown("###  Core Infrastructure")
    
    # API Backend
    badge_class = "badge-op" if api_status == "operational" else "badge-out"
    border_class = "status-operational" if api_status == "operational" else "status-outage"
    status_text = "Operational" if api_status == "operational" else "Offline"
    st.markdown(f"""
    <div class="status-card {border_class}">
        <span class="status-badge {badge_class}">{status_text}</span>
        <div class="status-title">FastAPI Backend</div>
        <div class="status-subtitle">Routing, LLM chain, and execution engine</div>
    </div>
    """, unsafe_allow_html=True)

    # SQLite DB
    badge_class = "badge-op" if db_status == "operational" else "badge-out"
    border_class = "status-operational" if db_status == "operational" else "status-outage"
    status_text = "Operational" if db_status == "operational" else "Offline"
    st.markdown(f"""
    <div class="status-card {border_class}">
        <span class="status-badge {badge_class}">{status_text}</span>
        <div class="status-title">Database Connection</div>
        <div class="status-subtitle">SQLite datasource connection active</div>
    </div>
    """, unsafe_allow_html=True)

    # ChromaDB
    badge_class = "badge-op" if chroma_status == "operational" else "badge-deg"
    border_class = "status-operational" if chroma_status == "operational" else "status-degraded"
    status_text = "Operational" if chroma_status == "operational" else "Empty / Offline"
    st.markdown(f"""
    <div class="status-card {border_class}">
        <span class="status-badge {badge_class}">{status_text}</span>
        <div class="status-title">Schema Vector Store</div>
        <div class="status-subtitle">{indexed_tables} tables currently indexed in ChromaDB</div>
    </div>
    """, unsafe_allow_html=True)


with col2:
    st.markdown("###  AI Model Availability (OpenRouter)")
    st.markdown("""
    <div class="status-card" style="border-left: 4px solid #89b4fa; padding: 20px;">
        <div class="status-title" style="margin-bottom: 12px; color: #89b4fa;">Fallback Chain Health</div>
        <div class="status-subtitle" style="margin-bottom: 20px;">The agent automatically tries these models in order.</div>
        <div id="model-list">
    """, unsafe_allow_html=True)

    FREE_MODEL_CHAIN = [
        "nvidia/nemotron-3-super-120b-a12b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-3-27b-it:free",
        "google/gemma-4-31b-it:free",
        "nousresearch/hermes-3-llama-3.1-405b:free",
        "meta-llama/llama-3.2-3b-instruct:free",
    ]

    with st.spinner("Pinging upstream AI models..."):
        for model in FREE_MODEL_CHAIN:
            model_status = "operational"
            status_reason = "Operational"
            
            try:
                payload = json.dumps({
                    "model": model, 
                    "messages": [{"role": "user", "content": "ping"}], 
                    "max_tokens": 1
                })
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                }
                r = requests.post("https://openrouter.ai/api/v1/chat/completions", data=payload, headers=headers, timeout=5)
                
                if r.status_code == 429:
                    model_status = "rate-limited"
                    status_reason = "Rate Limited"
                elif r.status_code == 404:
                    model_status = "offline"
                    status_reason = "Not Found"
                elif r.status_code >= 500:
                    model_status = "offline"
                    status_reason = "Provider Outage"
                else:
                    r.raise_for_status()
                    
            except Exception as e:
                model_status = "offline"
                status_reason = "Timeout/Error"
                
            badge = ""
            if model_status == "operational":
                badge = f'<span class="status-badge badge-op" style="margin:0;">Operational</span>'
            elif model_status == "rate-limited":
                badge = f'<span class="status-badge badge-deg" style="margin:0;">Rate Limited</span>'
            else:
                badge = f'<span class="status-badge badge-out" style="margin:0;">{status_reason}</span>'
                
            st.markdown(f"""
            <div class="model-row">
                <span style="font-family: 'Inter', monospace; font-size: 13px; font-weight: 600; color: #b4befe;">{model}</span>
                {badge}
            </div>
            """, unsafe_allow_html=True)
            
    st.markdown("</div></div>", unsafe_allow_html=True)
