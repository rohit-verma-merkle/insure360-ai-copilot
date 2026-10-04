import streamlit as st
import pandas as pd

conn = st.session_state["conn"]
session = conn.session()

st.header("Customer 360 View")

if st.button("Refresh customer list", icon=":material/refresh:"):
    st.cache_data.clear()


@st.cache_data(ttl=60)
def load_customer_list():
    df = conn.query("""
        SELECT CUSTOMER_ID, CUSTOMER_NAME, CUSTOMER_SEGMENT,
               TOTAL_ANNUAL_PREMIUM, TOTAL_CLAIMS, OPEN_CLAIMS, HAS_FRAUD_FLAG
        FROM INSURE360_APP.ANALYTICS.DT_CUSTOMER_360
        ORDER BY CUSTOMER_NAME
    """)
    if not df.empty:
        df = df.rename(columns={
            "CUSTOMER_ID": "Customer ID", "CUSTOMER_NAME": "Customer Name",
            "CUSTOMER_SEGMENT": "Segment", "TOTAL_ANNUAL_PREMIUM": "Annual Premium",
            "TOTAL_CLAIMS": "Total Claims", "OPEN_CLAIMS": "Open Claims",
            "HAS_FRAUD_FLAG": "Fraud Flag",
        })
    return df


cust_list = load_customer_list()

if cust_list.empty:
    st.info("No customers found. Ensure interface views are generated and data exists.")
    st.stop()

options = {
    f"{row['Customer Name']} ({row['Customer ID']}) — {row['Segment']}": row["Customer ID"]
    for _, row in cust_list.iterrows()
}

selected = st.selectbox("Search customer", list(options.keys()), index=None,
                         placeholder="Type to search by name, ID, or segment...")

if not selected:
    st.info("Select a customer from the dropdown to view their 360 profile.")
    with st.container(border=True):
        st.subheader("All Customers")
        st.dataframe(cust_list, use_container_width=True, hide_index=True)
    st.stop()

cust_id = options[selected]

df = conn.query(
    """
    SELECT CUSTOMER_ID, CUSTOMER_NAME, AGE, GENDER, CITY, STATE,
           CUSTOMER_SEGMENT, CUSTOMER_TENURE_MONTHS, PREFERRED_CHANNEL,
           TOTAL_POLICIES, ACTIVE_POLICIES, LAPSED_POLICIES, POLICY_TYPES,
           TOTAL_SUM_INSURED, TOTAL_ANNUAL_PREMIUM, NEXT_RENEWAL_DATE, DAYS_TO_RENEWAL,
           TOTAL_CLAIMS, OPEN_CLAIMS, TOTAL_CLAIM_AMOUNT, TOTAL_APPROVED_AMOUNT,
           HAS_FRAUD_FLAG
    FROM INSURE360_APP.ANALYTICS.DT_CUSTOMER_360
    WHERE CUSTOMER_ID = ?
    """,
    params=[cust_id],
    ttl=0,
)
if df.empty:
    st.warning("Customer not found.")
    st.stop()

c = df.iloc[0]

# ═══════════════════════════════════════════════════════════════════
# SECTION 1: CUSTOMER PROFILE
# ═══════════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("Customer Profile")

    profile = conn.query(
        """
        SELECT CUSTOMER_ID, FIRST_NAME, LAST_NAME, GENDER, DATE_OF_BIRTH,
               CITY, STATE, PINCODE, CUSTOMER_SEGMENT, ONBOARDING_DATE,
               KYC_STATUS, OCCUPATION, MARITAL_STATUS, NUMBER_OF_DEPENDENTS,
               MOBILE_NUMBER, EMAIL_ADDRESS
        FROM INSURE360_APP.INTERFACE.V_CUSTOMERS
        WHERE CUSTOMER_ID = ?
        """,
        params=[cust_id],
    )

    if not profile.empty:
        p = profile.iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Name", f"{p.get('FIRST_NAME', '')} {p.get('LAST_NAME', '')}", border=True)
        col2.metric("Segment", c.get("CUSTOMER_SEGMENT", "N/A"), border=True)
        tenure = c.get("CUSTOMER_TENURE_MONTHS", 0) or 0
        col3.metric("Tenure", f"{int(tenure)} months", border=True)
        col4.metric("KYC Status", p.get("KYC_STATUS", "N/A"), border=True)

        p1, p2, p3, p4 = st.columns(4)
        p1.markdown(f"**Gender:** {p.get('GENDER', 'N/A')}")
        p2.markdown(f"**Occupation:** {p.get('OCCUPATION', 'N/A')}")
        p3.markdown(f"**City:** {p.get('CITY', 'N/A')}, {p.get('STATE', 'N/A')}")
        p4.markdown(f"**Marital Status:** {p.get('MARITAL_STATUS', 'N/A')}")

        d1, d2, d3, d4 = st.columns(4)
        d1.markdown(f"**DOB:** {p.get('DATE_OF_BIRTH', 'N/A')}")
        d2.markdown(f"**Dependents:** {p.get('NUMBER_OF_DEPENDENTS', 0)}")
        d3.markdown(f"**Mobile:** {p.get('MOBILE_NUMBER', 'N/A')}")
        d4.markdown(f"**Email:** {p.get('EMAIL_ADDRESS', 'N/A')}")

# ═══════════════════════════════════════════════════════════════════
# SECTION 2: KEY METRICS
# ═══════════════════════════════════════════════════════════════════
with st.container(horizontal=True):
    premium = c.get("TOTAL_ANNUAL_PREMIUM", 0) or 0
    st.metric("Annual Premium", f"₹{premium:,.0f}", border=True)
    st.metric("Policies", f"{int(c.get('TOTAL_POLICIES', 0))}", border=True)
    st.metric("Open Claims", f"{int(c.get('OPEN_CLAIMS', 0))}", border=True)
    claim_amt = c.get("TOTAL_CLAIM_AMOUNT", 0) or 0
    st.metric("Claims Amount", f"₹{claim_amt:,.0f}", border=True)
    fraud = c.get("HAS_FRAUD_FLAG")
    if fraud:
        st.metric("Fraud Alert", "FLAGGED", border=True)


# ═══════════════════════════════════════════════════════════════════
# SECTION 3: POLICIES
# ═══════════════════════════════════════════════════════════════════
st.divider()
with st.container(border=True):
    st.subheader("Policies")
    policies = conn.query(
        """
        SELECT POLICY_ID, POLICY_TYPE, PRODUCT_NAME, POLICY_STATUS,
               INCEPTION_DATE, EXPIRY_DATE, SUM_INSURED, ANNUAL_PREMIUM, RISK_CATEGORY
        FROM INSURE360_APP.INTERFACE.V_POLICIES
        WHERE CUSTOMER_ID = ?
        ORDER BY INCEPTION_DATE DESC
        """,
        params=[cust_id],
    )
    if not policies.empty:
        st.dataframe(policies, use_container_width=True, hide_index=True)
        all_types = {"HEALTH", "LIFE", "MOTOR", "HOME", "TRAVEL"}
        existing = set(policies["POLICY_TYPE"].unique())
        gaps = all_types - existing
        if gaps:
            st.warning(f"Coverage gaps detected: **{', '.join(sorted(gaps))}**")
        else:
            st.success("Comprehensive coverage across all major categories.")
    else:
        st.info("No policies found.")


# ═══════════════════════════════════════════════════════════════════
# SECTION 4: CLAIMS
# ═══════════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("Claims History")
    claims = conn.query(
        """
        SELECT CLAIM_ID, CLAIM_DATE, CLAIM_TYPE, CLAIM_STATUS,
               CLAIM_AMOUNT, APPROVED_AMOUNT, CAUSE_OF_LOSS, FRAUD_FLAG
        FROM INSURE360_APP.INTERFACE.V_CLAIMS
        WHERE CUSTOMER_ID = ?
        ORDER BY CLAIM_DATE DESC
        """,
        params=[cust_id],
    )
    if not claims.empty:
        st.dataframe(claims, use_container_width=True, hide_index=True)
    else:
        st.info("No claims history.")


# ═══════════════════════════════════════════════════════════════════
# SECTION 5: AI INSIGHTS & SENTIMENT
# ═══════════════════════════════════════════════════════════════════
with st.container(border=True):
    st.subheader("AI Insights")

    insights = conn.query(
        """
        SELECT SOURCE_TYPE, SOURCE_ID, PRIMARY_INTENT, SENTIMENT_LABEL,
               SENTIMENT_SCORE, LIFE_EVENT_DETECTED, LEFT(SUMMARY, 200) AS SUMMARY_PREVIEW,
               PROCESSING_DATE
        FROM INSURE360_APP.AI.AI_INSIGHTS
        WHERE CUSTOMER_ID = ?
        ORDER BY PROCESSING_DATE DESC
        """,
        params=[cust_id],
    )

    if not insights.empty:
        # Sentiment summary
        ai1, ai2, ai3 = st.columns(3)
        avg_sent = insights["SENTIMENT_SCORE"].mean()
        most_common_intent = insights["PRIMARY_INTENT"].mode().iloc[0] if not insights["PRIMARY_INTENT"].mode().empty else "N/A"
        life_events = insights[insights["LIFE_EVENT_DETECTED"].notna() & (insights["LIFE_EVENT_DETECTED"] != "NONE")]

        sent_label = "POSITIVE" if avg_sent > 0.3 else ("NEGATIVE" if avg_sent < -0.3 else "NEUTRAL")
        ai1.metric("Avg Sentiment", f"{avg_sent:.2f} ({sent_label})", border=True)
        ai2.metric("Top Intent", most_common_intent, border=True)
        ai3.metric("Life Events", f"{len(life_events)} detected", border=True)

        st.dataframe(insights, use_container_width=True, hide_index=True)

        # Sentiment chart
        if len(insights) > 1:
            chart_df = insights[["PROCESSING_DATE", "SENTIMENT_SCORE"]].sort_values("PROCESSING_DATE")
            st.line_chart(chart_df, x="PROCESSING_DATE", y="SENTIMENT_SCORE")
    else:
        st.info("No AI insights yet.")

# Life events section
life_events_df = conn.query(
    """
    SELECT EVENT_TYPE, DETECTION_DATE, CONFIDENCE_SCORE, SOURCE_TYPE, EVIDENCE_TEXT, STATUS
    FROM INSURE360_APP.AI.LIFE_EVENTS
    WHERE CUSTOMER_ID = ?
    ORDER BY DETECTION_DATE DESC
    """,
    params=[cust_id],
)
if not life_events_df.empty:
    with st.container(border=True):
        st.subheader("Life Events Detected")
        st.dataframe(life_events_df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# SECTION 6: NEXT BEST ACTION (Rule-based + AI + Execute)
# ═══════════════════════════════════════════════════════════════════
st.divider()

# ── Fetch transcript summaries & full AI insights for NBA context ──
transcripts_df = conn.query(
    """
    SELECT T.TRANSCRIPT_ID, T.TRANSCRIPT_TEXT, T.CALL_TIMESTAMP,
           I.INTERACTION_TYPE, I.SUBJECT, I.INTERACTION_SUMMARY,
           I.RESOLUTION_STATUS, I.CSAT_SCORE, I.RELATED_CLAIM_ID
    FROM INSURE360_APP.INTERFACE.V_CALL_TRANSCRIPTS T
    LEFT JOIN INSURE360_APP.INTERFACE.V_INTERACTIONS I
        ON T.INTERACTION_ID = I.INTERACTION_ID
    WHERE T.CUSTOMER_ID = ?
    ORDER BY T.CALL_TIMESTAMP DESC
    """,
    params=[cust_id],
    ttl=0,
)

ai_summaries_df = conn.query(
    """
    SELECT SOURCE_TYPE, SOURCE_ID, SUMMARY, PRIMARY_INTENT,
           SENTIMENT_LABEL, SENTIMENT_SCORE, LIFE_EVENT_DETECTED,
           LIFE_EVENT_EVIDENCE
    FROM INSURE360_APP.AI.AI_INSIGHTS
    WHERE CUSTOMER_ID = ?
    ORDER BY PROCESSING_DATE DESC
    """,
    params=[cust_id],
    ttl=0,
)

with st.container(border=True):
    st.subheader("Next Best Actions")

    # ── Rule-based instant recommendations (no AI call needed) ──
    import datetime

    def generate_rule_based_actions(c, policies_df, claims_df, insights_df, life_events_df, transcripts_df, ai_summaries_df):
        actions = []
        today = datetime.date.today()

        # -- Build transcript context helpers --
        complaint_transcripts = []
        request_transcripts = []
        positive_transcripts = []
        if not transcripts_df.empty:
            for _, tr in transcripts_df.iterrows():
                itype = str(tr.get("INTERACTION_TYPE", "")).upper()
                subj = str(tr.get("SUBJECT", ""))
                summary = str(tr.get("INTERACTION_SUMMARY", ""))
                csat = tr.get("CSAT_SCORE")
                claim_ref = tr.get("RELATED_CLAIM_ID")
                entry = {"subject": subj, "summary": summary, "csat": csat, "claim_ref": claim_ref}
                if itype == "COMPLAINT":
                    complaint_transcripts.append(entry)
                elif itype == "REQUEST":
                    request_transcripts.append(entry)
                if csat is not None and float(csat) >= 4.0:
                    positive_transcripts.append(entry)

        # -- AI summary helper: get specific complaint/request details --
        neg_summaries = []
        product_requests = []
        if not ai_summaries_df.empty:
            for _, ai in ai_summaries_df.iterrows():
                sent = str(ai.get("SENTIMENT_LABEL", "")).upper()
                intent = str(ai.get("PRIMARY_INTENT", "")).upper()
                summary = str(ai.get("SUMMARY", ""))[:300]
                if sent == "NEGATIVE":
                    neg_summaries.append(summary)
                if intent in ("NEW_POLICY_INQUIRY", "COVERAGE_QUESTION"):
                    le = ai.get("LIFE_EVENT_EVIDENCE")
                    product_requests.append({"summary": summary, "evidence": str(le) if le else ""})

        # 1. Open claims → Escalate (enriched with claim IDs and transcript complaints)
        open_cl = int(c.get("OPEN_CLAIMS", 0) or 0)
        if open_cl >= 1 and not claims_df.empty:
            open_claims_rows = claims_df[claims_df["CLAIM_STATUS"].isin(["OPEN", "UNDER_REVIEW", "IN_PROGRESS"])]
            if open_claims_rows.empty:
                open_claims_rows = claims_df[claims_df["CLAIM_STATUS"] != "SETTLED"]
            claim_ids = open_claims_rows["CLAIM_ID"].tolist()[:5]
            claim_details = []
            for _, cl in open_claims_rows.iterrows():
                amt = f"₹{float(cl.get('CLAIM_AMOUNT', 0) or 0):,.0f}"
                claim_details.append(f"• **{cl['CLAIM_ID']}** — {cl.get('CLAIM_TYPE', 'N/A')} | Amount: {amt} | Status: {cl['CLAIM_STATUS']} | Cause: {cl.get('CAUSE_OF_LOSS', 'N/A')}")
            claim_complaints = [t for t in complaint_transcripts if t.get("claim_ref")]
            transcript_notes = []
            for tc in claim_complaints[:3]:
                transcript_notes.append(f"• Call about {tc.get('claim_ref', 'claim')}: {tc['summary'][:150]}")
            extra = ""
            if claim_complaints:
                subjects = [t["subject"] for t in claim_complaints[:2]]
                extra = f" Customer has called {len(claim_complaints)} time(s) about claims ({'; '.join(subjects)})."
            ref_str = ", ".join(str(cid) for cid in claim_ids)
            actions.append({
                "action": f"Escalate claim(s) {ref_str} to priority processing",
                "priority": "High", "department": "Claims",
                "outcome": "Faster resolution, prevent customer escalation",
                "confidence": 0.95 if claim_complaints else 0.92,
                "reasoning": f"{open_cl} unresolved claim(s): {ref_str}.{extra} Proactive escalation prevents complaints and churn.",
                "ref_ids": ref_str,
                "details": "\n".join(claim_details + (["", "**Customer Interactions:**"] + transcript_notes if transcript_notes else [])),
            })

        # 2. Fraud flagged → Investigate or Reject (only SUSPECT or Y claims)
        if c.get("HAS_FRAUD_FLAG") and not claims_df.empty:
            fraud_claims = claims_df[claims_df["FRAUD_FLAG"].isin(["Y", "SUSPECT"])]
            if not fraud_claims.empty:
                fraud_ids = fraud_claims["CLAIM_ID"].tolist()
                fraud_detail = []
                for _, fc in fraud_claims.iterrows():
                    amt = f"₹{float(fc.get('CLAIM_AMOUNT', 0) or 0):,.0f}"
                    fraud_detail.append(f"• **{fc['CLAIM_ID']}** — {fc.get('CLAIM_TYPE', 'N/A')} | Amount: {amt} | Status: {fc.get('CLAIM_STATUS', 'N/A')} | Fraud: {fc['FRAUD_FLAG']} | Cause: {fc.get('CAUSE_OF_LOSS', 'N/A')}")
                ref_str = ", ".join(str(fid) for fid in fraud_ids)
                actions.append({
                    "action": f"SIU Investigation for {ref_str} — hold settlement",
                    "priority": "Critical", "department": "Claims",
                    "outcome": "Prevent fraudulent payout, protect loss ratio",
                    "confidence": 0.95,
                    "reasoning": f"Fraud indicators on {ref_str}. SIU review required before any settlement.",
                    "ref_ids": ref_str,
                    "details": "\n".join(fraud_detail),
                })

        # 3. Rejected claims exist → Explain + Suggest alternative
        if not claims_df.empty:
            rejected = claims_df[claims_df["CLAIM_STATUS"] == "REJECTED"]
            if len(rejected) > 0:
                rej_ids = rejected["CLAIM_ID"].tolist()[:5]
                rej_detail = []
                for _, rj in rejected.iterrows():
                    amt = f"₹{float(rj.get('CLAIM_AMOUNT', 0) or 0):,.0f}"
                    rej_detail.append(f"• **{rj['CLAIM_ID']}** — {rj.get('CLAIM_TYPE', 'N/A')} | Amount: {amt} | Cause: {rj.get('CAUSE_OF_LOSS', 'N/A')}")
                ref_str = ", ".join(str(rid) for rid in rej_ids)
                actions.append({
                    "action": f"Callback to explain denied claim(s) {ref_str} and suggest alternatives",
                    "priority": "High", "department": "Customer Service",
                    "outcome": "Reduce dissatisfaction, prevent churn from denial",
                    "confidence": 0.85,
                    "reasoning": f"{len(rejected)} rejected claim(s): {ref_str}. Unexplained denials are the #1 driver of churn.",
                    "ref_ids": ref_str,
                    "details": "\n".join(rej_detail),
                })

        # 4. Renewal approaching → Retention offer
        renewal_date = c.get("NEXT_RENEWAL_DATE")
        if renewal_date is not None:
            try:
                if isinstance(renewal_date, str):
                    renewal_date = datetime.datetime.strptime(str(renewal_date)[:10], "%Y-%m-%d").date()
                elif isinstance(renewal_date, datetime.datetime):
                    renewal_date = renewal_date.date()
                days_left = (renewal_date - today).days
                if 0 < days_left <= 30:
                    # Find policies approaching renewal
                    renewing_pols = []
                    if not policies_df.empty and "EXPIRY_DATE" in policies_df.columns:
                        for _, p in policies_df.iterrows():
                            exp = p.get("EXPIRY_DATE")
                            if exp:
                                renewing_pols.append(f"• **{p.get('POLICY_ID', 'N/A')}** — {p.get('POLICY_TYPE', 'N/A')} | Premium: ₹{float(p.get('ANNUAL_PREMIUM', 0) or 0):,.0f}")
                    actions.append({
                        "action": f"Send personalized renewal offer with loyalty discount — {days_left} days left",
                        "priority": "High", "department": "Sales",
                        "outcome": "Secure renewal, maintain premium revenue",
                        "confidence": 0.88,
                        "reasoning": f"Policy renewal in {days_left} days. Proactive offer increases retention by 25%.",
                        "ref_ids": f"Renewal in {days_left} days",
                        "details": "\n".join(renewing_pols) if renewing_pols else f"Next renewal date: {renewal_date}",
                    })
            except Exception:
                pass

        # 5. Coverage gaps → Cross-sell (enriched with transcript product requests)
        if not policies_df.empty:
            all_types = {"HEALTH", "LIFE", "MOTOR", "HOME", "TRAVEL"}
            existing_types = set(policies_df["POLICY_TYPE"].unique())
            gaps = all_types - existing_types
            for gap in sorted(gaps):
                product_map = {
                    "HOME": ("Offer Home Insurance — property protection", "Home Shield Comprehensive", 15000),
                    "TRAVEL": ("Offer Travel Insurance for trips", "Travel Guard Premium", 5000),
                    "LIFE": ("Recommend Term Life Insurance", "Term Life Protection", 18000),
                    "MOTOR": ("Offer Motor Insurance for vehicle", "Comprehensive Car Insurance", 12000),
                    "HEALTH": ("Offer Health Insurance coverage", "Family Health Floater", 25000),
                }
                rec, prod, rev = product_map.get(gap, (f"Offer {gap} insurance", gap, 10000))
                # Check if customer explicitly asked about this product in transcripts
                asked = [r for r in request_transcripts if gap.lower() in r["summary"].lower() or gap.lower() in r["subject"].lower()]
                ai_asked = [r for r in product_requests if gap.lower() in r["summary"].lower()]
                conf = 0.78
                extra_reason = ""
                if asked or ai_asked:
                    conf = 0.93
                    rec = f"PRIORITY: {rec} — customer has actively enquired"
                    extra_reason = f" Customer explicitly asked about {gap} insurance in recent call(s)."
                # Build details: existing policies + transcript context
                detail_lines = [f"**Missing:** {gap} insurance", f"**Existing Policies:**"]
                for _, ep in policies_df.iterrows():
                    detail_lines.append(f"• {ep.get('POLICY_ID', 'N/A')} — {ep.get('POLICY_TYPE', 'N/A')} | Premium: ₹{float(ep.get('ANNUAL_PREMIUM', 0) or 0):,.0f}")
                if asked:
                    detail_lines.append(f"\n**From call:** {asked[0]['summary'][:200]}")
                actions.append({
                    "action": rec,
                    "priority": "High" if (asked or ai_asked) else "Medium",
                    "department": "Sales",
                    "outcome": f"Increase wallet share — estimated ₹{rev:,}/yr",
                    "confidence": conf,
                    "reasoning": f"No {gap} policy found.{extra_reason} Coverage gap represents cross-sell opportunity.",
                    "ref_ids": f"Gap: {gap}",
                    "details": "\n".join(detail_lines),
                })

        # 6. Life events → Targeted products (enriched with transcript evidence)
        if not life_events_df.empty:
            for _, ev in life_events_df.iterrows():
                event = ev["EVENT_TYPE"]
                event_actions = {
                    "HOME_PURCHASE": ("Offer Home Insurance for new property", "Home Shield", "High"),
                    "NEW_CHILD": ("Offer Child Education Plan + Family Floater upgrade", "Child Future Protect", "High"),
                    "MARRIAGE": ("Offer Joint Life Plan + Spouse Health Add-on", "Joint Life Plan", "High"),
                    "RETIREMENT_PLANNING": ("Pension review + Health upgrade before retirement", "Pension Plus", "Medium"),
                    "VEHICLE_PURCHASE": ("Offer Motor Insurance for new vehicle", "Comprehensive Car", "High"),
                    "MEDICAL_EVENT": ("Review health sum insured adequacy + Super Top-Up", "Health Super Top-Up", "Medium"),
                }
                if event in event_actions:
                    act, prod, pri = event_actions[event]
                    evidence = str(ev.get("EVIDENCE_TEXT", ""))[:150]
                    # Find matching AI insight with transcript evidence
                    ai_evidence = [r for r in product_requests if r["evidence"] and event.lower().replace("_", " ") in r["evidence"].lower()]
                    transcript_note = ""
                    if evidence:
                        transcript_note = f" Customer stated: '{evidence}'"
                    elif ai_evidence:
                        transcript_note = f" Detected from call: '{ai_evidence[0]['evidence'][:120]}'"
                    actions.append({
                        "action": act,
                        "priority": pri, "department": "Sales",
                        "outcome": f"Life event conversion — product: {prod}",
                        "confidence": 0.90 if transcript_note else 0.85,
                        "reasoning": f"Life event '{event}' detected.{transcript_note} High conversion window for relevant products.",
                        "ref_ids": f"Event: {event}",
                        "details": f"**Life Event:** {event}\n**Evidence:** {evidence or 'Detected from AI analysis'}\n**Recommended Product:** {prod}",
                    })

        # 7. Negative sentiment → Service recovery (enriched with complaint transcripts)
        if not insights_df.empty:
            neg_count = len(insights_df[insights_df["SENTIMENT_LABEL"] == "NEGATIVE"])
            if neg_count >= 2:
                complaint_detail = ""
                if complaint_transcripts:
                    subjects = [t["subject"] for t in complaint_transcripts[:3]]
                    complaint_detail = f" Complaints about: {'; '.join(subjects)}."
                elif neg_summaries:
                    complaint_detail = f" Key issue: {neg_summaries[0][:150]}..."
                neg_detail = []
                for _, ni in insights_df[insights_df["SENTIMENT_LABEL"] == "NEGATIVE"].iterrows():
                    neg_detail.append(f"• [{ni.get('SOURCE_TYPE', 'N/A')}] {ni.get('PRIMARY_INTENT', 'N/A')} — {str(ni.get('SUMMARY_PREVIEW', ''))[:150]}")
                actions.append({
                    "action": "Initiate service recovery — manager callback within 24hrs",
                    "priority": "Critical", "department": "Retention",
                    "outcome": "Prevent churn from accumulated negative experience",
                    "confidence": 0.93 if complaint_detail else 0.90,
                    "reasoning": f"{neg_count} negative sentiment interactions.{complaint_detail} Immediate intervention required.",
                    "ref_ids": f"{neg_count} negative interactions",
                    "details": "\n".join(neg_detail) if neg_detail else "Multiple negative sentiment interactions detected.",
                })

        # 8. High-value customer care
        segment = c.get("CUSTOMER_SEGMENT", "")
        policies_count = int(c.get("TOTAL_POLICIES", 0) or 0)
        if segment in ("PLATINUM", "GOLD") and policies_count >= 3:
            pol_detail = []
            if not policies_df.empty:
                for _, ep in policies_df.iterrows():
                    pol_detail.append(f"• {ep.get('POLICY_ID', 'N/A')} — {ep.get('POLICY_TYPE', 'N/A')} | Premium: ₹{float(ep.get('ANNUAL_PREMIUM', 0) or 0):,.0f}")
            actions.append({
                "action": "Assign dedicated relationship manager",
                "priority": "Medium", "department": "Retention",
                "outcome": "Increase NPS and retention for high-value segment",
                "confidence": 0.82,
                "reasoning": f"{segment} tier with {policies_count} policies. High-value customer deserves dedicated service.",
                "ref_ids": f"Segment: {segment}",
                "details": f"**Segment:** {segment} | **Policies:** {policies_count} | **Premium:** ₹{float(c.get('TOTAL_ANNUAL_PREMIUM', 0) or 0):,.0f}\n" + "\n".join(pol_detail),
            })

        # 9. Claim approval suggestion (for under_review claims with clean fraud score)
        if not claims_df.empty:
            review_claims = claims_df[
                (claims_df["CLAIM_STATUS"] == "UNDER_REVIEW") &
                (claims_df["FRAUD_FLAG"] == "N")
            ]
            if len(review_claims) > 0:
                rev_ids = review_claims["CLAIM_ID"].tolist()[:5]
                rev_detail = []
                for _, rc in review_claims.iterrows():
                    amt = f"₹{float(rc.get('CLAIM_AMOUNT', 0) or 0):,.0f}"
                    rev_detail.append(f"• **{rc['CLAIM_ID']}** — {rc.get('CLAIM_TYPE', 'N/A')} | Amount: {amt} | Cause: {rc.get('CAUSE_OF_LOSS', 'N/A')} | Fraud: {rc['FRAUD_FLAG']}")
                ref_str = ", ".join(str(rid) for rid in rev_ids)
                actions.append({
                    "action": f"Approve clean claim(s) {ref_str} — no fraud indicators",
                    "priority": "High", "department": "Claims",
                    "outcome": "Faster settlement, improved customer satisfaction",
                    "confidence": 0.88,
                    "reasoning": f"{len(review_claims)} claim(s) under review with clean fraud flag: {ref_str}. Eligible for fast-track approval.",
                    "ref_ids": ref_str,
                    "details": "\n".join(rev_detail),
                })

        # Default if nothing else
        if not actions:
            actions.append({
                "action": "Send appreciation message and policy review invitation",
                "priority": "Low", "department": "Customer Service",
                "outcome": "Maintain engagement and loyalty",
                "confidence": 0.65,
                "reasoning": "Healthy customer profile. Regular engagement maintains satisfaction."
            })

        return actions

    # Generate rule-based actions
    rule_actions = generate_rule_based_actions(c, policies, claims, insights, life_events_df, transcripts_df, ai_summaries_df)

    # ── Fetch previous actions for this customer ──
    prev_actions = conn.query(
        """
        SELECT N.RECOMMENDATION_ID, N.ACTION_TYPE, N.RECOMMENDATION, N.BUSINESS_IMPACT AS PRIORITY,
               N.CONFIDENCE_SCORE, N.STATUS, N.REASONING, N.CREATED_AT,
               N.RECOMMENDATION_DETAIL AS REJECTION_COMMENTS,
               T.TICKET_ID
        FROM INSURE360_APP.RECOMMENDATIONS.NEXT_BEST_ACTION N
        LEFT JOIN INSURE360_APP.RECOMMENDATIONS.TICKETS T
            ON N.RECOMMENDATION_ID = T.RECOMMENDATION_ID
        WHERE N.CUSTOMER_ID = ?
        ORDER BY N.CREATED_AT DESC
        LIMIT 30
        """,
        params=[cust_id],
        ttl=0,
    )

    # ── Show Previous Actions FIRST ──
    if not prev_actions.empty:
        st.markdown("##### Previous Actions")
        with st.container(border=True):
            with st.container(horizontal=True):
                total_a = len(prev_actions)
                accepted = len(prev_actions[prev_actions["STATUS"] == "ACCEPTED"])
                rejected = len(prev_actions[prev_actions["STATUS"] == "REJECTED"])
                open_tickets = len(prev_actions[(prev_actions["STATUS"] == "ACCEPTED") & (prev_actions["TICKET_ID"].notna())])
                st.metric("Total", total_a, border=True)
                st.metric("Accepted", accepted, border=True)
                st.metric("Rejected", rejected, border=True)
                st.metric("Tickets", open_tickets, border=True)

            for _, pa in prev_actions.iterrows():
                status = pa["STATUS"]
                color = "green" if status == "ACCEPTED" else ("red" if status == "REJECTED" else "gray")
                with st.container(border=True):
                    pa1, pa2 = st.columns([4, 1])
                    with pa1:
                        st.markdown(f":{color}[**{status}**] — {pa['RECOMMENDATION']}")
                        if status == "REJECTED" and pa.get("REJECTION_COMMENTS"):
                            st.caption(f"Rejection reason: *{pa['REJECTION_COMMENTS']}*")
                        if pa.get("TICKET_ID"):
                            st.caption(f"Ticket: **{pa['TICKET_ID']}**")
                    with pa2:
                        st.caption(f"{str(pa['CREATED_AT'])[:16]}")

        st.divider()

    # ── Filter rule-based actions: skip already accepted/rejected ones ──
    prev_action_texts = set()
    if not prev_actions.empty:
        prev_action_texts = set(prev_actions["RECOMMENDATION"].str.strip().str.lower().tolist())

    filtered_actions = [a for a in rule_actions if a["action"].strip().lower() not in prev_action_texts]

    # Sort: Critical > High > Medium > Low, then by confidence descending
    priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    filtered_actions.sort(key=lambda x: (priority_order.get(x["priority"], 9), -x["confidence"]))

    st.markdown(f"##### New Recommendations ({len(filtered_actions)})")
    if not filtered_actions:
        st.info("All recommendations have been acted upon. Generate AI Deep Analysis for additional insights.")

    for i, a in enumerate(filtered_actions):
        pri_color = {"Critical": "red", "High": "orange", "Medium": "blue", "Low": "green"}.get(a["priority"], "gray")

        with st.container(border=True):
            r1, r2 = st.columns([4, 1])
            with r1:
                ref = a.get("ref_ids", "")
                ref_badge = f"  `{ref}`" if ref else ""
                st.markdown(f"**{i+1}. {a['action']}**{ref_badge}")
                st.caption(f"Dept: **{a['department']}** | {a['reasoning']}")
                st.caption(f"Expected: {a['outcome']}")
            with r2:
                st.markdown(f":{pri_color}[**{a['priority']}**]")
                st.markdown(f"Confidence: **{a['confidence']:.0%}**")

            # View Details expander
            if a.get("details"):
                with st.expander("View Details"):
                    st.markdown(a["details"])

            # Accept / Reject buttons
            import hashlib
            reco_id = "NBA-RULE-" + hashlib.md5(f"{cust_id}{a['action']}".encode()).hexdigest()[:8].upper()
            detail_text = a.get("details", "")[:5000]

            ab1, ab2 = st.columns(2)
            if ab1.button("Accept", key=f"rule_accept_{i}", type="primary", use_container_width=True):
                # 1. Insert into NEXT_BEST_ACTION as ACCEPTED
                session.sql(
                    "INSERT INTO INSURE360_APP.RECOMMENDATIONS.NEXT_BEST_ACTION "
                    "(RECOMMENDATION_ID, CUSTOMER_ID, RECOMMENDATION_DATE, ACTION_TYPE, "
                    "RECOMMENDATION, CONFIDENCE_SCORE, PRIORITY_RANK, REASONING, BUSINESS_IMPACT, "
                    "STATUS, BATCH_ID, RECOMMENDATION_DETAIL) "
                    "SELECT :1,:2,CURRENT_TIMESTAMP(),:3,:4,:5,:6,:7,:8,'ACCEPTED','RULE',:9 "
                    "WHERE NOT EXISTS (SELECT 1 FROM INSURE360_APP.RECOMMENDATIONS.NEXT_BEST_ACTION WHERE RECOMMENDATION_ID = :1)",
                    params=[
                        reco_id, str(cust_id),
                        a["department"][:30], a["action"][:500], a["confidence"],
                        i + 1, a["reasoning"], a["priority"][:20],
                        detail_text,
                    ],
                ).collect()
                # 2. Generate ticket with full details
                ticket_row = session.sql(
                    "SELECT 'TKT-' || INSURE360_APP.RECOMMENDATIONS.SEQ_TICKET_ID.NEXTVAL AS TID"
                ).collect()
                ticket_id = ticket_row[0]["TID"] if ticket_row else "TKT-UNKNOWN"
                session.sql(
                    "INSERT INTO INSURE360_APP.RECOMMENDATIONS.TICKETS "
                    "(TICKET_ID, RECOMMENDATION_ID, CUSTOMER_ID, CUSTOMER_NAME, ACTION_TYPE, "
                    "RECOMMENDATION, PRIORITY, DEPARTMENT, REASONING, CONFIDENCE_SCORE, "
                    "ASSIGNED_TO_ROLE, STATUS, CREATED_BY, RESOLUTION_NOTES) "
                    "VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,'INSURE360_ADMIN','OPEN',CURRENT_USER(),:11)",
                    params=[
                        ticket_id, reco_id, str(cust_id),
                        str(c.get("CUSTOMER_NAME", ""))[:200],
                        a["department"][:30], a["action"][:500],
                        a["priority"][:20], a["department"][:50],
                        a["reasoning"], a["confidence"],
                        detail_text,
                    ],
                ).collect()
                st.success(f"Accepted. Ticket **{ticket_id}** created.")
                st.rerun()

            # Reject with comments
            reject_key = f"rule_reject_{i}"
            comment_key = f"reject_comment_{i}"
            if ab2.button("Reject", key=reject_key, use_container_width=True):
                st.session_state[f"show_reject_{i}"] = True

            if st.session_state.get(f"show_reject_{i}", False):
                reject_comment = st.text_area("Reason for rejection", key=comment_key, placeholder="Enter reason...")
                if st.button("Submit Rejection", key=f"submit_reject_{i}", type="secondary"):
                    if not reject_comment:
                        st.warning("Please provide a reason for rejection.")
                    else:
                        session.sql(
                            "INSERT INTO INSURE360_APP.RECOMMENDATIONS.NEXT_BEST_ACTION "
                            "(RECOMMENDATION_ID, CUSTOMER_ID, RECOMMENDATION_DATE, ACTION_TYPE, "
                            "RECOMMENDATION, CONFIDENCE_SCORE, PRIORITY_RANK, REASONING, BUSINESS_IMPACT, "
                            "STATUS, BATCH_ID, RECOMMENDATION_DETAIL) "
                            "SELECT :1,:2,CURRENT_TIMESTAMP(),:3,:4,:5,:6,:7,:8,'REJECTED','RULE',:9 "
                            "WHERE NOT EXISTS (SELECT 1 FROM INSURE360_APP.RECOMMENDATIONS.NEXT_BEST_ACTION WHERE RECOMMENDATION_ID = :1)",
                            params=[
                                reco_id, str(cust_id),
                                a["department"][:30], a["action"][:500], a["confidence"],
                                i + 1, a["reasoning"], a["priority"][:20],
                                reject_comment[:2000],
                            ],
                        ).collect()
                        st.info(f"Rejected: {a['action'][:60]}...")
                        st.session_state[f"show_reject_{i}"] = False
                        st.rerun()

    # ── AI Deep Analysis (on-demand) ──
    st.divider()
    if st.button("Generate AI Deep Analysis", icon=":material/auto_awesome:", type="primary", use_container_width=True):
        with st.spinner("AI is analyzing full customer context..."):
            pt = c.get("POLICY_TYPES")
            pt_str = ""
            if pt is not None:
                if isinstance(pt, str):
                    pt_str = pt.replace('"', '').replace('[', '').replace(']', '')
                elif isinstance(pt, list):
                    pt_str = ", ".join(str(x) for x in pt)
                else:
                    pt_str = str(pt).replace('"', '')

            gaps_str = ""
            if not policies.empty:
                all_t = {"HEALTH", "LIFE", "MOTOR", "HOME", "TRAVEL"}
                existing_t = set(policies["POLICY_TYPE"].unique())
                gap_list = all_t - existing_t
                if gap_list:
                    gaps_str = ", ".join(sorted(gap_list))

            le_str = ", ".join(life_events_df["EVENT_TYPE"].tolist()) if not life_events_df.empty else "None"

            # Build transcript summaries for AI context
            transcript_context = ""
            if not ai_summaries_df.empty:
                summaries = []
                for _, ai_row in ai_summaries_df.head(5).iterrows():
                    src = str(ai_row.get("SOURCE_TYPE", ""))
                    sent = str(ai_row.get("SENTIMENT_LABEL", ""))
                    intent = str(ai_row.get("PRIMARY_INTENT", ""))
                    summ = str(ai_row.get("SUMMARY", ""))[:200]
                    summaries.append(f"- [{src}] Sentiment: {sent}, Intent: {intent}. {summ}")
                transcript_context = "\n".join(summaries)

            # Build recent complaint context
            complaint_context = ""
            if not transcripts_df.empty:
                complaints = transcripts_df[transcripts_df["INTERACTION_TYPE"] == "COMPLAINT"] if "INTERACTION_TYPE" in transcripts_df.columns else transcripts_df.head(0)
                if not complaints.empty:
                    items = []
                    for _, tr in complaints.head(3).iterrows():
                        subj = str(tr.get("SUBJECT", ""))
                        summ = str(tr.get("INTERACTION_SUMMARY", ""))[:150]
                        res = str(tr.get("RESOLUTION_STATUS", ""))
                        items.append(f"- {subj}: {summ} [Status: {res}]")
                    complaint_context = "\n".join(items)

            prompt = f"""You are an insurance customer success advisor. Generate 3 specific Next Best Action recommendations.

Customer: {c.get('CUSTOMER_NAME', 'N/A')} (ID: {cust_id})
Segment: {c.get('CUSTOMER_SEGMENT', 'N/A')}
Tenure: {int(c.get('CUSTOMER_TENURE_MONTHS', 0) or 0)} months
Policies: {int(c.get('TOTAL_POLICIES', 0) or 0)} ({pt_str})
Coverage Gaps: {gaps_str or 'None'}
Premium: Rs.{float(c.get('TOTAL_ANNUAL_PREMIUM', 0) or 0):,.0f}
Open Claims: {int(c.get('OPEN_CLAIMS', 0) or 0)}
Fraud Flag: {'YES' if c.get('HAS_FRAUD_FLAG') else 'NO'}
Life Events: {le_str}

RECENT INTERACTION INSIGHTS (from call transcripts and emails):
{transcript_context or 'No transcript insights available.'}

ACTIVE COMPLAINTS:
{complaint_context or 'No active complaints.'}

Use the transcript insights and complaints above to tailor your recommendations. If the customer has expressed frustration, prioritize service recovery. If they asked about specific products, recommend those. If they mentioned life events, tie recommendations to those needs.

Include actions like: Approve claim, Reject claim with reason, Escalate claim, Cross-sell, Upsell, Retention offer, Service recovery.

For EACH provide:
- **Action**: Specific action
- **Priority**: Critical / High / Medium / Low
- **Department**: Sales / Claims / Customer Service / Retention / Underwriting
- **Expected Outcome**: Measurable result
- **Confidence**: 0.0-1.0
- **Reasoning**: Data-driven explanation referencing transcript insights where applicable"""

            try:
                escaped = prompt.replace("\\", "\\\\").replace("'", "\\'")
                result = session.sql(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', '{escaped}') AS RESPONSE").collect()
                ai_response = result[0]["RESPONSE"] if result else "No response."
                with st.container(border=True):
                    st.markdown("**AI-Generated Deep Recommendations**")
                    st.markdown(ai_response)
            except Exception as e:
                st.error(f"AI unavailable: {str(e)[:200]}")
