import streamlit as st
from datetime import datetime, timezone

conn = st.session_state["conn"]
session = conn.session()

st.header("Recommendations Center")


@st.cache_data(ttl=120)
def load_tickets():
    return conn.query("""
        SELECT T.TICKET_ID, T.CUSTOMER_ID, T.CUSTOMER_NAME, T.ACTION_TYPE AS DEPARTMENT,
               T.RECOMMENDATION, T.PRIORITY, T.CONFIDENCE_SCORE, T.STATUS,
               T.CREATED_BY, T.CREATED_AT, T.RESOLVED_BY, T.RESOLVED_AT,
               T.RESOLUTION_NOTES AS DETAILS, T.RESOLVE_COMMENTS
        FROM INSURE360_APP.RECOMMENDATIONS.TICKETS T
        ORDER BY
            CASE T.STATUS WHEN 'OPEN' THEN 0 ELSE 1 END,
            CASE T.PRIORITY
                WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3 ELSE 4
            END,
            T.CREATED_AT DESC
        LIMIT 200
    """, ttl=0)


# ── Process pending resolve (runs BEFORE page renders) ──
if st.session_state.get("pending_resolve_tid"):
    tid = st.session_state["pending_resolve_tid"]
    comment = st.session_state.get("pending_resolve_comment", "")
    if comment.strip():
        session.sql(
            "UPDATE INSURE360_APP.RECOMMENDATIONS.TICKETS "
            "SET STATUS = 'RESOLVED', RESOLVED_BY = CURRENT_USER(), "
            "RESOLVED_AT = CURRENT_TIMESTAMP(), RESOLVE_COMMENTS = :1, "
            "UPDATED_AT = CURRENT_TIMESTAMP() "
            "WHERE TICKET_ID = :2",
            params=[comment.strip()[:5000], tid],
        ).collect()
        st.cache_data.clear()
        st.toast(f"Ticket {tid} resolved successfully!")
    st.session_state["pending_resolve_tid"] = None
    st.session_state["pending_resolve_comment"] = ""
    st.session_state["resolving_ticket"] = None


if st.button("Refresh", icon=":material/refresh:"):
    st.cache_data.clear()

all_tickets = load_tickets()

if all_tickets.empty:
    st.info("No tickets yet. Accept recommendations from Customer 360 to create tickets.")
    st.stop()

# ── Recommendation Audit Summary ──
open_tk = len(all_tickets[all_tickets["STATUS"] == "OPEN"])
resolved_tk = len(all_tickets[all_tickets["STATUS"] == "RESOLVED"])

audit = conn.query("""
    SELECT
        COUNT(*) AS total_recommendations,
        COUNT(CASE WHEN STATUS = 'ACCEPTED' THEN 1 END) AS converted_to_ticket,
        COUNT(CASE WHEN STATUS = 'REJECTED' THEN 1 END) AS rejected,
        COUNT(CASE WHEN STATUS IN ('GENERATED', 'DELIVERED') THEN 1 END) AS no_action
    FROM INSURE360_APP.RECOMMENDATIONS.NEXT_BEST_ACTION
""", ttl=120)

with st.container(border=True):
    if not audit.empty:
        a = audit.iloc[0]
        total = int(a["TOTAL_RECOMMENDATIONS"]) or 1
        converted = int(a["CONVERTED_TO_TICKET"])
        rejected = int(a["REJECTED"])
        no_action = int(a["NO_ACTION"])
        with st.container(horizontal=True):
            st.metric("Total Recommendations", f"{total}", border=True)
            st.metric("Converted to Ticket", f"{converted} ({converted * 100 // total}%)", border=True)
            st.metric("Rejected", f"{rejected} ({rejected * 100 // total}%)", border=True)
            st.metric("No Action Taken", f"{no_action} ({no_action * 100 // total}%)", border=True)
        st.caption(f"Tickets — Open: **{open_tk}** | Resolved: **{resolved_tk}**")

st.divider()

# ── Status filter pills (default to Open) ──
status_options = ["Open", "Resolved", "All"]
selected_filter = st.pills("Filter by status", status_options, default="Open", key="ticket_filter_pills")
active_filter = selected_filter if selected_filter else "Open"

if active_filter == "All":
    filtered = all_tickets
else:
    filtered = all_tickets[all_tickets["STATUS"] == active_filter.upper()]

st.caption(f"Showing **{len(filtered)}** ticket(s)")


# ── Callbacks ──
def on_resolve_click(tid):
    st.session_state["resolving_ticket"] = tid


def on_cancel_resolve():
    st.session_state["resolving_ticket"] = None


def on_submit_resolve(tid):
    comment = st.session_state.get(f"comment_{tid}", "")
    if comment.strip():
        st.session_state["pending_resolve_tid"] = tid
        st.session_state["pending_resolve_comment"] = comment
    else:
        st.session_state["resolve_error"] = tid


# ── Ticket cards ──
now = datetime.now(timezone.utc)
resolving = st.session_state.get("resolving_ticket")

for _, tk in filtered.iterrows():
    status = tk["STATUS"]
    color = "green" if status == "RESOLVED" else "orange"
    pri_color = {"Critical": "red", "High": "orange", "Medium": "blue", "Low": "green"}.get(tk["PRIORITY"], "gray")
    tid = tk["TICKET_ID"]

    with st.container(border=True):
        t1, t2 = st.columns([4, 1])
        with t1:
            st.markdown(f":{color}[**{status}**] **{tid}** — {tk['RECOMMENDATION']}")
            st.caption(
                f"Customer: **{tk['CUSTOMER_NAME']}** ({tk['CUSTOMER_ID']}) | "
                f"Dept: **{tk['DEPARTMENT']}** | Created by: {tk['CREATED_BY']} | "
                f"{str(tk['CREATED_AT'])[:16]}"
            )

            if status == "OPEN":
                created = tk["CREATED_AT"]
                if created is not None:
                    if isinstance(created, str):
                        created = datetime.fromisoformat(str(created).replace(" ", "T"))
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    delta = now - created
                    days = delta.days
                    hours = delta.seconds // 3600
                    if days > 0:
                        age_str = f"{days}d {hours}h"
                    else:
                        age_str = f"{hours}h {(delta.seconds % 3600) // 60}m"
                    age_color = "red" if days >= 3 else ("orange" if days >= 1 else "blue")
                    st.markdown(f":{age_color}[Open for **{age_str}**]")

            if status == "RESOLVED":
                resolved_at = str(tk.get("RESOLVED_AT", ""))[:16]
                resolved_by = tk.get("RESOLVED_BY", "N/A")
                st.caption(f"Resolved by: **{resolved_by}** on {resolved_at}")
                comments = tk.get("RESOLVE_COMMENTS")
                if comments and str(comments).strip():
                    st.info(f"Resolution: {comments}")

        with t2:
            st.markdown(f":{pri_color}[**{tk['PRIORITY']}**]")
            st.caption(f"Confidence: {tk['CONFIDENCE_SCORE']:.0%}")
            if status == "OPEN" and resolving != tid:
                st.button(
                    "Resolve", key=f"rbtn_{tid}", type="primary",
                    use_container_width=True,
                    on_click=on_resolve_click, args=(tid,),
                )

        # Inline resolve panel
        if status == "OPEN" and resolving == tid:
            st.markdown("---")
            st.markdown(f"**Resolve {tid}**")
            st.text_area(
                "Resolution comments (required)",
                placeholder="Describe the action taken...",
                key=f"comment_{tid}",
            )
            if st.session_state.get("resolve_error") == tid:
                st.warning("Please provide resolution comments.")
                st.session_state["resolve_error"] = None
            bc1, bc2 = st.columns(2)
            bc1.button(
                "Submit Resolution", key=f"submit_{tid}", type="primary",
                use_container_width=True,
                on_click=on_submit_resolve, args=(tid,),
            )
            bc2.button(
                "Cancel", key=f"cancel_{tid}",
                use_container_width=True,
                on_click=on_cancel_resolve,
            )

        # View NBA details
        details = tk.get("DETAILS")
        if details and str(details).strip():
            with st.expander("View Details"):
                st.markdown(str(details))


# ═══════════════════════════════════════════════════════════════════
# Rejected & No Action Recommendations
# ═══════════════════════════════════════════════════════════════════
st.divider()

@st.cache_data(ttl=120)
def load_rejected_noaction():
    return conn.query("""
        SELECT N.RECOMMENDATION_ID, N.CUSTOMER_ID, C.CUSTOMER_NAME,
               N.ACTION_TYPE AS DEPARTMENT, N.RECOMMENDATION,
               N.CONFIDENCE_SCORE, N.BUSINESS_IMPACT AS PRIORITY,
               N.REASONING, N.STATUS, N.CREATED_AT,
               N.RECOMMENDATION_DETAIL AS COMMENTS
        FROM INSURE360_APP.RECOMMENDATIONS.NEXT_BEST_ACTION N
        LEFT JOIN INSURE360_APP.ANALYTICS.DT_CUSTOMER_360 C
            ON N.CUSTOMER_ID = C.CUSTOMER_ID
        WHERE N.STATUS IN ('REJECTED', 'GENERATED', 'DELIVERED')
        ORDER BY N.CREATED_AT DESC
        LIMIT 500
    """)

with st.container(border=True):
    st.subheader("Rejected & No Action Recommendations")

    rna_df = load_rejected_noaction()

    if rna_df.empty:
        st.info("No rejected or pending recommendations.")
    else:
        # Filter pills: Rejected / No Action / All
        rna_filter = st.pills(
            "Filter", ["Rejected", "No Action", "All"],
            default="All", key="rna_filter_pills",
        )
        if rna_filter == "Rejected":
            rna_filtered = rna_df[rna_df["STATUS"] == "REJECTED"]
        elif rna_filter == "No Action":
            rna_filtered = rna_df[rna_df["STATUS"].isin(["GENERATED", "DELIVERED"])]
        else:
            rna_filtered = rna_df

        # Search box
        search_term = st.text_input(
            "Search", placeholder="Search by customer name, ID, recommendation...",
            key="rna_search",
        )
        if search_term:
            term = search_term.strip().lower()
            rna_filtered = rna_filtered[
                rna_filtered.apply(
                    lambda r: term in str(r.get("CUSTOMER_NAME", "")).lower()
                    or term in str(r.get("CUSTOMER_ID", "")).lower()
                    or term in str(r.get("RECOMMENDATION", "")).lower()
                    or term in str(r.get("DEPARTMENT", "")).lower(),
                    axis=1,
                )
            ]

        total_records = len(rna_filtered)
        page_size = 10
        total_pages = max(1, (total_records + page_size - 1) // page_size)

        st.caption(f"**{total_records}** record(s) found")

        # Pagination
        if "rna_page" not in st.session_state:
            st.session_state["rna_page"] = 1
        # Reset page on filter/search change
        if st.session_state["rna_page"] > total_pages:
            st.session_state["rna_page"] = 1

        page = st.session_state["rna_page"]
        start_idx = (page - 1) * page_size
        page_data = rna_filtered.iloc[start_idx : start_idx + page_size]

        for _, r in page_data.iterrows():
            status = r["STATUS"]
            color = "red" if status == "REJECTED" else "gray"
            label = "REJECTED" if status == "REJECTED" else "NO ACTION"
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                with c1:
                    cust_name = r.get("CUSTOMER_NAME") or "Unknown"
                    st.markdown(f":{color}[**{label}**] {r['RECOMMENDATION']}")
                    st.caption(
                        f"Customer: **{cust_name}** ({r['CUSTOMER_ID']}) | "
                        f"Dept: {r.get('DEPARTMENT', 'N/A')} | "
                        f"{str(r['CREATED_AT'])[:16]}"
                    )
                    if status == "REJECTED" and r.get("COMMENTS") and str(r["COMMENTS"]).strip():
                        st.caption(f"Rejection reason: *{r['COMMENTS']}*")
                with c2:
                    pri = r.get("PRIORITY", "")
                    pri_color = {"Critical": "red", "High": "orange", "Medium": "blue", "Low": "green"}.get(pri, "gray")
                    if pri:
                        st.markdown(f":{pri_color}[**{pri}**]")
                    st.caption(f"Confidence: {r['CONFIDENCE_SCORE']:.0%}")

        # Page navigation
        if total_pages > 1:
            nav1, nav2, nav3 = st.columns([1, 2, 1])
            with nav1:
                if st.button("Previous", disabled=(page <= 1), use_container_width=True, key="rna_prev"):
                    st.session_state["rna_page"] = page - 1
                    st.rerun()
            with nav2:
                st.markdown(f"<div style='text-align:center'>Page **{page}** of **{total_pages}**</div>", unsafe_allow_html=True)
            with nav3:
                if st.button("Next", disabled=(page >= total_pages), use_container_width=True, key="rna_next"):
                    st.session_state["rna_page"] = page + 1
                    st.rerun()
