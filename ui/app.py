"""Streamlit UI for the CI pipeline. Read-only: opens data/ci.db with
mode=ro and never writes. Tables that only exist after a later pipeline
stage (insights, runs, quarantine) may be missing entirely, not just
empty, so every query is guarded against sqlite3.OperationalError."""

import json
import sqlite3
import tomllib
from datetime import timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "ci.db"

CONFIDENCE_COLOR = {"high": "green", "medium": "orange", "low": "gray"}
LOW_SIGNAL_CATEGORIES = ("marketing_content", "other")


def demote_low_signal(insights: pd.DataFrame) -> pd.DataFrame:
    """kind='stable' is load-bearing: pandas' default sort is not stable,
    and arrival order must survive within each band."""
    return insights.sort_values(
        "category", key=lambda s: s.isin(LOW_SIGNAL_CATEGORIES), kind="stable"
    )

def filter_by_title(items: pd.DataFrame, search: str) -> pd.DataFrame:
    """regex=False is load-bearing: user input like "C++" or "(" is a search
    term, not a pattern, and pandas' regex default raises on it."""
    return items[items["title"].str.contains(search, case=False, na=False, regex=False)]


st.set_page_config(page_title="CI Tool", page_icon=":material/radar:", layout="wide")


@st.cache_data(ttl=300)
def _config() -> dict:
    try:
        return tomllib.loads((REPO_ROOT / "config.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def competitor_names() -> dict[str, str]:
    return {c["id"]: c["name"] for c in _config().get("competitors", [])}


def display_name(competitor) -> str:
    if not competitor or pd.isna(competitor):
        return "Industry"
    return competitor_names().get(competitor, str(competitor).title())


def source_labels() -> dict[str, str]:
    return {s["id"]: s.get("label", s["id"]) for s in _config().get("sources", [])}


def source_label(source_id: str) -> str:
    return source_labels().get(source_id, source_id)


def category_label(slug: str) -> str:
    return slug.replace("_", " ").capitalize()


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


def _json_safe(s: str, default: list | dict):
    try:
        v = json.loads(s) if s else default
    except (json.JSONDecodeError, TypeError):
        return default
    return v if isinstance(v, type(default)) else default


def badge_line(category: str, themes: list, confidence: str) -> str:
    conf_color = CONFIDENCE_COLOR.get(confidence, "gray")
    parts = [f":blue-badge[{category_label(category)}]"]
    parts += [f":violet-badge[{t}]" for t in themes]
    parts.append(f":{conf_color}-badge[{confidence} confidence]")
    return " ".join(parts)


def competitor_groups(insights: pd.DataFrame):
    """UI order: named competitors alphabetically, industry (no competitor) last.
    fillna first: pandas NaN is unsortable against the competitor name strings."""
    competitors = insights["competitor"].fillna("")
    for name in sorted(competitors.unique(), key=lambda c: (c == "", c)):
        yield name, insights[competitors == name]


def digest_markdown(insights: pd.DataFrame, links: pd.DataFrame, date_str: str) -> str:
    lines = [f"# Competitive intelligence digest - {date_str}", ""]
    for name, group in competitor_groups(insights):
        lines.append(f"## {display_name(name)}")
        for _, ins in group.iterrows():
            lines.append(
                f"- **{ins['summary']}**"
                f" ({category_label(ins['category'])}, {ins['confidence']} confidence)"
            )
            lines.append(f"  > {ins['quote']}")
            for _, item in links[links["cluster_id"] == ins["cluster_id"]].iterrows():
                lines.append(f"  - [{source_label(item['source_id'])}]({item['url']})")
        lines.append("")
    return "\n".join(lines)


def render_insight(insight: pd.Series) -> None:
    themes = _json_safe(insight["themes"], [])
    items = query_df(
        "SELECT source_id, url, published_at FROM items WHERE cluster_id = ?",
        (insight["cluster_id"],),
    )
    dates = items["published_at"].dropna()
    published = dates.min()[:10] if not dates.empty else None
    with st.container(border=True):
        st.markdown(f"##### {insight['summary']}")
        badges = badge_line(insight["category"], themes, insight["confidence"])
        st.markdown(badges + (f" :gray[{published}]" if published else ""))
        if themes:
            st.caption(":material/target: Touches JFrog focus: " + ", ".join(themes))
        # popover, not expander: this card renders inside the per-competitor
        # expander in the digest, and expanders may not be nested
        with st.popover("Evidence", icon=":material/format_quote:"):
            st.markdown(f"> {insight['quote']}")
            for _, item in items.iterrows():
                st.caption(
                    f"[{source_label(item['source_id'])}]({item['url']})"
                    f" - published {item['published_at'] or 'unknown'}"
                )


def view_daily_digest() -> None:
    st.header(":green[:material/today:] Daily digest")
    dates = query_df("SELECT DISTINCT date(created_at) AS d FROM insights ORDER BY d DESC")
    if dates.empty:
        st.info("No insights yet - the analysis stage hasn't produced anything for this database.")
        st.caption("Operator: `uv run python -m ci_tool analyze` populates the digest.")
        return

    left, _ = st.columns([1, 3])
    with left:
        picked = st.selectbox("Digest date", dates["d"].tolist(), index=0)
    insights = query_df("SELECT * FROM insights WHERE date(created_at) = ?", (picked,))
    if insights.empty:
        st.info("No insights for this date.")
        return
    cluster_dates = query_df(
        "SELECT cluster_id, MIN(published_at) AS published_at FROM items GROUP BY cluster_id"
    )
    insights = insights.merge(cluster_dates, on="cluster_id", how="left")
    insights = demote_low_signal(
        insights.sort_values("published_at", ascending=False, na_position="last")
    )

    events = int((~insights["category"].isin(LOW_SIGNAL_CATEGORIES)).sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Insights", len(insights), border=True)
    c2.metric("Product & security events", events, border=True)
    c3.metric("Marketing & misc", len(insights) - events, border=True)
    c4.metric("Competitors covered", insights["competitor"].dropna().nunique(), border=True)

    cluster_ids = insights["cluster_id"].tolist()
    links = query_df(
        "SELECT cluster_id, source_id, url FROM items WHERE cluster_id IN"
        f" ({','.join('?' * len(cluster_ids))})",
        tuple(cluster_ids),
    )
    st.download_button(
        "Download digest (Markdown)",
        digest_markdown(insights, links, picked),
        file_name=f"digest-{picked}.md",
        mime="text/markdown",
        icon=":material/download:",
    )

    names = [name for name, _ in competitor_groups(insights)]
    picked_comp = st.pills(
        "Competitor",
        ["All"] + names,
        default="All",
        format_func=lambda n: "All" if n == "All" else display_name(n),
    )
    for name, group in competitor_groups(insights):
        if picked_comp not in (None, "All") and name != picked_comp:
            continue
        with st.expander(f"**{display_name(name)}** :gray[({len(group)})]", expanded=True):
            for _, insight in group.iterrows():
                render_insight(insight)


def view_competitor_timeline() -> None:
    st.header(":green[:material/timeline:] Competitor timeline & comparison")
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
    picked = st.pills(
        "Competitors", competitors, selection_mode="multi", default=competitors,
        format_func=display_name,
    )

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

    with st.container(border=True):
        for _, row in filtered.iterrows():
            date_str = row["published_at"].date().isoformat() if pd.notna(row["published_at"]) else "unknown"
            st.markdown(
                f"**{date_str}** :blue-badge[{category_label(row['category'])}] "
                f"**{display_name(row['competitor'])}** - {row['summary']}"
            )

    st.subheader("Insight counts by competitor and category")
    st.caption("Counts of verifiable events only; deliberately no scores.")
    counts = filtered.pivot_table(
        index="competitor", columns="category", values="cluster_id", aggfunc="count", fill_value=0
    ).rename(columns=category_label, index=display_name)
    if not counts.empty:
        st.bar_chart(counts)
    st.dataframe(counts)


def view_item_explorer() -> None:
    st.header(":green[:material/search:] Item explorer")
    items = query_df("SELECT * FROM items")
    if items.empty:
        st.info("No items in the database yet.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        source = st.selectbox(
            "Source", ["All"] + sorted(items["source_id"].dropna().unique().tolist()),
            format_func=lambda s: s if s == "All" else source_label(s),
        )
    with col2:
        competitor = st.selectbox(
            "Competitor", ["All"] + sorted(items["competitor"].dropna().unique().tolist()),
            format_func=lambda c: c if c == "All" else display_name(c),
        )
    with col3:
        search = st.text_input("Search title")

    filtered = items
    if source != "All":
        filtered = filtered[filtered["source_id"] == source]
    if competitor != "All":
        filtered = filtered[filtered["competitor"] == competitor]
    if search:
        filtered = filter_by_title(filtered, search)
    filtered = filtered.sort_values("published_at", ascending=False)

    event = st.dataframe(
        filtered[["published_at", "source_id", "trust_tier", "competitor", "title", "url"]],
        hide_index=True,
        column_config={
            "url": st.column_config.LinkColumn("url"),
            "published_at": st.column_config.DatetimeColumn("published", format="YYYY-MM-DD HH:mm"),
        },
        on_select="rerun",
        selection_mode="single-row",
    )

    if filtered.empty:
        return

    st.caption("Select a row for detail; the newest item is shown by default.")
    rows = event.selection.rows
    item = filtered.iloc[rows[0] if rows else 0]

    st.subheader(item["title"])
    st.markdown(f"[{item['url']}]({item['url']})")
    st.write(item["text"])

    detail, prov = st.columns([2, 1])
    with prov:
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
    with detail:
        insight = query_df("SELECT * FROM insights WHERE cluster_id = ?", (item["cluster_id"],))
        if insight.empty:
            st.caption("No insight for this item's cluster yet.")
        else:
            ins = insight.iloc[0]
            st.markdown("**Insight**")
            st.write(ins["summary"])
            st.markdown(f"> {ins['quote']}")
            st.caption(f"prompt_version={ins['prompt_version']} provider={ins['provider']} model={ins['model']}")


def view_run_report() -> None:
    st.header(":green[:material/monitor_heart:] Run report")

    items_count = len(query_df("SELECT id FROM items"))
    insights_count = len(query_df("SELECT cluster_id FROM insights"))
    quarantine_count = len(query_df("SELECT id FROM quarantine"))
    runs = query_df("SELECT * FROM runs ORDER BY ts DESC")
    last_run = runs.iloc[0]["ts"][:16].replace("T", " ") if not runs.empty else "never"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Items", items_count, border=True)
    c2.metric("Insights", insights_count, border=True)
    c3.metric("Held back", quarantine_count, border=True)
    c4.metric("Last run (UTC)", last_run, border=True)

    st.subheader("Runs")
    if runs.empty:
        st.info("No runs recorded yet.")
    else:
        counters = pd.json_normalize(runs["counters"].apply(lambda s: _json_safe(s, {})).tolist())
        table = pd.concat([runs[["run_id", "ts", "mode"]].reset_index(drop=True), counters], axis=1)
        st.dataframe(table, hide_index=True)

    st.subheader("Held back - failed verification")
    st.caption(
        ":material/block: These extractions could not be verified against their "
        "source text, so they were kept out of the digest rather than published. "
        "Nothing is dropped silently."
    )
    quarantine = query_df("SELECT * FROM quarantine ORDER BY ts DESC")
    if quarantine.empty:
        st.info("Nothing quarantined.")
    else:
        for _, row in quarantine.iterrows():
            with st.expander(f"{row['ts'][:16]} - {row['stage']} - {row['error'][:120]}",
                             icon=":material/block:"):
                st.caption(f"cluster {row['ref_id']}")
                st.code(row["payload"] or "")


def main() -> None:
    if not DB_PATH.exists():
        st.title("CI Tool")
        st.warning("No data yet - the pipeline hasn't run on this machine.")
        st.caption("Operator: `uv run python -m ci_tool run` from the repo root creates data/ci.db.")
        st.stop()

    page = st.navigation(
        [
            st.Page(view_daily_digest, title="Daily digest", icon=":material/today:", default=True),
            st.Page(view_competitor_timeline, title="Timeline & comparison", icon=":material/timeline:"),
            st.Page(view_item_explorer, title="Item explorer", icon=":material/search:"),
            st.Page(view_run_report, title="Run report", icon=":material/monitor_heart:"),
        ]
    )
    st.sidebar.markdown("### :green[:material/radar:] CI Tool")
    st.sidebar.caption(
        "Every insight is quote-backed and source-linked; anything that fails "
        "verification is held back and shown in the run report, never hidden."
    )
    page.run()


# streamlit run still executes this as __main__; the guard only unblocks
# test imports of demote_low_signal
if __name__ == "__main__":
    main()
