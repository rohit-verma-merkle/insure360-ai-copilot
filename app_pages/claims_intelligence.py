import streamlit as st

conn = st.session_state["conn"]

st.header("Claims Intelligence")


@st.cache_data(ttl=300)
def load_claims_kpis():
    return conn.query("""
        SELECT
            COUNT(*) AS total_claims,
            COUNT(CASE WHEN CLAIM_STATUS NOT IN ('SETTLED','CLOSED','REJECTED') THEN 1 END) AS open_claims,
            SUM(CLAIM_AMOUNT) AS total_claim_amount,
            SUM(APPROVED_AMOUNT) AS total_approved,
            AVG(DATEDIFF('DAY', CLAIM_DATE, COALESCE(SETTLEMENT_DATE, CURRENT_DATE()))) AS avg_days,
            COUNT(CASE WHEN CLAIM_STATUS = 'SETTLED' THEN 1 END) * 100.0
                / NULLIF(COUNT(*), 0) AS settlement_rate,
            COUNT(CASE WHEN FRAUD_FLAG IN ('Y','SUSPECT') THEN 1 END) AS fraud_alerts
        FROM INSURE360_APP.INTERFACE.V_CLAIMS
    """)


@st.cache_data(ttl=300)
def load_claims_pipeline():
    return conn.query("""
        SELECT CLAIM_STATUS AS "Status", COUNT(*) AS "Count", SUM(CLAIM_AMOUNT) AS "Total Amount"
        FROM INSURE360_APP.INTERFACE.V_CLAIMS
        GROUP BY 1 ORDER BY 2 DESC
    """)


@st.cache_data(ttl=300)
def load_claims_by_type():
    return conn.query("""
        SELECT CLAIM_TYPE AS "Claim Type", COUNT(*) AS "Count"
        FROM INSURE360_APP.INTERFACE.V_CLAIMS
        WHERE CLAIM_TYPE IS NOT NULL
        GROUP BY 1
    """)


@st.cache_data(ttl=300)
def load_fraud_claims():
    df = conn.query("""
        SELECT CLAIM_ID, CUSTOMER_ID, CLAIM_DATE, CLAIM_TYPE,
               CLAIM_AMOUNT, FRAUD_SCORE, CLAIM_STATUS, PRIORITY
        FROM INSURE360_APP.INTERFACE.V_CLAIMS
        WHERE FRAUD_FLAG IN ('Y','SUSPECT')
        ORDER BY FRAUD_SCORE DESC
        LIMIT 20
    """)
    if not df.empty:
        df = df.rename(columns={
            "CLAIM_ID": "Claim ID", "CUSTOMER_ID": "Customer ID",
            "CLAIM_DATE": "Claim Date", "CLAIM_TYPE": "Type",
            "CLAIM_AMOUNT": "Amount", "FRAUD_SCORE": "Fraud Score",
            "CLAIM_STATUS": "Status", "PRIORITY": "Priority",
        })
    return df


if st.button("Refresh", icon=":material/refresh:"):
    load_claims_kpis.clear()
    load_claims_pipeline.clear()
    load_claims_by_type.clear()
    load_fraud_claims.clear()

with st.spinner("Loading claims data..."):
    kpi = load_claims_kpis()

if not kpi.empty:
    row = kpi.iloc[0]
    with st.container(horizontal=True):
        st.metric("Total Claims", f"{int(row['TOTAL_CLAIMS']):,}", border=True)
        st.metric("Open Claims", f"{int(row['OPEN_CLAIMS']):,}", border=True)
        claim_amt = row["TOTAL_CLAIM_AMOUNT"] or 0
        st.metric("Total Claimed", f"₹{claim_amt:,.0f}", border=True)
        approved = row["TOTAL_APPROVED"] or 0
        st.metric("Total Approved", f"₹{approved:,.0f}", border=True)
    with st.container(horizontal=True):
        avg_d = row["AVG_DAYS"]
        st.metric("Avg Processing Days", f"{avg_d:.0f}" if avg_d else "N/A", border=True)
        sr = row["SETTLEMENT_RATE"]
        st.metric("Settlement Rate", f"{sr:.1f}%" if sr else "N/A", border=True)
        st.metric("Fraud Alerts", f"{int(row['FRAUD_ALERTS']):,}", border=True)

st.divider()

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("Claims Pipeline")
        df_pipe = load_claims_pipeline()
        if not df_pipe.empty:
            st.dataframe(df_pipe, use_container_width=True, hide_index=True)

with col2:
    with st.container(border=True):
        st.subheader("Claims by Type")
        df_type = load_claims_by_type()
        if not df_type.empty:
            st.bar_chart(df_type, x="Claim Type", y="Count")

st.divider()
with st.container(border=True):
    st.subheader("Fraud-Flagged Claims")
    df_fraud = load_fraud_claims()
    if not df_fraud.empty:
        st.dataframe(df_fraud, use_container_width=True, hide_index=True)
    else:
        st.success("No fraud-flagged claims.")
