import streamlit as st
import pandas as pd
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, CustomJS, Slider, HoverTool, Div, Label
from bokeh.layouts import column, row
from bokeh.models import Range1d
from math import pi

st.set_page_config(page_title="Ultra-Smooth Shot Map", layout="wide")


# ─── Load Data ───────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_parquet("datacompleta.parquet", engine='pyarrow')
    df.columns = df.columns.str.strip()
    return df[df["xG"] > 0].copy()


df = load_data()

# ─── UI Header ───────────────────────────────────────────────────────────────
st.title("⚽ Live 'What-If' Shot Simulator")
st.write("Comprehensive shot analytics — filter by xG, explore patterns, see what makes this player dangerous.")

# ─── Player Selector ─────────────────────────────────────────────────────────
all_players = sorted(df["player"].unique())
selected_player = st.selectbox(
    "Select Striker",
    all_players,
    index=all_players.index("Cristiano Ronaldo") if "Cristiano Ronaldo" in all_players else 0,
)
player_df = df[df["player"] == selected_player].copy()


# ─────────────────────────────────────────────────────────────────────────────
# STATS COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────
def compute_stats(pdf):
    shots      = len(pdf)
    goals      = int((pdf["result"] == "Goal").sum())
    on_tgt     = int(pdf["result"].isin(["Goal", "SavedShot"]).sum())
    xg_sum     = float(pdf["xG"].sum())
    high_xg    = float(pdf["xG"].max()) if shots > 0 else 0.0
    conv_pct   = (goals / shots * 100) if shots > 0 else 0.0
    on_tgt_pct = (on_tgt / shots * 100) if shots > 0 else 0.0
    xg_per     = (xg_sum / shots) if shots > 0 else 0.0
    xg_diff    = goals - xg_sum
    
    # New stats
    blocked    = int((pdf["result"] == "BlockedShot").sum())
    missed     = int((pdf["result"] == "MissedShots").sum())
    saved      = int((pdf["result"] == "SavedShot").sum())
    post       = int((pdf["result"] == "ShotOnPost").sum())
    
    return dict(
        shots=shots, goals=goals, on_tgt=on_tgt,
        xg_sum=xg_sum, high_xg=high_xg,
        conv_pct=conv_pct, on_tgt_pct=on_tgt_pct,
        xg_per=xg_per, xg_diff=xg_diff,
        blocked=blocked, missed=missed, saved=saved, post=post,
    )


def render_stats_html(s):
    card = (
        "background:#1a1d27;border:1px solid #2e3240;border-radius:12px;"
        "padding:16px 18px;box-shadow:0 4px 24px rgba(0,0,0,0.35);width:300px;"
    )
    xg_sign  = "+" if s["xg_diff"] >= 0 else ""
    xg_color = "#00e676" if s["xg_diff"] >= 0 else "#ff5f52"

    def badge(v, c="#ffffff"):
        return f'<span style="color:{c};font-weight:700;font-size:22px;">{v}</span>'
    def lbl(t):
        return f'<span style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1px;">{t}</span>'
    def stat_row(l, v, c="#ffffff"):
        return (
            '<div style="display:flex;justify-content:space-between;align-items:baseline;'
            f'padding:6px 0;border-bottom:1px solid #2e3240;">{lbl(l)}{badge(v, c)}</div>'
        )
    def section(t):
        return f'<div style="margin-top:12px;margin-bottom:3px;">{lbl(t)}</div>'

    conv_color  = "#00e676" if s["conv_pct"]   >= 15 else "#ffcc00"
    ontgt_color = "#00e676" if s["on_tgt_pct"] >= 40 else "#ffcc00"
    
    # Shot outcome percentages
    total = s["shots"]
    goal_pct   = (s["goals"]   / total * 100) if total > 0 else 0
    saved_pct  = (s["saved"]   / total * 100) if total > 0 else 0
    missed_pct = (s["missed"]  / total * 100) if total > 0 else 0
    blocked_pct= (s["blocked"] / total * 100) if total > 0 else 0
    post_pct   = (s["post"]    / total * 100) if total > 0 else 0

    return (
        f'<div style="{card}">'
        '<div style="font-family:Segoe UI,system-ui,sans-serif;color:#fff;user-select:none;">'
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">'
        '<span style="font-size:15px;font-weight:600;color:#e2e8f0;">📊 Live Stats</span>'
        '<span style="font-size:10px;color:#4ade80;background:#1a3a2a;padding:2px 8px;'
        'border-radius:99px;border:1px solid rgba(74,222,128,0.25);">● live</span>'
        '</div>'
        
        + section("Shot Summary")
        + stat_row("Total shots",   s["shots"])
        + stat_row("Goals scored",  s["goals"],                                   "#00e676")
        + stat_row("Conversion %",  f'{s["conv_pct"]:.1f}%',                      conv_color)
        + stat_row("On-target %",   f'{s["on_tgt_pct"]:.1f}%',                    ontgt_color)
        
        + section("Shot Outcomes")
        + stat_row("⚽ Goals",      f'{goal_pct:.0f}%',   "#00e676")
        + stat_row("🧤 Saved",     f'{saved_pct:.0f}%',  "#60a5fa")
        + stat_row("❌ Missed",    f'{missed_pct:.0f}%', "#ff5f52")
        + stat_row("🚫 Blocked",   f'{blocked_pct:.0f}%',"#9ca3af")
        + (stat_row("🥅 Hit post", f'{post_pct:.0f}%',   "#f59e0b") if s["post"] > 0 else "")
        
        + section("xG Analysis")
        + stat_row("Total xG", f'{s["xg_sum"]:.2f}',            "#a78bfa")
        + stat_row("Actual goals",              s["goals"],                       "#00e676")
        + stat_row("Over / Under-perform",      f'{xg_sign}{s["xg_diff"]:.2f}',  xg_color)
        
        + section("Per-Shot Insights")
        + stat_row("Highest xG chance",  f'{s["high_xg"]:.3f}',                  "#f59e0b")
        + stat_row("Avg xG per shot",    f'{s["xg_per"]:.3f}',                   "#60a5fa")
        + '</div></div>'
    )


initial_html = render_stats_html(compute_stats(player_df))


# ─────────────────────────────────────────────────────────────────────────────
# SHOT MAP  (pitch + dots + xG slider + live stats card)
# ─────────────────────────────────────────────────────────────────────────────
source = ColumnDataSource(
    data=dict(
        x=player_df["Y"].tolist(),
        y=player_df["X"].tolist(),
        xg=player_df["xG"].tolist(),
        goal_flag=(player_df["result"] == "Goal").astype(int).tolist(),
        on_target=player_df["result"].isin(["Goal", "SavedShot"]).astype(int).tolist(),
        blocked=(player_df["result"] == "BlockedShot").astype(int).tolist(),
        missed=(player_df["result"] == "MissedShots").astype(int).tolist(),
        saved=(player_df["result"] == "SavedShot").astype(int).tolist(),
        post=(player_df["result"] == "ShotOnPost").astype(int).tolist(),
        color=["#00e676" if g else "#ff5f52" for g in (player_df["result"] == "Goal")],
        alpha=[0.85] * len(player_df),
        marker_size=[12 if g else 9 for g in (player_df["result"] == "Goal")],
        line_color=["#00e676" if g else "white" for g in (player_df["result"] == "Goal")],
    )
)

stats_div = Div(width=300, height=660, text=initial_html)

pitch = figure(
    height=520, width=340, title="",
    x_range=Range1d(-0.05, 1.05), y_range=Range1d(0.5, 1.05),
    toolbar_location=None,
    background_fill_color="#0E1117",
    border_fill_color="#0E1117",
    outline_line_color="#444444",
)
pitch.rect(x=0.5, y=0.75,  width=1.0, height=0.50, fill_alpha=0, line_color="white", line_width=2)
pitch.rect(x=0.5, y=0.91,  width=0.6, height=0.18, fill_alpha=0, line_color="white", line_width=2)
pitch.rect(x=0.5, y=0.965, width=0.3, height=0.07, fill_alpha=0, line_color="white", line_width=2)
pitch.segment(x0=0.45, y0=1.0, x1=0.55, y1=1.0, line_color="#00FF00", line_width=10)

# Use scatter instead of circle (Bokeh 3.4+ compatibility)
glyph = pitch.scatter(
    "x", "y", size="marker_size", source=source,
    fill_color="color", line_color="line_color", line_width=2,
    fill_alpha="alpha", line_alpha="alpha",
)
pitch.add_tools(HoverTool(renderers=[glyph], tooltips=[("xG", "@xg{0.00}")]))

STATS_JS = """
    const thresh    = cb_obj.value;
    const d         = source.data;
    const xg        = d['xg'];
    const goal_flag = d['goal_flag'];
    const on_target = d['on_target'];
    const blocked   = d['blocked'];
    const missed    = d['missed'];
    const saved     = d['saved'];
    const post      = d['post'];
    const color     = d['color'];
    const alpha     = d['alpha'];
    const marker_size = d['marker_size'];

    let shots=0, goals=0, onTgt=0, xgSum=0, highXg=-1;
    let nBlocked=0, nMissed=0, nSaved=0, nPost=0;

    for (let i = 0; i < xg.length; i++) {
        if (xg[i] >= thresh) {
            color[i] = goal_flag[i] ? "#00e676" : "#ff5f52";
            alpha[i] = 0.85;
            marker_size[i]  = goal_flag[i] ? 12 : 9;
            shots   += 1;
            goals   += goal_flag[i];
            onTgt   += on_target[i];
            xgSum   += xg[i];
            nBlocked+= blocked[i];
            nMissed += missed[i];
            nSaved  += saved[i];
            nPost   += post[i];
            if (xg[i] > highXg) highXg = xg[i];
        } else {
            color[i] = "#555555";
            alpha[i] = 0.25;
            marker_size[i]  = 6;
        }
    }
    source.change.emit();

    const convPct   = shots > 0 ? (goals / shots * 100) : 0;
    const onTgtPct  = shots > 0 ? (onTgt  / shots * 100) : 0;
    const xgPerShot = shots > 0 ? (xgSum  / shots)       : 0;
    const xgDiff    = goals - xgSum;
    const xgSign    = xgDiff >= 0 ? "+" : "";
    const xgColor   = xgDiff >= 0 ? "#00e676" : "#ff5f52";
    
    const goalPct   = shots > 0 ? (goals    / shots * 100) : 0;
    const savedPct  = shots > 0 ? (nSaved   / shots * 100) : 0;
    const missedPct = shots > 0 ? (nMissed  / shots * 100) : 0;
    const blockedPct= shots > 0 ? (nBlocked / shots * 100) : 0;
    const postPct   = shots > 0 ? (nPost    / shots * 100) : 0;

    function badge(v, c) { return '<span style="color:'+c+';font-weight:700;font-size:22px;">'+v+'</span>'; }
    function lbl(t)      { return '<span style="color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:1px;">'+t+'</span>'; }
    function statRow(l, v, c) {
        c = c || "#ffffff";
        return '<div style="display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;border-bottom:1px solid #2e3240;">'+lbl(l)+badge(v,c)+'</div>';
    }
    function section(t) { return '<div style="margin-top:12px;margin-bottom:3px;">'+lbl(t)+'</div>'; }

    const card = "background:#1a1d27;border:1px solid #2e3240;border-radius:12px;padding:16px 18px;box-shadow:0 4px 24px rgba(0,0,0,0.35);width:300px;";
    stats_div.text =
        '<div style="'+card+'">'
      + '<div style="font-family:Segoe UI,system-ui,sans-serif;color:#fff;user-select:none;">'
      + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">'
      +   '<span style="font-size:15px;font-weight:600;color:#e2e8f0;">📊 Live Stats</span>'
      +   '<span style="font-size:10px;color:#4ade80;background:#1a3a2a;padding:2px 8px;border-radius:99px;border:1px solid rgba(74,222,128,0.25);">● live</span>'
      + '</div>'
      + section("Shot Summary")
      + statRow("Total shots",   shots)
      + statRow("Goals scored",  goals,                                          "#00e676")
      + statRow("Conversion %",  convPct.toFixed(1)+"%",  convPct>=15  ? "#00e676" : "#ffcc00")
      + statRow("On-target %",   onTgtPct.toFixed(1)+"%", onTgtPct>=40 ? "#00e676" : "#ffcc00")
      + section("Shot Outcomes")
      + statRow("⚽ Goals",    goalPct.toFixed(0)+"%",    "#00e676")
      + statRow("🧤 Saved",   savedPct.toFixed(0)+"%",   "#60a5fa")
      + statRow("❌ Missed",  missedPct.toFixed(0)+"%",  "#ff5f52")
      + statRow("🚫 Blocked", blockedPct.toFixed(0)+"%", "#9ca3af")
      + (nPost > 0 ? statRow("🥅 Hit post", postPct.toFixed(0)+"%", "#f59e0b") : "")
      + section("xG Analysis")
      + statRow("Total xG",        xgSum.toFixed(2),              "#a78bfa")
      + statRow("Actual goals",    goals,                         "#00e676")
      + statRow("Over / Under-perform", xgSign+xgDiff.toFixed(2), xgColor)
      + section("Per-Shot Insights")
      + statRow("Highest xG chance",  highXg >= 0 ? highXg.toFixed(3) : "—", "#f59e0b")
      + statRow("Avg xG per shot",    xgPerShot.toFixed(3),                   "#60a5fa")
      + '</div></div>';
"""

xg_slider = Slider(start=0, end=1, value=0, step=0.01,
                   title="Min xG Threshold", bar_color="#ffcc00")
xg_slider.js_on_change("value", CustomJS(args=dict(source=source, stats_div=stats_div), code=STATS_JS))


# ─────────────────────────────────────────────────────────────────────────────
# xG OVERPERFORMANCE CURVE
# ─────────────────────────────────────────────────────────────────────────────
opdf = player_df.sort_values("xG", ascending=True).reset_index(drop=True)
opdf["is_goal"]      = (opdf["result"] == "Goal").astype(int)
opdf["cum_expected"] = opdf["xG"].cumsum()
opdf["cum_actual"]   = opdf["is_goal"].cumsum().astype(float)
opdf["overperf"]     = opdf["cum_actual"] - opdf["cum_expected"]

n = len(opdf)
idx          = list(range(n))
cum_expected = [0.0] + opdf["cum_expected"].tolist()
cum_actual   = [0.0] + opdf["cum_actual"].tolist()
overperf     = [0.0] + opdf["overperf"].tolist()
idx_plot     = [0] + [i + 1 for i in idx]

goal_idx     = [i + 1 for i in opdf[opdf["is_goal"] == 1].index.tolist()]
goal_y       = opdf.loc[opdf["is_goal"] == 1, "cum_actual"].tolist()
goal_xg      = opdf.loc[opdf["is_goal"] == 1, "xG"].tolist()
goal_overp   = opdf.loc[opdf["is_goal"] == 1, "overperf"].tolist()

peak_idx_in_list = int(opdf["overperf"].idxmax()) + 1
peak_overp_val   = float(opdf["overperf"].max())

op_source = ColumnDataSource(data=dict(
    idx=idx_plot, cum_expected=cum_expected,
    cum_actual=cum_actual, overperf=overperf,
))
goal_source = ColumnDataSource(data=dict(
    idx=goal_idx, y=goal_y, xg=goal_xg, overp=goal_overp,
))

y_max = max(max(cum_actual), max(cum_expected)) * 1.15 or 1

op_fig = figure(
    height=280, width=660, title="",
    x_range=Range1d(-0.5, n + 0.5), y_range=Range1d(-0.3, y_max),
    toolbar_location=None,
    background_fill_color="#0E1117",
    border_fill_color="#0E1117",
    outline_line_color="#444444",
)
op_fig.xgrid.visible = False
op_fig.ygrid.grid_line_color = "#2e3240"
op_fig.yaxis.axis_label = "Cumulative Goals"
op_fig.yaxis.axis_label_text_color = "#6b7280"
op_fig.yaxis.axis_label_text_font_size = "11px"
op_fig.yaxis.major_label_text_color = "#6b7280"
op_fig.xaxis.major_label_text_color = "#6b7280"
op_fig.xaxis.axis_label = "← Hardest shots (low xG)          Shot index (sorted by xG)          Easiest shots (high xG) →"
op_fig.xaxis.axis_label_text_color = "#6b7280"
op_fig.xaxis.axis_label_text_font_size = "10px"

# Bokeh 3.x varea (no line_color support, uses y1/y2 instead of top)
op_fig.varea(x="idx", y1=0, y2="cum_actual", source=op_source,
             fill_alpha=0.12, fill_color="#00e676")
op_fig.varea(x="idx", y1=0, y2="cum_expected", source=op_source,
             fill_alpha=0.12, fill_color="#a78bfa")
op_fig.line("idx", "cum_actual",   source=op_source, color="#00e676", line_width=2.5, legend_label="Actual goals")
op_fig.line("idx", "cum_expected", source=op_source, color="#a78bfa", line_width=2,   line_dash="dashed", legend_label="Expected (xG)")

# Use scatter instead of circle (Bokeh 3.4+ compatibility)
goal_glyph = op_fig.scatter("idx", "y", source=goal_source, marker="circle",
                            size=10, fill_color="#00e676", line_color="white", line_width=2)
op_fig.add_tools(HoverTool(renderers=[goal_glyph], tooltips=[
    ("Shot xG", "@xg{0.000}"),
    ("Overperformance", "+@overp{0.00}"),
]))

if peak_overp_val > 0:
    peak_label = Label(
        x=peak_idx_in_list, y=peak_overp_val,
        x_offset=12, y_offset=8,
        text=f"Peak +{peak_overp_val:.2f}",
        text_color="#f59e0b", text_font_size="11px", text_font_style="italic",
    )
    op_fig.add_layout(peak_label)
    op_fig.segment(x0=peak_idx_in_list, y0=0, x1=peak_idx_in_list, y1=peak_overp_val,
                   line_color="#f59e0b", line_width=1, line_dash="dotted", line_alpha=0.6)

op_fig.legend.background_fill_color = "#1a1d27"
op_fig.legend.border_line_color = "#2e3240"
op_fig.legend.label_text_color = "#c8d0dc"
op_fig.legend.label_text_font_size = "11px"
op_fig.legend.location = "top_left"

op_title = Div(width=660, height=40, text="""
<div style="font-family:Segoe UI,system-ui,sans-serif;color:#e2e8f0;
            font-size:15px;font-weight:600;padding:4px 0 2px 4px;">
    🔥 xG Overperformance Curve
    <span style="color:#6b7280;font-weight:400;font-size:12px;margin-left:10px;">
        Every jump = a goal that "shouldn't have gone in"
    </span>
</div>
""")


# ─────────────────────────────────────────────────────────────────────────────
# SHOT SITUATION BREAKDOWN (donut chart)
# ─────────────────────────────────────────────────────────────────────────────
sit_counts = player_df["situation"].value_counts().to_dict()
sit_goals  = player_df[player_df["result"] == "Goal"]["situation"].value_counts().to_dict()

situations = ["FromCorner", "SetPiece", "OpenPlay"]
sit_data = []
for s in situations:
    total = sit_counts.get(s, 0)
    goals = sit_goals.get(s, 0)
    if total > 0:
        sit_data.append({
            "situation": s,
            "attempts": total,
            "goals": goals,
            "conv": goals / total * 100,
        })

# Create donut wedges - RENAMED LOOP VARIABLE TO AVOID SHADOWING
angles = []
colors_sit = ["#00e676", "#a78bfa", "#60a5fa"]
starts = [0]
for i, sit_item in enumerate(sit_data):  # Changed from 'row' to 'sit_item'
    angle = sit_item["attempts"] / len(player_df) * 2 * pi
    angles.append(angle)
    if i < len(sit_data) - 1:
        starts.append(starts[-1] + angle)

sit_source = ColumnDataSource(data=dict(
    start=[starts[i] for i in range(len(sit_data))],
    end=[starts[i] + angles[i] for i in range(len(sit_data))],
    color=colors_sit[:len(sit_data)],
    situation=[d["situation"] for d in sit_data],
    attempts=[d["attempts"] for d in sit_data],
    goals=[d["goals"] for d in sit_data],
    conv=[d["conv"] for d in sit_data],
))

sit_fig = figure(
    height=240, width=310, title="",
    toolbar_location=None,
    x_range=(-1.3, 1.3), y_range=(-1.3, 1.3),
    background_fill_color="#0E1117",
    border_fill_color="#0E1117",
    outline_line_color="#444444",
)
sit_fig.axis.visible = False
sit_fig.grid.visible = False

sit_fig.annular_wedge(
    x=0, y=0, inner_radius=0.5, outer_radius=0.95,
    start_angle="start", end_angle="end",
    color="color", source=sit_source, alpha=0.85, line_color="white", line_width=2,
)
sit_fig.add_tools(HoverTool(tooltips=[
    ("Situation", "@situation"),
    ("Attempts", "@attempts"),
    ("Goals", "@goals"),
    ("Conversion", "@conv{0.0}%"),
]))

sit_title = Div(width=310, height=35, text="""
<div style="font-family:Segoe UI,system-ui,sans-serif;color:#e2e8f0;
            font-size:14px;font-weight:600;padding:2px 0;">
    📍 Shots by Situation
</div>
""")


# ─────────────────────────────────────────────────────────────────────────────
# SHOT TYPE BREAKDOWN (horizontal bars)
# ─────────────────────────────────────────────────────────────────────────────
type_counts = player_df["shotType"].value_counts().to_dict()
type_goals  = player_df[player_df["result"] == "Goal"]["shotType"].value_counts().to_dict()

shot_types = ["Head", "RightFoot", "LeftFoot", "OtherBodyPart"]
type_data = []
for st in shot_types:
    total = type_counts.get(st, 0)
    goals = type_goals.get(st, 0)
    if total > 0:
        type_data.append({
            "type": st,
            "attempts": total,
            "goals": goals,
            "conv": goals / total * 100,
        })

type_source = ColumnDataSource(data=dict(
    type=[d["type"] for d in type_data],
    attempts=[d["attempts"] for d in type_data],
    goals=[d["goals"] for d in type_data],
    conv=[d["conv"] for d in type_data],
))

type_fig = figure(
    height=240, width=310,
    y_range=[d["type"] for d in type_data],
    toolbar_location=None,
    background_fill_color="#0E1117",
    border_fill_color="#0E1117",
    outline_line_color="#444444",
)
type_fig.xgrid.visible = False
type_fig.ygrid.visible = False
type_fig.xaxis.major_label_text_color = "#6b7280"
type_fig.yaxis.major_label_text_color = "#c8d0dc"
type_fig.xaxis.axis_label = "Attempts"
type_fig.xaxis.axis_label_text_color = "#6b7280"
type_fig.xaxis.axis_label_text_font_size = "10px"

type_fig.hbar(y="type", right="attempts", height=0.6, source=type_source,
              fill_color="#ffcc00", line_color="white", line_width=1, alpha=0.7)
type_fig.hbar(y="type", right="goals", height=0.4, source=type_source,
              fill_color="#00e676", line_color="white", line_width=1, alpha=0.9)

type_fig.add_tools(HoverTool(tooltips=[
    ("Type", "@type"),
    ("Attempts", "@attempts"),
    ("Goals", "@goals"),
    ("Conversion", "@conv{0.0}%"),
]))

type_title = Div(width=310, height=35, text="""
<div style="font-family:Segoe UI,system-ui,sans-serif;color:#e2e8f0;
            font-size:14px;font-weight:600;padding:2px 0;">
    🦶 Shots by Type
</div>
""")


# ─────────────────────────────────────────────────────────────────────────────
# FINAL LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
top_row       = row(column(pitch, xg_slider), stats_div)
overperf_row  = column(op_title, op_fig)
breakdown_row = row(column(sit_title, sit_fig), column(type_title, type_fig))

layout = column(top_row, overperf_row, breakdown_row)

st.bokeh_chart(layout, use_container_width=True)

st.info(
    "💡 **xG Threshold** – drag right to gray out low-probability shots.  "
    "🟢 Green dots = goals &nbsp; 🔴 Red dots = misses/saved  "
    "🔥 **Overperformance curve** – every green spike is a goal that defied the odds  "
    "📊 Hover over any chart for details"
)
