import streamlit as st

conn = st.session_state["conn"]


@st.cache_data(ttl=300)
def load_portfolio_summary():
    return conn.query("""
        SELECT
            COUNT(*) AS total_customers,
            SUM(TOTAL_POLICIES) AS total_policies,
            SUM(ACTIVE_POLICIES) AS active_policies,
            SUM(TOTAL_ANNUAL_PREMIUM) AS total_premium,
            SUM(TOTAL_CLAIMS) AS total_claims,
            SUM(OPEN_CLAIMS) AS open_claims,
            SUM(TOTAL_CLAIM_AMOUNT) AS total_claim_amount,
            SUM(TOTAL_APPROVED_AMOUNT) AS total_approved,
            AVG(CUSTOMER_TENURE_MONTHS) AS avg_tenure,
            SUM(CASE WHEN HAS_FRAUD_FLAG THEN 1 ELSE 0 END) AS fraud_flagged
        FROM INSURE360_APP.ANALYTICS.DT_CUSTOMER_360
    """)


@st.cache_data(ttl=300)
def load_segment_distribution():
    return conn.query("""
        SELECT CUSTOMER_SEGMENT AS "Segment", COUNT(*) AS "Customers",
               SUM(TOTAL_ANNUAL_PREMIUM) AS "Premium",
               SUM(TOTAL_CLAIMS) AS "Claims"
        FROM INSURE360_APP.ANALYTICS.DT_CUSTOMER_360
        GROUP BY 1 ORDER BY 2 DESC
    """)


@st.cache_data(ttl=300)
def load_city_distribution():
    return conn.query("""
        SELECT CITY AS "City", COUNT(*) AS "Customers"
        FROM INSURE360_APP.ANALYTICS.DT_CUSTOMER_360
        WHERE CITY IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10
    """)


@st.cache_data(ttl=300)
def load_policy_mix():
    return conn.query("""
        SELECT POLICY_TYPE AS "Policy Type", COUNT(*) AS "Count", SUM(ANNUAL_PREMIUM) AS "Premium"
        FROM INSURE360_APP.INTERFACE.V_POLICIES
        WHERE POLICY_STATUS = 'ACTIVE'
        GROUP BY 1 ORDER BY 2 DESC
    """)


@st.cache_data(ttl=300)
def load_claims_by_status():
    return conn.query("""
        SELECT CLAIM_STATUS AS "Status", COUNT(*) AS "Count"
        FROM INSURE360_APP.INTERFACE.V_CLAIMS
        GROUP BY 1
    """)


st.header("Executive Dashboard")

if st.button("Refresh", icon=":material/refresh:"):
    st.cache_data.clear()

# ── Portfolio KPIs ──
summary = load_portfolio_summary()
if not summary.empty:
    s = summary.iloc[0]
    with st.container(horizontal=True):
        st.metric("Total Customers", f"{int(s['TOTAL_CUSTOMERS']):,}", border=True)
        st.metric("Active Policies", f"{int(s['ACTIVE_POLICIES']):,}", border=True)
        st.metric("Annual Premium", f"₹{float(s['TOTAL_PREMIUM'] or 0):,.0f}", border=True)
        st.metric("Open Claims", f"{int(s['OPEN_CLAIMS']):,}", border=True)
        st.metric("Fraud Flagged", f"{int(s['FRAUD_FLAGGED']):,}", border=True)
    with st.container(horizontal=True):
        st.metric("Total Policies", f"{int(s['TOTAL_POLICIES']):,}", border=True)
        st.metric("Total Claims", f"{int(s['TOTAL_CLAIMS']):,}", border=True)
        st.metric("Claim Amount", f"₹{float(s['TOTAL_CLAIM_AMOUNT'] or 0):,.0f}", border=True)
        st.metric("Approved Amount", f"₹{float(s['TOTAL_APPROVED'] or 0):,.0f}", border=True)
        st.metric("Avg Tenure", f"{float(s['AVG_TENURE'] or 0):.0f} months", border=True)

st.divider()

# ── Charts Row 1 ──
g1, g2 = st.columns(2)
with g1:
    with st.container(border=True):
        st.subheader("Customers by Segment")
        seg = load_segment_distribution()
        if not seg.empty:
            st.bar_chart(seg, x="Segment", y="Customers", color="Segment")

with g2:
    with st.container(border=True):
        st.subheader("Top 10 Cities")
        city = load_city_distribution()
        if not city.empty:
            st.bar_chart(city, x="City", y="Customers", horizontal=True)

# ── Charts Row 2 ──
g3, g4 = st.columns(2)
with g3:
    with st.container(border=True):
        st.subheader("Premium by Segment")
        seg = load_segment_distribution()
        if not seg.empty:
            st.bar_chart(seg, x="Segment", y="Premium", color="Segment")

with g4:
    with st.container(border=True):
        st.subheader("Claims by Status")
        df_claims = load_claims_by_status()
        if not df_claims.empty:
            st.bar_chart(df_claims, x="Status", y="Count")

# ── Charts Row 3 ──
g5, g6 = st.columns(2)
with g5:
    with st.container(border=True):
        st.subheader("Active Policy Mix")
        df_mix = load_policy_mix()
        if not df_mix.empty:
            st.bar_chart(df_mix, x="Policy Type", y="Count")

with g6:
    with st.container(border=True):
        st.subheader("Premium by Policy Type")
        df_mix = load_policy_mix()
        if not df_mix.empty:
            st.bar_chart(df_mix, x="Policy Type", y="Premium")


