"""Streamlit UI for the CI pipeline. Read-only: opens data/ci.db with
mode=ro and never writes. Tables that only exist after a later pipeline
stage (insights, runs, quarantine) may be missing entirely, not just
empty, so every query is guarded against sqlite3.OperationalError."""

import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "ci.db"

CONFIDENCE_COLOR = {"high": "green", "medium": "orange", "low": "gray"}

st.set_page_config(layout="wide", page_title="CI Tool")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=60)
def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    try:
        conn = _connect()
        try:
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows], columns=cols)


def _json_list(s: str) -> list:
    try:
        v = json.loads(s) if s else []
    except (json.JSONDecodeError, TypeError):
        return []
    return v if isinstance(v, list) else []


def _json_dict(s: str) -> dict:
    try:
        v = json.loads(s) if s else {}
    except (json.JSONDecodeError, TypeError):
        return {}
    return v if isinstance(v, dict) else {}


def render_badges(category: str, themes: list, confidence: str) -> None:
    color = CONFIDENCE_COLOR.get(confidence, "gray")
    labels = [(category, "blue")] + [(t, "violet") for t in themes] + [(confidence, color)]
    if hasattr(st, "badge"):
        cols = st.columns(len(labels))
        for col, (label, c) in zip(cols, labels):
            with col:
                st.badge(label, color=c)
    else:
        st.markdown(f"**{category}**")
        if themes:
            st.caption("themes: " + ", ".join(themes))
        st.caption(f"confidence: {confidence}")


def render_insight(insight: pd.Series) -> None:
    st.markdown(f"#### {insight['summary']}")
    themes = _json_list(insight["themes"])
    render_badges(insight["category"], themes, insight["confidence"])

    items = query_df("SELECT * FROM items WHERE cluster_id = ?", (insight["cluster_id"],))
    with st.expander("evidence"):
        st.write(insight["quote"])
        for _, item in items.iterrows():
            st.caption(
                f"[{item['source_id']}]({item['url']}) - published {item['published_at'] or 'unknown'}"
            )

    if themes:
        st.caption("Touches JFrog focus: " + ", ".join(themes))
    st.divider()


def view_daily_digest() -> None:
    st.header("Daily digest")
    dates = query_df("SELECT DISTINCT date(created_at) AS d FROM insights ORDER BY d DESC")
    if dates.empty:
        st.info("No insights yet. Run `uv run python -m ci_tool analyze` to populate the digest.")
        return

    picked = st.selectbox("Date", dates["d"].tolist(), index=0)
    insights = query_df("SELECT * FROM insights WHERE date(created_at) = ?", (picked,))
    if insights.empty:
        st.info("No insights for this date.")
        return

    # insights with no competitor are industry news; pandas turns that NULL into
    # NaN, which is unsortable against the competitor names, so name it first
    competitors = insights["competitor"].fillna("")
    for name in sorted(competitors.unique(), key=lambda c: (c == "", c)):
        st.subheader(name or "Industry")
        for _, insight in insights[competitors == name].iterrows():
            render_insight(insight)


def view_competitor_timeline() -> None:
    st.header("Competitor timeline")
    insights = query_df("SELECT * FROM insights")
    if insights.empty:
        st.info("No insights yet.")
        return

    cluster_dates = query_df(
        "SELECT cluster_id, MIN(published_at) AS published_at FROM items GROUP BY cluster_id"
    )
    merged = insights.merge(cluster_dates, on="cluster_id", how="left")
    merged["published_at"] = pd.to_datetime(merged["published_at"], utc=True, errors="coerce")

    competitors = sorted(merged["competitor"].dropna().unique().tolist())
    picked = st.multiselect("Competitors", competitors, default=competitors)

    max_date = merged["published_at"].max()
    anchor = max_date.date() if pd.notna(max_date) else pd.Timestamp.utcnow().date()
    default_range = (anchor - timedelta(days=14), anchor)
    date_range = st.date_input("Date range", value=default_range)
    start, end = date_range if isinstance(date_range, tuple) and len(date_range) == 2 else default_range

    mask = merged["competitor"].isin(picked)
    has_date = merged["published_at"].notna()
    mask &= ~has_date | merged["published_at"].dt.date.between(start, end)
    filtered = merged[mask].sort_values("published_at", ascending=False)

    if filtered.empty:
        st.info("No insights match these filters.")
        return

    for _, row in filtered.iterrows():
        date_str = row["published_at"].date().isoformat() if pd.notna(row["published_at"]) else "unknown"
        st.markdown(f"**{date_str}** - {row['competitor'] or 'Industry'} - {row['category']} - {row['summary']}")

    counts = filtered.pivot_table(
        index="competitor", columns="category", values="cluster_id", aggfunc="count", fill_value=0
    )
    if not counts.empty:
        st.bar_chart(counts)
    st.subheader("Insight counts by competitor and category")
    st.dataframe(counts)


def view_item_explorer() -> None:
    st.header("Item explorer")
    items = query_df("SELECT * FROM items")
    if items.empty:
        st.info("No items in the database yet.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        source = st.selectbox("Source", ["All"] + sorted(items["source_id"].dropna().unique().tolist()))
    with col2:
        competitor = st.selectbox("Competitor", ["All"] + sorted(items["competitor"].dropna().unique().tolist()))
    with col3:
        search = st.text_input("Search title")

    filtered = items
    if source != "All":
        filtered = filtered[filtered["source_id"] == source]
    if competitor != "All":
        filtered = filtered[filtered["competitor"] == competitor]
    if search:
        filtered = filtered[filtered["title"].str.contains(search, case=False, na=False)]

    display_cols = ["published_at", "source_id", "trust_tier", "competitor", "title", "url"]
    st.dataframe(filtered[display_cols])

    if filtered.empty:
        return

    options = (filtered["title"] + " (" + filtered["id"].str[:8] + ")").tolist()
    picked_label = st.selectbox("Select item for detail", options)
    item = filtered.iloc[options.index(picked_label)]

    st.subheader(item["title"])
    st.markdown(f"[{item['url']}]({item['url']})")
    st.write(item["text"])

    st.markdown("**Provenance**")
    st.json(
        {
            "source_id": item["source_id"],
            "trust_tier": int(item["trust_tier"]),
            "fetched_at": item["fetched_at"],
            "raw_ref": item["raw_ref"],
            "content_id": item["id"],
            "cluster_id": item["cluster_id"],
            "run_id": item["run_id"],
        }
    )

    insight = query_df("SELECT * FROM insights WHERE cluster_id = ?", (item["cluster_id"],))
    if insight.empty:
        st.caption("No insight for this item's cluster yet.")
    else:
        ins = insight.iloc[0]
        st.markdown("**Insight**")
        st.write(ins["summary"])
        st.caption(f"Quote: {ins['quote']}")
        st.caption(f"prompt_version={ins['prompt_version']} provider={ins['provider']} model={ins['model']}")


def view_run_report() -> None:
    st.header("Run report")

    items_count = len(query_df("SELECT id FROM items"))
    insights_count = len(query_df("SELECT cluster_id FROM insights"))
    quarantine_count = len(query_df("SELECT id FROM quarantine"))
    runs = query_df("SELECT * FROM runs ORDER BY ts DESC")
    last_run = runs.iloc[0]["ts"] if not runs.empty else "never"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Items", items_count)
    c2.metric("Insights", insights_count)
    c3.metric("Quarantined", quarantine_count)
    c4.metric("Last run", last_run)

    st.subheader("Runs")
    if runs.empty:
        st.info("No runs recorded yet.")
    else:
        counters = pd.json_normalize(runs["counters"].apply(_json_dict).tolist())
        table = pd.concat([runs[["run_id", "ts", "mode"]].reset_index(drop=True), counters], axis=1)
        st.dataframe(table)

    st.subheader("Quarantine")
    st.caption("Items here failed schema or grounding verification and were kept out of the digest.")
    quarantine = query_df("SELECT * FROM quarantine ORDER BY ts DESC")
    if quarantine.empty:
        st.info("Nothing quarantined.")
    else:
        for _, row in quarantine.iterrows():
            with st.expander(f"{row['ts']} - {row['stage']} - {row['ref_id']} - {row['error']}"):
                st.code(row["payload"] or "")


def main() -> None:
    if not DB_PATH.exists():
        st.title("CI Tool")
        st.warning(
            "No database found at data/ci.db. Run `uv run python -m ci_tool run` "
            "from the repo root first."
        )
        st.stop()

    st.sidebar.title("CI Tool")
    view = st.sidebar.radio(
        "View",
        ["Daily digest", "Competitor timeline", "Item explorer", "Run report"],
    )
    if view == "Daily digest":
        view_daily_digest()
    elif view == "Competitor timeline":
        view_competitor_timeline()
    elif view == "Item explorer":
        view_item_explorer()
    else:
        view_run_report()


main()
