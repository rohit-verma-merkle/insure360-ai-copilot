import streamlit as st

conn = st.session_state["conn"]
session = conn.session()

st.header("AI Insight Center")


@st.cache_data(ttl=300)
def load_ai_stats():
    return conn.query("""
        SELECT
            COUNT(*) AS total_insights,
            COUNT(DISTINCT CASE WHEN PRIMARY_INTENT IS NOT NULL THEN INSIGHT_ID END) AS intents_detected,
            COUNT(DISTINCT CASE WHEN LIFE_EVENT_DETECTED IS NOT NULL
                AND LIFE_EVENT_DETECTED != 'NONE' THEN INSIGHT_ID END) AS events_found,
            AVG(INTENT_CONFIDENCE) AS avg_confidence
        FROM INSURE360_APP.AI.AI_INSIGHTS
    """)


@st.cache_data(ttl=300)
def load_sentiment_dist():
    return conn.query("""
        SELECT SENTIMENT_LABEL AS "Sentiment", COUNT(*) AS "Count"
        FROM INSURE360_APP.AI.AI_INSIGHTS
        WHERE SENTIMENT_LABEL IS NOT NULL
        GROUP BY 1
    """)


@st.cache_data(ttl=300)
def load_intent_dist():
    return conn.query("""
        SELECT PRIMARY_INTENT AS "Intent", COUNT(*) AS "Count"
        FROM INSURE360_APP.AI.AI_INSIGHTS
        WHERE PRIMARY_INTENT IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10
    """)


@st.cache_data(ttl=300)
def load_life_events():
    return conn.query("""
        SELECT EVENT_TYPE AS "Event Type", COUNT(*) AS "Count"
        FROM INSURE360_APP.AI.LIFE_EVENTS
        GROUP BY 1 ORDER BY 2 DESC
    """)


if st.button("Refresh", icon=":material/refresh:"):
    load_ai_stats.clear()
    load_sentiment_dist.clear()
    load_intent_dist.clear()
    load_life_events.clear()

stats = load_ai_stats()
if not stats.empty:
    row = stats.iloc[0]
    with st.container(horizontal=True):
        st.metric("Total Insights", f"{int(row['TOTAL_INSIGHTS']):,}", border=True)
        st.metric("Intents Detected", f"{int(row['INTENTS_DETECTED']):,}", border=True)
        st.metric("Life Events Found", f"{int(row['EVENTS_FOUND']):,}", border=True)
        conf = row["AVG_CONFIDENCE"]
        st.metric("Avg Confidence", f"{conf:.1%}" if conf else "N/A", border=True)

st.divider()

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("Sentiment Distribution")
        df_sent = load_sentiment_dist()
        if not df_sent.empty:
            st.bar_chart(df_sent, x="Sentiment", y="Count")
        else:
            st.info("No sentiment data yet.")

with col2:
    with st.container(border=True):
        st.subheader("Top Intents")
        df_intent = load_intent_dist()
        if not df_intent.empty:
            st.bar_chart(df_intent, x="Intent", y="Count")
        else:
            st.info("No intent data yet.")

with st.container(border=True):
    st.subheader("Life Events Detected")
    df_events = load_life_events()
    if not df_events.empty:
        st.bar_chart(df_events, x="Event Type", y="Count")
    else:
        st.info("No life events detected yet.")

st.divider()
st.subheader("AI Copilot")
st.caption("Ask questions about your insurance data")

if "copilot_messages" not in st.session_state:
    st.session_state.copilot_messages = []

for msg in st.session_state.copilot_messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("e.g., Which customers have coverage gaps?"):
    st.session_state.copilot_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            sys_prompt = "You are an insurance analytics AI assistant with access to customer, policy, and claims data. Answer concisely."
            result = session.sql(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(:1, :2) AS RESPONSE",
                params=["llama3.1-70b", f"{sys_prompt}\n\nQuestion: {prompt}"],
            ).collect()
            response = result[0]["RESPONSE"] if result else "Sorry, I could not generate a response."
            st.markdown(response)

    st.session_state.copilot_messages.append({"role": "assistant", "content": response})
