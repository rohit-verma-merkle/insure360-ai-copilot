import streamlit as st
import os

st.set_page_config(
    page_title="Insure 360 by AI",
    page_icon=":material/shield:",
    layout="wide",
)

st.markdown("""
<style>
    /* ── Typography ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"], .stMarkdown, .stText {
        font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    }

    /* ── Layout ── */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F172A 0%, #1E293B 100%);
    }
    [data-testid="stSidebar"] * {
        color: #CBD5E1 !important;
    }
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3,
    [data-testid="stSidebar"] .stMarkdown strong {
        color: #F1F5F9 !important;
    }

    /* ── Page Headers ── */
    h1 {
        font-weight: 700 !important;
        font-size: 1.75rem !important;
        color: #0F172A !important;
        letter-spacing: -0.025em;
    }
    h2 {
        font-weight: 600 !important;
        font-size: 1.25rem !important;
        color: #1E293B !important;
        letter-spacing: -0.01em;
    }
    h3 {
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        color: #334155 !important;
    }

    /* ── Metric Cards ── */
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px 18px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    [data-testid="stMetric"] label {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        color: #64748B !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
    }

    /* ── Containers / Cards ── */
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
        border-color: #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* ── Tables / DataFrames ── */
    [data-testid="stDataFrame"] th {
        background-color: #F1F5F9 !important;
        color: #334155 !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    /* ── Buttons ── */
    .stButton button[kind="primary"] {
        background: #2563EB;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.85rem;
        padding: 0.5rem 1.25rem;
        transition: all 0.2s ease;
    }
    .stButton button[kind="primary"]:hover {
        background: #1D4ED8;
        box-shadow: 0 4px 12px rgba(37,99,235,0.3);
    }
    .stButton button[kind="secondary"] {
        border-radius: 8px;
        font-weight: 500;
        border-color: #CBD5E1;
    }

    /* ── Selectbox ── */
    [data-testid="stSelectbox"] > div {
        border-radius: 8px;
    }

    /* ── Expanders ── */
    [data-testid="stExpander"] {
        border-radius: 10px;
        border-color: #E2E8F0;
    }
    [data-testid="stExpander"] summary {
        font-weight: 500;
        color: #475569;
    }

    /* ── Dividers ── */
    hr {
        border-color: #E2E8F0 !important;
        margin: 1rem 0 !important;
    }

    /* ── Pills / Chips ── */
    [data-testid="stPills"] button {
        border-radius: 20px !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
    }

    /* ── Info / Warning / Success boxes ── */
    [data-testid="stAlert"] {
        border-radius: 8px;
        font-size: 0.88rem;
    }

    /* ── Charts ── */
    [data-testid="stVegaLiteChart"] {
        border-radius: 8px;
    }

    /* ── Caption styling ── */
    .stCaption, [data-testid="stCaption"] {
        color: #64748B !important;
        font-size: 0.82rem !important;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #F1F5F9; }
    ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
</style>
""", unsafe_allow_html=True)

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
st.session_state["conn"] = conn

# ── Detect current Snowflake role ──
if "current_role" not in st.session_state:
    role_result = conn.query("SELECT CURRENT_ROLE() AS ROLE")
    st.session_state["current_role"] = role_result["ROLE"].iloc[0]

current_role = st.session_state["current_role"]

# ── Role → Display name mapping ──
ROLE_DISPLAY = {
    "ACCOUNTADMIN":              "Platform Administrator",
    "INSURE360_ADMIN":           "Platform Administrator",
    "INSURE360_DATA_ENGINEER":   "Data Engineer",
    "INSURE360_SALES_ADVISOR":   "Sales Advisor",
    "INSURE360_CLAIMS_PROCESSOR":"Claims Processor",
    "INSURE360_UNDERWRITER":     "Underwriter",
    "INSURE360_RETENTION_MGR":   "Retention Manager",
    "INSURE360_CC_MANAGER":      "Contact Center Manager",
    "INSURE360_VIEWER":          "Viewer",
}

# ── All available pages ──
ALL_PAGES = {
    "executive_dashboard": st.Page("app_pages/executive_dashboard.py", title="Executive Dashboard", icon=":material/dashboard:"),
    "customer_360":        st.Page("app_pages/customer_360.py",        title="Customer 360",        icon=":material/person_search:"),
    "ai_insights":         st.Page("app_pages/ai_insights.py",         title="AI Insight Center",   icon=":material/psychology:"),
    "claims_intelligence": st.Page("app_pages/claims_intelligence.py", title="Claims Intelligence", icon=":material/gavel:"),
    "recommendations":     st.Page("app_pages/recommendations.py",     title="Recommendations",     icon=":material/rocket_launch:"),
    "integration_config":  st.Page("app_pages/integration_config.py",  title="Integration Config",  icon=":material/settings:"),
    "role_config":         st.Page("app_pages/role_config.py",         title="Role Configuration",  icon=":material/admin_panel_settings:"),
}

# ── Role → Authorized pages ──
# Each role gets a specific set of pages they can access.
#
# ── Role → Page access (table-driven with fallback) ──
# Reads from INSURE360_APP.CONFIG.ROLE_PAGE_ACCESS table.
# Falls back to hardcoded defaults if the table is empty or inaccessible.

FALLBACK_ROLE_PAGE_ACCESS = {
    "ACCOUNTADMIN":              ["executive_dashboard", "customer_360", "claims_intelligence", "recommendations", "integration_config"],
    "INSURE360_ADMIN":           ["executive_dashboard", "customer_360", "claims_intelligence", "recommendations", "integration_config"],
    "INSURE360_DATA_ENGINEER":   ["executive_dashboard", "customer_360", "claims_intelligence", "recommendations", "integration_config"],
    "INSURE360_SALES_ADVISOR":   ["executive_dashboard", "customer_360", "recommendations"],
    "INSURE360_CLAIMS_PROCESSOR":["customer_360", "claims_intelligence"],
    "INSURE360_UNDERWRITER":     ["executive_dashboard", "customer_360", "claims_intelligence"],
    "INSURE360_RETENTION_MGR":   ["executive_dashboard", "customer_360", "recommendations"],
    "INSURE360_CC_MANAGER":      ["executive_dashboard", "customer_360"],
    "INSURE360_VIEWER":          ["executive_dashboard"],
}

@st.cache_data(ttl=60)
def load_role_page_access():
    try:
        df = conn.query("""
            SELECT ROLE_NAME, PAGE_KEY
            FROM INSURE360_APP.CONFIG.ROLE_PAGE_ACCESS
            ORDER BY ROLE_NAME, PAGE_KEY
        """)
        if df.empty:
            return FALLBACK_ROLE_PAGE_ACCESS
        mapping = {}
        for _, row in df.iterrows():
            role = row["ROLE_NAME"]
            page = row["PAGE_KEY"]
            if role not in mapping:
                mapping[role] = []
            mapping[role].append(page)
        return mapping
    except Exception:
        return FALLBACK_ROLE_PAGE_ACCESS

ROLE_PAGE_ACCESS = load_role_page_access()

# PII visibility by role (used by pages that show sensitive data)
PII_ALLOWED_ROLES = {"ACCOUNTADMIN", "INSURE360_ADMIN", "INSURE360_CC_MANAGER", "INSURE360_SALES_ADVISOR"}

# ── Resolve mapped role if current role is not a native Insure360 role ──
effective_role = current_role
if current_role not in ROLE_PAGE_ACCESS:
    try:
        mapped = conn.query(
            "SELECT INSURE360_ROLE FROM INSURE360_APP.CONFIG.ROLE_MAPPING "
            "WHERE SOURCE_ROLE = ? AND IS_ACTIVE = TRUE LIMIT 1",
            params=[current_role],
            ttl=120,
        )
        if not mapped.empty:
            effective_role = mapped.iloc[0]["INSURE360_ROLE"]
    except Exception:
        pass

st.session_state["effective_role"] = effective_role
st.session_state["pii_allowed"] = effective_role in PII_ALLOWED_ROLES

# ── Build navigation from authorized pages ──
allowed_keys = ROLE_PAGE_ACCESS.get(effective_role, ["executive_dashboard"])
allowed_pages = [ALL_PAGES[k] for k in allowed_keys if k in ALL_PAGES]

if not allowed_pages:
    st.error(f"Role **{current_role}** has no authorized pages. Contact your administrator.")
    st.stop()

# Group pages into navigation sections
section_map = {
    "executive_dashboard": "",
    "customer_360": "Customer Intelligence",
    "ai_insights": "Customer Intelligence",
    "claims_intelligence": "Operations",
    "recommendations": "Operations",
    "integration_config": "Administration",
    "role_config": "Administration",
}

SECTION_ORDER = ["", "Customer Intelligence", "Operations", "Administration"]
PAGE_ORDER = [
    "executive_dashboard", "customer_360", "ai_insights",
    "claims_intelligence", "recommendations",
    "integration_config", "role_config",
]

nav_sections = {s: [] for s in SECTION_ORDER}
for key in PAGE_ORDER:
    if key not in allowed_keys or key not in ALL_PAGES:
        continue
    section = section_map.get(key, "")
    nav_sections[section].append(ALL_PAGES[key])
nav_sections = {k: v for k, v in nav_sections.items() if v}

with st.sidebar:
    st.markdown("""
    <div style="padding:12px 12px 8px; text-align:center;">
        <div style="font-size:1.25rem; font-weight:700; color:#F1F5F9; letter-spacing:-0.02em;">
            &#x1F6E1;&#xFE0F; Insure 360 <span style="font-weight:400; color:#94A3B8;">by AI</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

page = st.navigation(nav_sections, position="sidebar")

# ── Sidebar: role info ──
with st.sidebar:
    st.divider()
    display_role = ROLE_DISPLAY.get(effective_role, effective_role)
    mapped_note = ""
    if effective_role != current_role:
        mapped_note = f'<div style="font-size:0.68rem; color:#94A3B8; margin-top:2px;">Mapped from: {current_role}</div>'
    st.markdown(f"""
    <div style="padding:8px 12px; background:rgba(255,255,255,0.05); border-radius:8px;">
        <div style="font-size:0.68rem; color:#94A3B8; text-transform:uppercase; letter-spacing:0.08em;">Role</div>
        <div style="font-size:0.82rem; color:#E2E8F0; font-weight:500;">{display_role}</div>
    </div>
    """, unsafe_allow_html=True)

page.run()
