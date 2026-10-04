import streamlit as st
import pandas as pd

conn = st.session_state["conn"]
session = conn.session()

st.header("Data Integration Config")
st.caption("Map your insurance database to the Insure360 interface layer")


# ── Shared metadata loaders (cached, used across tabs) ──
# Note: SHOW commands don't work with conn.query(); use session.sql().collect()
@st.cache_data(ttl=300)
def load_databases():
    rows = session.sql("SELECT DATABASE_NAME FROM SNOWFLAKE.INFORMATION_SCHEMA.DATABASES ORDER BY 1").collect()
    return [r["DATABASE_NAME"] for r in rows] if rows else []


@st.cache_data(ttl=300)
def load_schemas(database):
    rows = session.sql(
        "SELECT SCHEMA_NAME FROM IDENTIFIER(:1) ORDER BY 1",
        params=[f"{database}.INFORMATION_SCHEMA.SCHEMATA"],
    ).collect()
    if not rows:
        return []
    exclude = {"INFORMATION_SCHEMA"}
    return sorted([r["SCHEMA_NAME"] for r in rows if r["SCHEMA_NAME"] not in exclude])


@st.cache_data(ttl=300)
def load_tables(database, schema):
    rows = session.sql(
        f"SELECT TABLE_NAME FROM \"{database}\".INFORMATION_SCHEMA.TABLES "
        f"WHERE TABLE_SCHEMA = '{schema}' AND TABLE_TYPE = 'BASE TABLE' ORDER BY 1"
    ).collect()
    return [r["TABLE_NAME"] for r in rows] if rows else []


@st.cache_data(ttl=300)
def load_source_columns(database, schema, table):
    rows = session.sql(
        f"SELECT COLUMN_NAME, DATA_TYPE FROM \"{database}\".INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}' ORDER BY ORDINAL_POSITION"
    ).collect()
    if rows:
        return pd.DataFrame([{"COLUMN_NAME": r["COLUMN_NAME"], "DATA_TYPE": r["DATA_TYPE"]} for r in rows])
    return pd.DataFrame(columns=["COLUMN_NAME", "DATA_TYPE"])


@st.cache_data(ttl=60)
def load_mapping_status():
    return conn.query("""
        SELECT INTERFACE_NAME, MAPPING_STATUS, TOTAL_COLUMNS,
               MAPPED_COLUMNS, MAPPING_COMPLETENESS_PCT, SOURCE_TABLE,
               LAST_GENERATED_AT
        FROM INSURE360_APP.CONFIG.V_MAPPING_DASHBOARD
        ORDER BY INTERFACE_NAME
    """)


@st.cache_data(ttl=120)
def load_interfaces():
    return conn.query(
        "SELECT DISTINCT INTERFACE_NAME FROM INSURE360_APP.CONFIG.INTERFACE_CONTRACTS ORDER BY 1"
    )


@st.cache_data(ttl=120)
def load_existing_table_maps():
    return conn.query("""
        SELECT MAPPING_ID, INTERFACE_NAME, SOURCE_DATABASE, SOURCE_SCHEMA,
               SOURCE_TABLE, SOURCE_FILTER, IS_ACTIVE
        FROM INSURE360_APP.CONFIG.SOURCE_TABLE_MAPPING
        WHERE JOIN_ORDER = 0 ORDER BY INTERFACE_NAME
    """)


@st.cache_data(ttl=120)
def load_contract_columns(iface_name):
    return conn.query(
        "SELECT COLUMN_NAME, DATA_TYPE, IS_REQUIRED, DEFAULT_EXPRESSION, DESCRIPTION "
        "FROM INSURE360_APP.CONFIG.INTERFACE_CONTRACTS WHERE INTERFACE_NAME = ? ORDER BY COLUMN_ORDER",
        params=[iface_name],
    )


@st.cache_data(ttl=60)
def load_existing_col_maps(iface_name):
    return conn.query(
        "SELECT INTERFACE_COLUMN, SOURCE_EXPRESSION "
        "FROM INSURE360_APP.CONFIG.COLUMN_MAPPING WHERE INTERFACE_NAME = ? AND IS_ACTIVE = TRUE",
        params=[iface_name],
    )


@st.cache_data(ttl=60)
def load_value_maps():
    return conn.query("""
        SELECT INTERFACE_NAME, INTERFACE_COLUMN, SOURCE_VALUE, TARGET_VALUE, IS_DEFAULT
        FROM INSURE360_APP.CONFIG.VALUE_MAPPING ORDER BY INTERFACE_NAME, INTERFACE_COLUMN
    """)


@st.cache_data(ttl=120)
def load_mapped_ifaces():
    return conn.query(
        "SELECT DISTINCT INTERFACE_NAME FROM INSURE360_APP.CONFIG.SOURCE_TABLE_MAPPING "
        "WHERE IS_ACTIVE = TRUE ORDER BY 1"
    )


def get_source_table_for_iface(iface_name):
    df = conn.query(
        "SELECT SOURCE_DATABASE, SOURCE_SCHEMA, SOURCE_TABLE "
        "FROM INSURE360_APP.CONFIG.SOURCE_TABLE_MAPPING "
        "WHERE INTERFACE_NAME = ? AND IS_ACTIVE = TRUE AND JOIN_ORDER = 0 LIMIT 1",
        params=[iface_name],
    )
    if not df.empty:
        return df.iloc[0]["SOURCE_DATABASE"], df.iloc[0]["SOURCE_SCHEMA"], df.iloc[0]["SOURCE_TABLE"]
    return None, None, None


# ── Tab layout ──
tab_status, tab_bulk, tab_tables, tab_columns, tab_values, tab_generate = st.tabs([
    "Mapping Status", "Bulk Import", "Map Tables", "Map Columns", "Value Translations", "Validate & Generate"
])


# =====================================================================
# TAB 1: Mapping Status Dashboard
# =====================================================================
with tab_status:
    st.subheader("Current Mapping Status")

    if st.button("Refresh status", key="refresh_status", icon=":material/refresh:"):
        load_mapping_status.clear()

    df_status = load_mapping_status()
    if not df_status.empty:
        with st.container(horizontal=True):
            active = len(df_status[df_status["MAPPING_STATUS"] == "ACTIVE"])
            total = len(df_status)
            st.metric("Active Interfaces", f"{active}/{total}", border=True)
            avg_pct = df_status["MAPPING_COMPLETENESS_PCT"].mean()
            st.metric("Avg Completeness", f"{avg_pct:.0f}%" if pd.notna(avg_pct) else "N/A", border=True)

        for _, row in df_status.iterrows():
            status = row["MAPPING_STATUS"]
            icon = {"ACTIVE": ":material/check_circle:", "VALIDATED": ":material/verified:",
                    "IN_PROGRESS": ":material/pending:", "NOT_STARTED": ":material/cancel:",
                    "ERROR": ":material/error:"}.get(status, ":material/help:")
            pct = row["MAPPING_COMPLETENESS_PCT"]
            pct_str = f"{pct:.0f}%" if pd.notna(pct) else "0%"
            src = row["SOURCE_TABLE"] if pd.notna(row["SOURCE_TABLE"]) else "Not mapped"

            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                c1.markdown(f"{icon} **{row['INTERFACE_NAME']}**")
                c2.caption(f"Source: `{src}`")
                c3.caption(f"Mapped: {row['MAPPED_COLUMNS'] or 0}/{row['TOTAL_COLUMNS'] or 0}")
                c4.caption(f"**{pct_str}**")
    else:
        st.info("No mapping data found. Start by mapping tables in the next tab.")


# =====================================================================
# TAB 2: Bulk Import (CSV/Excel template)
# =====================================================================
with tab_bulk:
    st.subheader("Bulk Mapping via CSV / Excel")
    st.markdown("""
    **Fastest way to onboard:** Download the mapping template, fill it in Excel or
    Google Sheets, then upload it here. The app will create all table mappings, column
    mappings, and value translations in one shot.
    """)

    # ── Step 1: Download Template ──
    with st.container(border=True):
        st.markdown("**Step 1: Download Mapping Template**")
        st.caption("The template contains all interface views and their required/optional columns.")

        @st.cache_data(ttl=600)
        def generate_template():
            contracts = conn.query("""
                SELECT INTERFACE_NAME, COLUMN_NAME, DATA_TYPE, IS_REQUIRED,
                       DEFAULT_EXPRESSION, DESCRIPTION, COLUMN_ORDER
                FROM INSURE360_APP.CONFIG.INTERFACE_CONTRACTS
                ORDER BY INTERFACE_NAME, COLUMN_ORDER
            """)
            if contracts.empty:
                return pd.DataFrame()

            template = pd.DataFrame({
                "INTERFACE_NAME": contracts["INTERFACE_NAME"],
                "INTERFACE_COLUMN": contracts["COLUMN_NAME"],
                "DATA_TYPE": contracts["DATA_TYPE"],
                "IS_REQUIRED": contracts["IS_REQUIRED"],
                "DESCRIPTION": contracts["DESCRIPTION"],
                "SOURCE_DATABASE": "",
                "SOURCE_SCHEMA": "",
                "SOURCE_TABLE": "",
                "SOURCE_COLUMN_OR_EXPRESSION": "",
                "VALUE_MAPPINGS": "",
                "DEFAULT_VALUE": contracts["DEFAULT_EXPRESSION"].fillna(""),
                "NOTES": "",
            })
            return template

        template_df = generate_template()

        if not template_df.empty:
            st.dataframe(template_df.head(10), use_container_width=True, hide_index=True)
            st.caption(f"Template has {len(template_df)} rows across {template_df['INTERFACE_NAME'].nunique()} interfaces.")

            csv_data = template_df.to_csv(index=False)
            st.download_button(
                "Download CSV Template",
                data=csv_data,
                file_name="insure360_mapping_template.csv",
                mime="text/csv",
                icon=":material/download:",
                use_container_width=True,
            )

            st.markdown("""
            **How to fill the template:**

            | Column | What to enter | Example |
            |--------|--------------|---------|
            | `SOURCE_DATABASE` | Your database name | `ACME_INSURANCE` |
            | `SOURCE_SCHEMA` | Your schema name | `DBO` |
            | `SOURCE_TABLE` | Your table name | `tbl_Clients` |
            | `SOURCE_COLUMN_OR_EXPRESSION` | Your column name prefixed with `T0.`, or a SQL expression | `T0.FName` or `T0.ClientID::VARCHAR` |
            | `VALUE_MAPPINGS` | Semicolon-separated translations: `source=target;source=target` | `M=Male;F=Female;O=Other` |
            | `DEFAULT_VALUE` | Default if column is not mapped (pre-filled from contract) | `'STANDARD'` |
            | `NOTES` | Your notes (ignored during import) | `Cast needed` |

            Leave `SOURCE_COLUMN_OR_EXPRESSION` empty for columns you don't want to map (optional columns will use the default or NULL).
            """)

    st.divider()

    # ── Step 2: Upload Filled Template ──
    with st.container(border=True):
        st.markdown("**Step 2: Upload & Validate**")

        uploaded_file = st.file_uploader(
            "Upload your filled CSV or Excel file",
            type=["csv", "xlsx", "xls"],
            key="bulk_upload",
        )

        if uploaded_file:
            try:
                if uploaded_file.name.endswith(".csv"):
                    df_upload = pd.read_csv(uploaded_file)
                else:
                    df_upload = pd.read_excel(uploaded_file)
            except Exception as e:
                st.error(f"Failed to read file: {e}")
                df_upload = pd.DataFrame()

            if not df_upload.empty:
                required_cols = {"INTERFACE_NAME", "INTERFACE_COLUMN", "SOURCE_DATABASE",
                                 "SOURCE_SCHEMA", "SOURCE_TABLE", "SOURCE_COLUMN_OR_EXPRESSION"}
                missing = required_cols - set(df_upload.columns)
                if missing:
                    st.error(f"Missing required columns: {', '.join(missing)}")
                else:
                    df_upload = df_upload.fillna("")

                    mapped_rows = df_upload[df_upload["SOURCE_COLUMN_OR_EXPRESSION"].str.strip() != ""].copy()
                    table_maps = df_upload[df_upload["SOURCE_TABLE"].str.strip() != ""].drop_duplicates(
                        subset=["INTERFACE_NAME", "SOURCE_DATABASE", "SOURCE_SCHEMA", "SOURCE_TABLE"]
                    ).copy()
                    value_rows = df_upload[df_upload.get("VALUE_MAPPINGS", pd.Series(dtype=str)).str.strip() != ""].copy()

                    with st.container(horizontal=True):
                        st.metric("Table Mappings", len(table_maps), border=True)
                        st.metric("Column Mappings", len(mapped_rows), border=True)
                        st.metric("Value Translations", len(value_rows), border=True)

                    # ══════════════════════════════════════════════════════
                    # VALIDATION: Check all mappings against actual metadata
                    # ══════════════════════════════════════════════════════
                    st.divider()
                    st.markdown("**Validation Results**")

                    # Cache of actual columns per table: {(DB,SCHEMA,TABLE): set(col_names)}
                    @st.cache_data(ttl=300)
                    def get_actual_columns(db, schema, table):
                        rows = session.sql(
                            f"SELECT COLUMN_NAME FROM \"{db}\".INFORMATION_SCHEMA.COLUMNS "
                            f"WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'"
                        ).collect()
                        return {r["COLUMN_NAME"] for r in rows} if rows else set()

                    @st.cache_data(ttl=300)
                    def get_actual_tables(db, schema):
                        rows = session.sql(
                            f"SELECT TABLE_NAME FROM \"{db}\".INFORMATION_SCHEMA.TABLES "
                            f"WHERE TABLE_SCHEMA = '{schema}'"
                        ).collect()
                        return {r["TABLE_NAME"] for r in rows} if rows else set()

                    @st.cache_data(ttl=300)
                    def get_actual_schemas(db):
                        rows = session.sql(
                            f"SELECT SCHEMA_NAME FROM \"{db}\".INFORMATION_SCHEMA.SCHEMATA"
                        ).collect()
                        return {r["SCHEMA_NAME"] for r in rows} if rows else set()

                    @st.cache_data(ttl=300)
                    def get_actual_databases():
                        rows = session.sql(
                            "SELECT DATABASE_NAME FROM SNOWFLAKE.INFORMATION_SCHEMA.DATABASES"
                        ).collect()
                        return {r["DATABASE_NAME"] for r in rows} if rows else set()

                    # Valid interface names from contract
                    valid_interfaces = set(
                        conn.query("SELECT DISTINCT INTERFACE_NAME FROM INSURE360_APP.CONFIG.INTERFACE_CONTRACTS")
                        ["INTERFACE_NAME"].tolist()
                    )

                    # Valid columns per interface from contract
                    contract_cols = {}
                    contract_df = conn.query(
                        "SELECT INTERFACE_NAME, COLUMN_NAME FROM INSURE360_APP.CONFIG.INTERFACE_CONTRACTS"
                    )
                    for _, r in contract_df.iterrows():
                        contract_cols.setdefault(r["INTERFACE_NAME"], set()).add(r["COLUMN_NAME"])

                    actual_dbs = get_actual_databases()
                    errors = []  # List of dicts matching the upload format + VALIDATION_ERROR

                    with st.spinner("Validating all mappings against Snowflake metadata..."):
                        progress_v = st.progress(0, text="Validating...")
                        total_v = len(mapped_rows)

                        for idx, (_, row) in enumerate(mapped_rows.iterrows()):
                            iface = str(row["INTERFACE_NAME"]).strip().upper()
                            iface_col = str(row["INTERFACE_COLUMN"]).strip().upper()
                            src_db = str(row["SOURCE_DATABASE"]).strip().upper()
                            src_sch = str(row["SOURCE_SCHEMA"]).strip().upper()
                            src_tbl = str(row["SOURCE_TABLE"]).strip().upper()
                            expr = str(row["SOURCE_COLUMN_OR_EXPRESSION"]).strip()
                            row_errors = []

                            # 1. Validate interface name
                            if iface not in valid_interfaces:
                                row_errors.append("Invalid interface name")

                            # 2. Validate interface column
                            if iface in contract_cols and iface_col not in contract_cols[iface]:
                                row_errors.append("Invalid interface column")

                            # 3. Validate source database exists
                            if src_db and src_db not in actual_dbs:
                                row_errors.append("Database not found")

                            # 4. Validate source schema exists
                            if src_db and src_sch and src_db in actual_dbs:
                                actual_schemas = get_actual_schemas(src_db)
                                if src_sch not in actual_schemas:
                                    row_errors.append("Schema not found")

                                    # 5. Validate source table exists
                                elif src_tbl:
                                    actual_tables = get_actual_tables(src_db, src_sch)
                                    if src_tbl not in actual_tables:
                                        row_errors.append("Table not found")

                                    # 6. Validate source column (if expression is a simple T0.COL reference)
                                    elif expr.startswith("T0.") and "::" not in expr and "(" not in expr:
                                        col_ref = expr.replace("T0.", "").strip().upper()
                                        actual_cols = get_actual_columns(src_db, src_sch, src_tbl)
                                        if col_ref not in actual_cols:
                                            row_errors.append("Column not found")

                            # 7. Validate value mapping syntax
                            vm_str = str(row.get("VALUE_MAPPINGS", "")).strip()
                            if vm_str:
                                for pair in vm_str.split(";"):
                                    pair = pair.strip()
                                    if pair and "=" not in pair:
                                        row_errors.append("Invalid value mapping syntax")

                            if row_errors:
                                error_row = row.to_dict()
                                error_row["VALIDATION_ERROR"] = " | ".join(row_errors)
                                errors.append(error_row)

                            progress_v.progress((idx + 1) / max(total_v, 1),
                                                text=f"Validating {idx+1}/{total_v}...")

                        progress_v.progress(1.0, text="Validation complete!")

                    # ── Display validation results ──
                    valid_count = len(mapped_rows) - len(errors)

                    if errors:
                        error_df = pd.DataFrame(errors)
                        st.error(f"Found {len(errors)} error(s) in {len(mapped_rows)} mapped rows.")

                        with st.container(horizontal=True):
                            st.metric("Valid", valid_count, border=True)
                            st.metric("Errors", len(errors), border=True)

                        st.dataframe(
                            error_df[["INTERFACE_NAME", "INTERFACE_COLUMN", "SOURCE_DATABASE",
                                      "SOURCE_SCHEMA", "SOURCE_TABLE", "SOURCE_COLUMN_OR_EXPRESSION",
                                      "VALIDATION_ERROR"]],
                            use_container_width=True, hide_index=True,
                        )

                        # Download error file in same CSV format with error comments
                        error_csv = error_df.to_csv(index=False)
                        st.download_button(
                            "Download Error Report (CSV)",
                            data=error_csv,
                            file_name="insure360_mapping_ERRORS.csv",
                            mime="text/csv",
                            icon=":material/error:",
                            use_container_width=True,
                        )
                        st.warning("Fix the errors in the file and re-upload. Only valid rows will be imported.")

                    else:
                        st.success(f"All {len(mapped_rows)} column mappings validated successfully!")

                    # ── Step 3: Import (only valid rows) ──
                    st.divider()

                    if errors:
                        # Build set of error keys to skip
                        error_keys = {
                            (str(e["INTERFACE_NAME"]).strip().upper(), str(e["INTERFACE_COLUMN"]).strip().upper())
                            for e in errors
                        }
                        valid_mapped = mapped_rows[
                            mapped_rows.apply(
                                lambda r: (str(r["INTERFACE_NAME"]).strip().upper(),
                                           str(r["INTERFACE_COLUMN"]).strip().upper()) not in error_keys,
                                axis=1
                            )
                        ].copy()
                        import_label = f"Import {len(valid_mapped)} Valid Mappings (skip {len(errors)} errors)"
                    else:
                        valid_mapped = mapped_rows
                        import_label = f"Import All {len(mapped_rows)} Mappings"

                    can_import = len(valid_mapped) > 0 or len(table_maps) > 0
                    if st.button(import_label, icon=":material/upload:", type="primary",
                                 use_container_width=True, disabled=not can_import):

                        progress = st.progress(0, text="Starting import...")
                        total_steps = len(table_maps) + len(valid_mapped) + len(value_rows)
                        step = 0

                        # 3a: Insert table mappings
                        for _, trow in table_maps.iterrows():
                            iface = str(trow["INTERFACE_NAME"]).strip().upper()
                            src_db = str(trow["SOURCE_DATABASE"]).strip().upper()
                            src_sch = str(trow["SOURCE_SCHEMA"]).strip().upper()
                            src_tbl = str(trow["SOURCE_TABLE"]).strip()
                            if iface and src_db and src_sch and src_tbl:
                                existing = conn.query(
                                    "SELECT COUNT(*) AS CNT FROM INSURE360_APP.CONFIG.SOURCE_TABLE_MAPPING "
                                    "WHERE INTERFACE_NAME = ? AND SOURCE_DATABASE = ? AND SOURCE_SCHEMA = ? "
                                    "AND SOURCE_TABLE = ? AND IS_ACTIVE = TRUE",
                                    params=[iface, src_db, src_sch, src_tbl],
                                )
                                if existing.iloc[0]["CNT"] == 0:
                                    session.sql(
                                        "INSERT INTO INSURE360_APP.CONFIG.SOURCE_TABLE_MAPPING "
                                        "(INTERFACE_NAME, SOURCE_DATABASE, SOURCE_SCHEMA, SOURCE_TABLE, JOIN_ORDER) "
                                        "VALUES (:1, :2, :3, :4, 0)",
                                        params=[iface, src_db, src_sch, src_tbl],
                                    ).collect()
                            step += 1
                            progress.progress(step / max(total_steps, 1), text=f"Tables: {iface}")

                        # 3b: Insert valid column mappings only
                        for _, crow in valid_mapped.iterrows():
                            iface = str(crow["INTERFACE_NAME"]).strip().upper()
                            col_name = str(crow["INTERFACE_COLUMN"]).strip().upper()
                            expr = str(crow["SOURCE_COLUMN_OR_EXPRESSION"]).strip()
                            if iface and col_name and expr:
                                existing_col = conn.query(
                                    "SELECT COUNT(*) AS CNT FROM INSURE360_APP.CONFIG.COLUMN_MAPPING "
                                    "WHERE INTERFACE_NAME = ? AND INTERFACE_COLUMN = ? AND IS_ACTIVE = TRUE",
                                    params=[iface, col_name],
                                )
                                if existing_col.iloc[0]["CNT"] > 0:
                                    session.sql(
                                        "UPDATE INSURE360_APP.CONFIG.COLUMN_MAPPING "
                                        "SET SOURCE_EXPRESSION = :1 "
                                        "WHERE INTERFACE_NAME = :2 AND INTERFACE_COLUMN = :3 AND IS_ACTIVE = TRUE",
                                        params=[expr, iface, col_name],
                                    ).collect()
                                else:
                                    session.sql(
                                        "INSERT INTO INSURE360_APP.CONFIG.COLUMN_MAPPING "
                                        "(INTERFACE_NAME, INTERFACE_COLUMN, SOURCE_EXPRESSION) VALUES (:1, :2, :3)",
                                        params=[iface, col_name, expr],
                                    ).collect()
                            step += 1
                            progress.progress(step / max(total_steps, 1), text=f"Columns: {iface}.{col_name}")

                        # 3c: Insert value mappings (parse "M=Male;F=Female" format)
                        for _, vrow in value_rows.iterrows():
                            iface = str(vrow["INTERFACE_NAME"]).strip().upper()
                            col_name = str(vrow["INTERFACE_COLUMN"]).strip().upper()
                            vm_str = str(vrow.get("VALUE_MAPPINGS", "")).strip()
                            if iface and col_name and vm_str:
                                pairs = [p.strip() for p in vm_str.split(";") if "=" in p]
                                for pair in pairs:
                                    src_val, tgt_val = pair.split("=", 1)
                                    src_val = src_val.strip()
                                    tgt_val = tgt_val.strip()
                                    if src_val and tgt_val:
                                        session.sql(
                                            "INSERT INTO INSURE360_APP.CONFIG.VALUE_MAPPING "
                                            "(INTERFACE_NAME, INTERFACE_COLUMN, SOURCE_VALUE, TARGET_VALUE, IS_DEFAULT) "
                                            "VALUES (:1, :2, :3, :4, FALSE)",
                                            params=[iface, col_name, src_val, tgt_val],
                                        ).collect()
                            step += 1
                            progress.progress(step / max(total_steps, 1), text=f"Values: {iface}.{col_name}")

                        progress.progress(1.0, text="Import complete!")
                        st.success(f"Imported {len(table_maps)} table(s), "
                                   f"{len(valid_mapped)} column(s), "
                                   f"{len(value_rows)} value translation group(s)."
                                   + (f" Skipped {len(errors)} error(s)." if errors else ""))

                        load_mapping_status.clear()
                        load_existing_table_maps.clear()
                        load_mapped_ifaces.clear()
                        load_value_maps.clear()

                        st.info("Go to **Validate & Generate** tab to create the interface views.")


# =====================================================================
# TAB 3: Map Source Tables (with dropdowns)
# =====================================================================
with tab_tables:
    st.subheader("Map Your Tables to Interface Views")
    st.caption("Select your database, schema, and table from the dropdowns below.")

    existing_maps = load_existing_table_maps()
    if not existing_maps.empty:
        st.markdown("**Existing Mappings:**")
        st.dataframe(existing_maps, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Add New Table Mapping:**")

    interfaces = load_interfaces()
    iface_list = interfaces["INTERFACE_NAME"].tolist() if not interfaces.empty else []

    iface = st.selectbox("Interface View", iface_list, key="tbl_iface")

    databases = load_databases()
    src_db = st.selectbox("Source Database", databases, key="tbl_db",
                          index=None, placeholder="Select database...")

    if src_db:
        schemas = load_schemas(src_db)
        src_schema = st.selectbox("Source Schema", schemas, key="tbl_schema",
                                  index=None, placeholder="Select schema...")
    else:
        src_schema = None
        st.selectbox("Source Schema", [], key="tbl_schema_disabled", disabled=True,
                     placeholder="Select a database first...")

    if src_db and src_schema:
        tables = load_tables(src_db, src_schema)
        src_table = st.selectbox("Source Table", tables, key="tbl_table",
                                 index=None, placeholder="Select table...")
    else:
        src_table = None
        st.selectbox("Source Table", [], key="tbl_table_disabled", disabled=True,
                     placeholder="Select a schema first...")

    src_filter = st.text_input("Row Filter (optional)", placeholder="e.g., STATUS != 'DELETED'",
                               key="tbl_filter")

    if src_db and src_schema and src_table:
        st.caption(f"Preview: `{src_db}.{src_schema}.{src_table}` → `{iface}`")
        cols_preview = load_source_columns(src_db, src_schema, src_table)
        if not cols_preview.empty:
            with st.expander(f"Columns in {src_table} ({len(cols_preview)} columns)"):
                st.dataframe(cols_preview, use_container_width=True, hide_index=True)

    if st.button("Add Table Mapping", icon=":material/add:", disabled=not (iface and src_db and src_schema and src_table)):
        session.sql("""
            INSERT INTO INSURE360_APP.CONFIG.SOURCE_TABLE_MAPPING
            (INTERFACE_NAME, SOURCE_DATABASE, SOURCE_SCHEMA, SOURCE_TABLE, SOURCE_FILTER, JOIN_ORDER)
            VALUES (:1, :2, :3, :4, :5, 0)
        """, params=[iface, src_db, src_schema, src_table, src_filter or None]).collect()
        st.success(f"Mapped `{src_db}.{src_schema}.{src_table}` → `{iface}`")
        load_existing_table_maps.clear()
        load_mapping_status.clear()
        load_mapped_ifaces.clear()
        st.rerun()


# =====================================================================
# TAB 3: Map Columns (with source column dropdowns)
# =====================================================================
with tab_columns:
    st.subheader("Map Columns")
    st.caption("For each interface column, pick the matching source column or write a SQL expression.")

    mapped_ifaces = load_mapped_ifaces()

    if mapped_ifaces.empty:
        st.info("Map at least one source table first (previous tab).")
    else:
        sel_iface = st.selectbox("Select Interface", mapped_ifaces["INTERFACE_NAME"].tolist(), key="col_iface")

        src_db_c, src_schema_c, src_table_c = get_source_table_for_iface(sel_iface)

        if src_db_c and src_schema_c and src_table_c:
            st.caption(f"Source table: `{src_db_c}.{src_schema_c}.{src_table_c}`")
            source_cols_df = load_source_columns(src_db_c, src_schema_c, src_table_c)
            source_col_names = source_cols_df["COLUMN_NAME"].tolist() if not source_cols_df.empty else []
            source_col_options = ["(not mapped)", "(custom expression)"] + [f"T0.{c}" for c in source_col_names]
        else:
            st.warning("No source table found for this interface. Map a table first.")
            source_col_options = ["(not mapped)", "(custom expression)"]

        contract = load_contract_columns(sel_iface)
        existing_cols = load_existing_col_maps(sel_iface)
        existing_map = {}
        if not existing_cols.empty:
            existing_map = dict(zip(existing_cols["INTERFACE_COLUMN"], existing_cols["SOURCE_EXPRESSION"]))

        st.markdown(f"**{len(contract)} columns** — {len(existing_map)} already mapped")

        with st.form(f"col_mapping_{sel_iface}"):
            mappings_to_save = []

            for _, col in contract.iterrows():
                col_name = col["COLUMN_NAME"]
                required = col["IS_REQUIRED"]
                desc = col["DESCRIPTION"] or ""
                dtype = col["DATA_TYPE"]
                existing_val = existing_map.get(col_name, "")

                label = f"{'* ' if required else ''}{col_name} ({dtype})"

                # Find current selection index
                if existing_val in source_col_options:
                    default_idx = source_col_options.index(existing_val)
                elif existing_val:
                    default_idx = 1  # custom expression
                else:
                    default_idx = 0  # not mapped

                selected = st.selectbox(label, source_col_options, index=default_idx,
                                        help=desc, key=f"col_{sel_iface}_{col_name}")

                if selected == "(custom expression)":
                    custom_val = st.text_input(f"Expression for {col_name}",
                                               value=existing_val if default_idx == 1 else "",
                                               key=f"expr_{sel_iface}_{col_name}",
                                               placeholder="e.g., T0.ClientID::VARCHAR")
                    if custom_val and custom_val != existing_val:
                        mappings_to_save.append((col_name, custom_val))
                elif selected.startswith("T0.") and selected != existing_val:
                    mappings_to_save.append((col_name, selected))

            if st.form_submit_button("Save Column Mappings", icon=":material/save:"):
                saved = 0
                for col_name, expr in mappings_to_save:
                    if col_name in existing_map:
                        session.sql(
                            "UPDATE INSURE360_APP.CONFIG.COLUMN_MAPPING SET SOURCE_EXPRESSION = :1 "
                            "WHERE INTERFACE_NAME = :2 AND INTERFACE_COLUMN = :3 AND IS_ACTIVE = TRUE",
                            params=[expr, sel_iface, col_name],
                        ).collect()
                    else:
                        session.sql(
                            "INSERT INTO INSURE360_APP.CONFIG.COLUMN_MAPPING "
                            "(INTERFACE_NAME, INTERFACE_COLUMN, SOURCE_EXPRESSION) VALUES (:1, :2, :3)",
                            params=[sel_iface, col_name, expr],
                        ).collect()
                    saved += 1
                if saved:
                    st.success(f"Saved {saved} column mapping(s) for `{sel_iface}`")
                    load_existing_col_maps.clear()
                    load_mapping_status.clear()
                    st.rerun()
                else:
                    st.info("No changes to save.")


# =====================================================================
# TAB 4: Value Translations (with dropdowns)
# =====================================================================
with tab_values:
    st.subheader("Value Translations")
    st.caption("Translate your source codes to standard values (e.g., `M` → `Male`).")

    existing_vals = load_value_maps()
    if not existing_vals.empty:
        st.dataframe(existing_vals, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Add Value Translation:**")

    mapped_ifaces_v = load_mapped_ifaces()
    iface_list_v = mapped_ifaces_v["INTERFACE_NAME"].tolist() if not mapped_ifaces_v.empty else []

    vm_iface = st.selectbox("Interface", iface_list_v, key="vm_iface",
                            index=None, placeholder="Select interface...")

    if vm_iface:
        contract_v = load_contract_columns(vm_iface)
        col_list = contract_v["COLUMN_NAME"].tolist() if not contract_v.empty else []
        vm_column = st.selectbox("Column", col_list, key="vm_column",
                                 index=None, placeholder="Select column...")
    else:
        vm_column = None
        st.selectbox("Column", [], key="vm_col_disabled", disabled=True,
                     placeholder="Select an interface first...")

    col_l, col_r = st.columns(2)
    with col_l:
        vm_source = st.text_input("Source Value", placeholder="e.g., M", key="vm_src")
    with col_r:
        vm_target = st.text_input("Standard Value", placeholder="e.g., Male", key="vm_tgt")
    vm_default = st.checkbox("Is Default (catch-all for unmapped values)?", key="vm_def")

    if st.button("Add Translation", icon=":material/add:",
                 disabled=not (vm_iface and vm_column and vm_source and vm_target)):
        session.sql(
            "INSERT INTO INSURE360_APP.CONFIG.VALUE_MAPPING "
            "(INTERFACE_NAME, INTERFACE_COLUMN, SOURCE_VALUE, TARGET_VALUE, IS_DEFAULT) "
            "VALUES (:1, :2, :3, :4, :5)",
            params=[vm_iface, vm_column, vm_source, vm_target, vm_default],
        ).collect()
        st.success(f"Added: `{vm_source}` → `{vm_target}` for {vm_iface}.{vm_column}")
        load_value_maps.clear()
        st.rerun()


# =====================================================================
# TAB 5: Validate & Generate
# =====================================================================
with tab_generate:
    st.subheader("Validate & Generate Interface Views")
    st.markdown("""
    **Step 1:** Validate your mapping is complete (all required columns mapped).
    **Step 2:** Generate the interface views the application reads from.
    """)

    col_v, col_g = st.columns(2)

    with col_v:
        with st.container(border=True):
            st.markdown("**Step 1: Validate**")
            if st.button("Run Validation", icon=":material/fact_check:", use_container_width=True):
                with st.spinner("Validating mappings..."):
                    result = session.sql("CALL INSURE360_APP.CONFIG.VALIDATE_CUSTOMER_MAPPING()").collect()
                    if result:
                        import json
                        validation = json.loads(result[0][0])
                        for item in validation:
                            status = item.get("status", "UNKNOWN")
                            iface = item.get("interface", "?")
                            mapped = item.get("mapped_columns", 0)
                            total_c = item.get("total_columns", 0)
                            icon = {"VALIDATED": ":white_check_mark:", "IN_PROGRESS": ":warning:",
                                    "NOT_STARTED": ":x:"}.get(status, ":question:")
                            st.markdown(f"{icon} **{iface}**: {status} ({mapped}/{total_c} columns)")
                    load_mapping_status.clear()

    with col_g:
        with st.container(border=True):
            st.markdown("**Step 2: Generate Views**")
            st.caption("Creates/replaces the INTERFACE views the app reads from.")

            mapped_tables = load_mapped_ifaces()
            if not mapped_tables.empty:
                gen_iface = st.selectbox("Interface to generate",
                                         ["-- All --"] + mapped_tables["INTERFACE_NAME"].tolist(),
                                         key="gen_select")
                if st.button("Generate", icon=":material/play_arrow:", use_container_width=True):
                    targets = mapped_tables["INTERFACE_NAME"].tolist() if gen_iface == "-- All --" else [gen_iface]
                    for t in targets:
                        with st.spinner(f"Generating {t}..."):
                            result = session.sql(
                                "CALL INSURE360_APP.CONFIG.GENERATE_INTERFACE_VIEW(:1)",
                                params=[t],
                            ).collect()
                            msg = result[0][0] if result else "Done"
                            if "SUCCESS" in msg:
                                st.success(msg)
                            else:
                                st.error(msg)
                    load_mapping_status.clear()
            else:
                st.info("No tables mapped yet.")

    st.divider()
    with st.container(border=True):
        st.markdown("### Onboarding Checklist")
        st.markdown("""
        1. **Grant access** — `GRANT SELECT ON <your_tables> TO ROLE INSURE360_ADMIN`
        2. **Map Tables** — Select your database → schema → table for each interface (Tab 2)
        3. **Map Columns** — Pick source columns from dropdowns or write expressions (Tab 3)
        4. **Value Translations** — Add code translations if your values differ (Tab 4)
        5. **Validate** — Check all required columns are mapped (Tab 5, Step 1)
        6. **Generate** — Create the interface views (Tab 5, Step 2)
        7. **Done** — The entire app now works with your data
        """)
