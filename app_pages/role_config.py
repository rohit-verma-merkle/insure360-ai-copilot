import streamlit as st

conn = st.session_state["conn"]
session = conn.session()

st.header("Role Configuration")
st.caption("Manage which roles can access which pages. Changes take effect on next page load.")

ALL_PAGE_OPTIONS = {
    "executive_dashboard": "Executive Dashboard",
    "customer_360": "Customer 360",
    "ai_insights": "AI Insight Center",
    "claims_intelligence": "Claims Intelligence",
    "recommendations": "Recommendations",
    "integration_config": "Integration Config",
    "role_config": "Role Configuration",
}


@st.cache_data(ttl=30)
def load_current_mappings():
    return conn.query("""
        SELECT ROLE_NAME AS "Role", PAGE_KEY AS "Page Key", CREATED_BY AS "Created By",
               CREATED_AT AS "Created At"
        FROM INSURE360_APP.CONFIG.ROLE_PAGE_ACCESS
        ORDER BY ROLE_NAME, PAGE_KEY
    """)


@st.cache_data(ttl=120)
def load_snowflake_roles():
    rows = session.sql("""
        SELECT ROLE_NAME FROM INSURE360_APP.CONFIG.ROLE_PAGE_ACCESS
        GROUP BY ROLE_NAME
        UNION
        SELECT 'ACCOUNTADMIN'
        UNION SELECT 'INSURE360_ADMIN'
        UNION SELECT 'INSURE360_DATA_ENGINEER'
        UNION SELECT 'INSURE360_SALES_ADVISOR'
        UNION SELECT 'INSURE360_CLAIMS_PROCESSOR'
        UNION SELECT 'INSURE360_UNDERWRITER'
        UNION SELECT 'INSURE360_RETENTION_MGR'
        UNION SELECT 'INSURE360_CC_MANAGER'
        UNION SELECT 'INSURE360_VIEWER'
        ORDER BY 1
    """).collect()
    return [r["ROLE_NAME"] for r in rows]


if st.button("Refresh", icon=":material/refresh:"):
    load_current_mappings.clear()
    load_snowflake_roles.clear()
    st.cache_data.clear()

# ── Current Mapping Matrix ──
mappings = load_current_mappings()
roles_list = load_snowflake_roles()

if not mappings.empty:
    # Build matrix view
    role_page_map = {}
    for _, row in mappings.iterrows():
        role = row["Role"]
        page = row["Page Key"]
        if role not in role_page_map:
            role_page_map[role] = set()
        role_page_map[role].add(page)

    with st.container(border=True):
        st.subheader("Current Access Matrix")
        matrix_data = []
        for role in sorted(role_page_map.keys()):
            row_data = {"Role": role}
            for page_key, page_name in ALL_PAGE_OPTIONS.items():
                row_data[page_name] = "Yes" if page_key in role_page_map.get(role, set()) else "—"
            matrix_data.append(row_data)

        import pandas as pd
        matrix_df = pd.DataFrame(matrix_data)
        st.dataframe(matrix_df, use_container_width=True, hide_index=True)
else:
    st.info("No role-page mappings found. Add mappings below.")

st.divider()

# ── Edit Role Access ──
with st.container(border=True):
    st.subheader("Edit Role Access")

    selected_role = st.selectbox("Select Role", roles_list, key="edit_role")

    if selected_role:
        # Get current pages for this role
        current_pages = set()
        if not mappings.empty:
            role_rows = mappings[mappings["Role"] == selected_role]
            current_pages = set(role_rows["Page Key"].tolist())

        st.caption(f"Select pages for **{selected_role}**:")

        new_pages = []
        cols = st.columns(3)
        for idx, (page_key, page_name) in enumerate(ALL_PAGE_OPTIONS.items()):
            col = cols[idx % 3]
            checked = col.checkbox(
                page_name,
                value=(page_key in current_pages),
                key=f"cb_{selected_role}_{page_key}",
            )
            if checked:
                new_pages.append(page_key)

        new_set = set(new_pages)
        has_changes = new_set != current_pages

        if has_changes:
            st.warning(f"Unsaved changes: {len(new_set)} page(s) selected (was {len(current_pages)})")

        if st.button("Save Changes", type="primary", disabled=not has_changes, use_container_width=True):
            # Delete existing mappings for this role
            session.sql(
                "DELETE FROM INSURE360_APP.CONFIG.ROLE_PAGE_ACCESS WHERE ROLE_NAME = :1",
                params=[selected_role],
            ).collect()
            # Insert new mappings
            for page_key in new_pages:
                session.sql(
                    "INSERT INTO INSURE360_APP.CONFIG.ROLE_PAGE_ACCESS (ROLE_NAME, PAGE_KEY) VALUES (:1, :2)",
                    params=[selected_role, page_key],
                ).collect()
            load_current_mappings.clear()
            st.cache_data.clear()
            st.success(f"Updated {selected_role}: {len(new_pages)} page(s) assigned.")
            st.rerun()

st.divider()

# ── Add New Role ──
with st.container(border=True):
    st.subheader("Add New Role")
    st.caption("Map a Snowflake role that is not yet in the system.")

    new_role_name = st.text_input("Role Name", placeholder="e.g., INSURE360_AUDITOR", key="new_role_input")

    if new_role_name:
        new_role_name = new_role_name.strip().upper()
        if new_role_name in roles_list:
            st.info(f"Role **{new_role_name}** already exists. Edit it above.")
        else:
            st.caption(f"Select pages for **{new_role_name}**:")
            new_role_pages = []
            cols = st.columns(3)
            for idx, (page_key, page_name) in enumerate(ALL_PAGE_OPTIONS.items()):
                col = cols[idx % 3]
                if col.checkbox(page_name, key=f"new_cb_{page_key}"):
                    new_role_pages.append(page_key)

            if st.button("Add Role", type="primary", disabled=len(new_role_pages) == 0, use_container_width=True):
                for page_key in new_role_pages:
                    session.sql(
                        "INSERT INTO INSURE360_APP.CONFIG.ROLE_PAGE_ACCESS (ROLE_NAME, PAGE_KEY) VALUES (:1, :2)",
                        params=[new_role_name, page_key],
                    ).collect()
                load_current_mappings.clear()
                load_snowflake_roles.clear()
                st.cache_data.clear()
                st.success(f"Added role **{new_role_name}** with {len(new_role_pages)} page(s).")
                st.rerun()
