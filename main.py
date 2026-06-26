"""
QA Automation Burn-Down Forecasting Tool — Streamlit App
=========================================================
Run with: streamlit run qa_burndown_streamlit.py
"""

import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import date, datetime
import warnings
warnings.filterwarnings("ignore")

# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="QA Burn-Down Forecaster",
    page_icon="📉",
    layout="wide",
)

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

st.title("📉 QA Automation Burn-Down Forecaster")
st.caption("Adjust variables in the sidebar. The chart and table update instantly.")

# =============================================================================
# SIDEBAR — EDITABLE VARIABLES
# =============================================================================
with st.sidebar:
    st.header("⚙️ Baseline Variables")

    total_manual = st.number_input("Total Manual Test Cases", min_value=0, value=1400, step=10)
    total_auto   = st.number_input("Total Automated Test Cases", min_value=0, value=736, step=10)
    new_manual   = st.number_input("New Manual Cases per Release", min_value=0, value=0, step=5)
    fixed_per_rel = st.number_input(
        "Automated Cases Needing Fixes per Release",
        min_value=0, value=20, step=5,
        help=(
            "Automated test cases that break each release due to UI/logic changes "
            "(e.g. a moved button) and must be reworked by the QA team. "
            "This consumes capacity that would otherwise go toward new automation."
        ),
    )
    qa_engineers = st.number_input("Current QA Engineers", min_value=0.5, value=4.5, step=0.5)

    st.divider()
    st.header("📅 Release Schedule")
    st.caption("First date = current start point")

    default_dates = [
        date(2026, 7, 26),
        date(2026, 9, 26),
        date(2027, 1, 26),
        date(2027, 4, 26),
        date(2027, 7, 26),
        date(2027, 9, 26),
    ]
    release_dates = []
    for i, d in enumerate(default_dates):
        label = "Start (today)" if i == 0 else f"Release {i}"
        release_dates.append(st.date_input(label, value=d, key=f"rd_{i}"))

    st.divider()
    st.header("🔀 Scenarios")
    st.caption(
        "Set the total automated cases completed per release, engineers, "
        "and expected fix burden for each scenario."
    )

    scenario_defaults = [
        ("Current Trajectory",          4.5,  50,  20, "#e05252"),
        ("+1 Engineer (5.5 QA)",        5.5,  75,  20, "#f0a050"),
        ("+2 Engineers (6.5 QA)",       6.5,  105, 15, "#e8d44d"),
        ("Accelerated + 3 Engineers",   7.5,  140, 10, "#5ec97e"),
        ("Max Push (8 QA, fast cycle)", 8.0,  180,  5, "#5ab4e5"),
    ]

    scenarios = []
    for i, (lbl, eng, auto_per_rel, fix_per_rel, col) in enumerate(scenario_defaults):
        with st.expander(f"Scenario {i+1}: {lbl}", expanded=(i == 0)):
            s_show    = st.checkbox("Show Line on Chart", value=(i == 0), key=f"show_{i}")
            s_label   = st.text_input("Label", value=lbl, key=f"lbl_{i}")
            s_eng     = st.number_input("Engineers", min_value=0.5, value=eng, step=0.5, key=f"eng_{i}")
            s_auto    = st.number_input("Auto Cases Completed per Release", min_value=0, value=auto_per_rel, step=5, key=f"aut_{i}")
            s_fixed   = st.number_input(
                "Auto Cases Needing Fixes per Release",
                min_value=0, value=fix_per_rel, step=5, key=f"fix_{i}",
                help="Overrides the global baseline for this scenario only.",
            )
            s_color   = st.color_picker("Line Color", value=col, key=f"col_{i}")
            scenarios.append({
                "label":        s_label,
                "show":         s_show,
                "engineers":    s_eng,
                "auto_per_rel": s_auto,
                "fixed_per_rel": s_fixed,
                "color":        s_color,
            })

# =============================================================================
# CORE LOGIC
# =============================================================================

def simulate_scenario(rel_dates, manual_start, new_man, auto_per_rel, fixed_per_rel):
    """
    Simulate the manual-case burn-down over releases.

    Each release:
      - new_man         → new manual cases are added to the backlog
      - auto_per_rel    → manual cases converted to automation (reduces backlog)
      - fixed_per_rel   → already-automated cases break and need rework;
                          this consumes QA capacity that would otherwise automate
                          new manual cases, so it is subtracted from net progress.

    Net change per release = new_man - (auto_per_rel - fixed_per_rel)
                           = new_man - auto_per_rel + fixed_per_rel
    """
    dates   = [rel_dates[0]]
    manual  = [manual_start]
    current = manual_start
    for i in range(1, len(rel_dates)):
        # Effective new automation = gross automation minus rework burden
        effective_auto = max(0, auto_per_rel - fixed_per_rel)
        net = new_man - effective_auto
        current = max(0, current + net)
        dates.append(rel_dates[i])
        manual.append(current)
    return dates, manual


def required_trajectory(rel_dates, manual_start, new_man, fixed_per_rel):
    """
    How many gross automated cases must the team complete per release
    (before accounting for fix burden) to reach 0 manual cases by the
    final release date?

    Solving:  manual_start + n*(new_man - (req - fixed)) = 0
    =>  req = new_man + fixed + manual_start / n
    """
    n = len(rel_dates) - 1
    if n <= 0:
        return 0
    req = new_man + fixed_per_rel + manual_start / n
    return round(req, 1)


def build_summary(sc, rel_dates, manual_start, new_man):
    auto_per_rel  = sc["auto_per_rel"]
    fixed_per_rel = sc["fixed_per_rel"]
    engineers     = sc["engineers"]
    dates, manual_counts = simulate_scenario(
        rel_dates, manual_start, new_man, auto_per_rel, fixed_per_rel
    )
    final        = manual_counts[-1]
    can_achieve  = final <= 0
    req          = required_trajectory(rel_dates, manual_start, new_man, fixed_per_rel)
    effective    = max(0, auto_per_rel - fixed_per_rel)
    per_eng      = round(effective / engineers, 1) if engineers > 0 else "N/A"
    return {
        "label":         sc["label"],
        "show":          sc.get("show", True),
        "engineers":     engineers,
        "auto_per_rel":  auto_per_rel,
        "fixed_per_rel": fixed_per_rel,
        "effective_auto": effective,
        "req":           req,
        "per_eng":       per_eng,
        "can_achieve":   can_achieve,
        "final":         max(0, int(final)),
        "dates":         dates,
        "manual":        manual_counts,
        "color":         sc["color"],
    }

# =============================================================================
# BUILD DATA
# =============================================================================

rel_dates_dt  = [datetime(d.year, d.month, d.day) for d in release_dates]
summaries     = [build_summary(sc, release_dates, total_manual, new_manual) for sc in scenarios]
# Required trajectory uses the global fix baseline for the top-metrics row
req_per_rel   = required_trajectory(release_dates, total_manual, new_manual, fixed_per_rel)
n_releases    = len(release_dates) - 1

# =============================================================================
# TOP METRICS ROW
# =============================================================================

effective_base   = max(0, scenarios[0]["auto_per_rel"] - fixed_per_rel)
req_per_eng      = round(req_per_rel / qa_engineers, 1) if qa_engineers > 0 else "N/A"
current_auto     = scenarios[0]["auto_per_rel"]
deficit          = req_per_rel - current_auto          # gross deficit
base_achieves    = summaries[0]["can_achieve"]

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric("Total Manual Cases", f"{total_manual:,}")
with col2:
    st.metric("Auto Fixes / Release (Baseline)", f"{fixed_per_rel:,}",
              help="Automated cases needing rework each release — reduces effective automation output.")
with col3:
    st.metric("Required Gross Auto / Release", f"{req_per_rel:.0f}",
              help="Gross automation needed per release (includes absorbing the fix burden) to hit zero by goal date.")
with col4:
    st.metric("Required Auto / Engineer", f"{req_per_eng}")
with col5:
    delta_str = f"+{deficit:.0f}" if deficit > 0 else f"{deficit:.0f}"
    st.metric("Automation Deficit / Release", delta_str)
with col6:
    goal_label = "✅ YES" if base_achieves else "❌ NO"
    st.metric("Current Trajectory Achieves Goal?", goal_label)

st.divider()

# =============================================================================
# CHART
# =============================================================================

fig, ax = plt.subplots(figsize=(14, 6), facecolor="#0f1117")
ax.set_facecolor("#161b22")
for spine in ax.spines.values():
    spine.set_edgecolor("#2a2d36")

# Zero line
ax.axhline(0, color="#555", lw=1, ls="--", zorder=1)

# Release date markers
for d in rel_dates_dt:
    ax.axvline(d, color="#2a2d36", lw=1, zorder=0)

# Goal deadline
goal_dt = rel_dates_dt[-1]
ax.axvline(goal_dt, color="#e05252", lw=1.5, ls=":", alpha=0.8, zorder=2)
ax.text(goal_dt, total_manual * 1.02, "  Goal\n  Sep '27",
        color="#e05252", fontsize=8, va="bottom", alpha=0.9)

# Regression growth (do nothing)
growth_y = [total_manual + i * new_manual for i in range(len(release_dates))]
ax.fill_between(rel_dates_dt, growth_y, alpha=0.07, color="#e05252", zorder=0)
ax.plot(rel_dates_dt, growth_y, color="#e05252", lw=1, ls=":",
        alpha=0.4, label="Regression Growth (no automation)")

# Fix-burden drag line — same as regression growth but also adds fix rework cost
# Shown as the "worst case" where team spends all capacity on fixes, zero new automation
fix_drag_y = [total_manual + i * (new_manual + fixed_per_rel) for i in range(len(release_dates))]
ax.plot(rel_dates_dt, fix_drag_y, color="#c060c0", lw=1, ls=":",
        alpha=0.35,
        label=f"Fix-Drag Growth (no new auto + {fixed_per_rel} fixes/release)")

# Required trajectory line (using global fix baseline)
req_manual = [total_manual]
cur = total_manual
for _ in range(n_releases):
    effective_req = req_per_rel - fixed_per_rel
    cur = max(0, cur + new_manual - effective_req)
    req_manual.append(cur)
ax.plot(rel_dates_dt, req_manual, color="#ffffff", lw=1.5, ls="-.",
        alpha=0.35, label=f"Required Trajectory ({req_per_rel:.0f} gross auto/release)")

# Scenario lines
line_styles = ["-", "--", "--", "-", "-"]
line_widths = [2.5, 2, 2, 2, 2.5]
for i, s in enumerate(summaries):
    if not s["show"]:
        continue
    dates_dt = [datetime(d.year, d.month, d.day) for d in s["dates"]]
    fix_note = f", {s['fixed_per_rel']} fixes/rel" if s["fixed_per_rel"] > 0 else ""
    suffix   = "ACHIEVES GOAL" if s["can_achieve"] else f"ends at {s['final']} manual"
    ax.plot(dates_dt, s["manual"],
            color=s["color"],
            lw=line_widths[i % len(line_widths)],
            ls=line_styles[i % len(line_styles)],
            marker="o", markersize=5, markerfacecolor=s["color"],
            label=f"{s['label']}{fix_note}  ({suffix})")

# Axes
ax.set_ylabel("Manual Test Cases Remaining", color="#cccccc", fontsize=11)
ax.set_xlabel("Release Date", color="#cccccc", fontsize=11)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 9]))
plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right", fontsize=9, color="#888")
ax.yaxis.label.set_color("#cccccc")
ax.tick_params(axis="both", colors="#888888")
ax.set_ylim(bottom=-50)
ax.grid(axis="y", color="#1f2430", lw=0.8)

ax.legend(loc="lower left", fontsize=8.5, framealpha=0.3,
          facecolor="#0f1117", edgecolor="#333", labelcolor="white")

# Annotation
note = (
    f"Baseline  |  Manual: {total_manual}  |  Automated: {total_auto}"
    f"  |  Engineers: {qa_engineers}  |  New manual/release: {new_manual}"
    f"  |  Auto fixes/release: {fixed_per_rel}"
    f"  |  Required gross auto/release: {req_per_rel:.0f}"
)
ax.text(0.01, 0.98, note, transform=ax.transAxes, fontsize=7.5,
        color="#888888", va="top", ha="left",
        bbox=dict(facecolor="#0f1117", edgecolor="#2a2d36",
                  boxstyle="round,pad=0.4", alpha=0.85))

plt.tight_layout()
st.pyplot(fig)
plt.close(fig)

# =============================================================================
# SUMMARY TABLE
# =============================================================================

st.subheader("📊 Scenario Summary")

header_cols = st.columns([2.2, 0.8, 1.1, 1.0, 1.4, 1.2, 1.2, 1.2])
headers = [
    "Scenario", "Engineers", "Gross Auto\n/Release", "Fixes\n/Release",
    "Effective Auto\n/Release", "Req'd Auto\n/Release",
    "Final Manual", "Achieves Goal?"
]
for col, h in zip(header_cols, headers):
    col.markdown(f"**{h}**")

st.markdown("<hr style='margin:4px 0 8px 0; border-color:#2a2d36'>", unsafe_allow_html=True)

for s in summaries:
    row = st.columns([2.2, 0.8, 1.1, 1.0, 1.4, 1.2, 1.2, 1.2])
    goal_icon = "✅" if s["can_achieve"] else "❌"
    vals   = [
        s["label"], s["engineers"], s["auto_per_rel"], s["fixed_per_rel"],
        s["effective_auto"], s["req"], s["final"], goal_icon,
    ]
    # Dim rows whose lines are hidden
    base_color = "white" if s["show"] else "#555555"
    colors = [base_color] * 7 + ["#5ec97e" if s["can_achieve"] else "#e05252"]
    if not s["show"]:
        colors[7] = "#555555"  # also dim the goal icon when hidden
    # Highlight effective_auto in orange if it's meaningfully dragged down by fixes
    elif s["fixed_per_rel"] > 0:
        colors[4] = "#f0a050"
    for col, val, clr in zip(row, vals, colors):
        col.markdown(f"<span style='color:{clr}'>{val}</span>", unsafe_allow_html=True)