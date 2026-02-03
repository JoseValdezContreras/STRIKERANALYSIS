import streamlit as st
import pandas as pd
import numpy as np
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, CustomJS, Slider, HoverTool, Div, Range1d
from bokeh.layouts import column, row

st.set_page_config(page_title="Striker Efficiency Lab", layout="wide")

# ─── Load Data ───────────────────────────────────────────────────────────────
# --- Update your loading logic ---
@st.cache_data
def load_data():
    # Make sure your file is named exactly this in your folder
    df = pd.read_parquet("datacompleta.parquet") 
    df.columns = df.columns.str.strip()
    return df[df["xG"] > 0].copy()

try:
    df = load_data()
    st.write(f"Total rows loaded: {len(df)}")
    st.write(f"Columns found: {list(df.columns)}")
except Exception as e:
    st.error(f"Error: Could not find the parquet file. Make sure it's in the same folder as app.py. Details: {e}")
    st.stop()

# ─── Sidebar / Top Filters ───────────────────────────────────────────────────
st.title("🎯 Striker Efficiency Lab")

# Player Selection
all_players = sorted(df["player"].unique())
selected_player = st.selectbox(
    "Select Striker",
    all_players,
    index=all_players.index("Cristiano Ronaldo") if "Cristiano Ronaldo" in all_players else 0,
)

# Situation Checkboxes (Toggles)
st.write("### Filter Situations")
all_situations = sorted(df['situation'].unique())
cols = st.columns(len(all_situations))
selected_situations = []

for i, sit in enumerate(all_situations):
    if cols[i].checkbox(sit, value=True):
        selected_situations.append(sit)

# Apply Server-side Filters
player_df = df[
    (df["player"] == selected_player) & 
    (df["situation"].isin(selected_situations))
].copy()

# ─────────────────────────────────────────────────────────────────────────────
# DATA PREPARATION FOR GRAPHS
# ─────────────────────────────────────────────────────────────────────────────

# 1. Prepare Cumulative Chart Data (Sorted by xG)
opdf = player_df.sort_values("xG", ascending=True).reset_index(drop=True)
opdf["is_goal"] = (opdf["GOAL"] == 1).astype(int)
opdf["cum_expected"] = opdf["xG"].cumsum()
opdf["cum_actual"] = opdf["is_goal"].cumsum().astype(float)

# Create Plot lists (starting from 0)
idx_plot = [0] + [i + 1 for i in range(len(opdf))]
cum_expected = [0.0] + opdf["cum_expected"].tolist()
cum_actual = [0.0] + opdf["cum_actual"].tolist()

op_source = ColumnDataSource(data=dict(idx=idx_plot, cum_expected=cum_expected, cum_actual=cum_actual))

# 2. Map Source (for the interactive pitch)
source = ColumnDataSource(
    data=dict(
        x=player_df["Y"].tolist(),
        y=player_df["X"].tolist(),
        xg=player_df["xG"].tolist(),
        goal_flag=(player_df["GOAL"] == 1).astype(int).tolist(),
        color=["#00e676" if g == 1 else "#ff5f52" for g in player_df["GOAL"]],
        alpha=[0.85] * len(player_df),
        size=[12 if g == 1 else 9 for g in player_df["GOAL"]],
        line_color=["#00e676" if g == 1 else "white" for g in player_df["GOAL"]]
    )
)

# ─────────────────────────────────────────────────────────────────────────────
# UI COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────

# 1. The Stats Div (Initial State)
def get_initial_stats():
    goals = player_df['GOAL'].sum()
    xg_sum = player_df['xG'].sum()
    lethality = goals / xg_sum if xg_sum > 0 else 0
    xg_diff = goals - xg_sum
    conv_pct = (goals / len(player_df) * 100) if len(player_df) > 0 else 0
    
    color = "#00e676" if xg_diff >= 0 else "#ff5f52"
    grade = "S" if lethality > 1.2 else "A" if lethality > 1.05 else "B" if lethality > 0.95 else "C"
    
    return f"""
    <div style="background:#1a1d27; border:1px solid #2e3240; border-radius:12px; padding:20px; color:white; width:320px; font-family: sans-serif;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="color:#6b7280; font-size:12px; font-weight:bold;">EFFICIENCY LAB</span>
            <span style="background:#2e3240; padding:4px 12px; border-radius:8px; color:#FFD700; font-weight:bold;">GRADE: {grade}</span>
        </div>
        <div style="margin-top:20px;">
            <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2e3240;">
                <span style="color:#9ca3af;">Goals</span><span style="color:#00e676; font-size:20px; font-weight:bold;">{goals}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2e3240;">
                <span style="color:#9ca3af;">Total xG</span><span style="color:#a78bfa; font-size:20px; font-weight:bold;">{xg_sum:.2f}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2e3240;">
                <span style="color:#9ca3af;">Lethality</span><span style="color:#FFD700; font-size:20px; font-weight:bold;">{lethality:.2f}x</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2e3240;">
                <span style="color:#9ca3af;">Over/Under</span><span style="color:{color}; font-size:20px; font-weight:bold;">{'+' if xg_diff >=0 else ''}{xg_diff:.2f}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:8px 0;">
                <span style="color:#9ca3af;">Conversion %</span><span style="font-size:20px; font-weight:bold;">{conv_pct:.1f}%</span>
            </div>
        </div>
    </div>
    """

stats_div = Div(text=get_initial_stats(), width=350)

# 2. Consistent Pitch
pitch = figure(
    height=550, width=400, toolbar_location=None,
    x_range=Range1d(-0.05, 1.05), y_range=Range1d(0.5, 1.05),
    background_fill_color="#0E1117", border_fill_color="#0E1117", outline_line_color="#444444",
    match_aspect=True # STOPS THE PITCH FROM STRETCHING
)

# Draw markings
pitch.rect(x=0.5, y=0.75, width=1.0, height=0.50, fill_alpha=0, line_color="white", line_width=2)
pitch.rect(x=0.5, y=0.91, width=0.6, height=0.18, fill_alpha=0, line_color="white", line_width=2)
pitch.rect(x=0.5, y=0.965, width=0.3, height=0.07, fill_alpha=0, line_color="white", line_width=2)
pitch.segment(x0=0.45, y0=1.0, x1=0.55, y1=1.0, line_color="#00FF00", line_width=10)

glyph = pitch.circle("x", "y", size="size", source=source, fill_color="color", line_color="line_color", fill_alpha="alpha")
pitch.add_tools(HoverTool(renderers=[glyph], tooltips=[("xG", "@xg{0.00}")]))

# 3. Cumulative Graph (Fixed VArea)
op_fig = figure(
    height=250, width=750, title="Cumulative Goals vs Expected",
    toolbar_location=None, background_fill_color="#0E1117", border_fill_color="#0E1117"
)

# FIXED: Using y1 and y2 instead of top
op_fig.varea(x="idx", y1=0, y2="cum_actual", source=op_source, fill_alpha=0.1, fill_color="#00e676")
op_fig.varea(x="idx", y1=0, y2="cum_expected", source=op_source, fill_alpha=0.1, fill_color="#a78bfa")

op_fig.line("idx", "cum_actual", source=op_source, color="#00e676", line_width=3, legend_label="Actual Goals")
op_fig.line("idx", "cum_expected", source=op_source, color="#a78bfa", line_width=2, line_dash="dashed", legend_label="Expected")
op_fig.legend.location = "top_left"
op_fig.legend.background_fill_alpha = 0

# ─────────────────────────────────────────────────────────────────────────────
# JAVASCRIPT LOGIC
# ─────────────────────────────────────────────────────────────────────────────
STATS_JS = """
    const thresh = cb_obj.value;
    const d = source.data;
    const xg = d['xg'];
    const goal_flag = d['goal_flag'];
    const color = d['color'];
    const alpha = d['alpha'];
    const size = d['size'];

    let shots=0, goals=0, xgSum=0;

    for (let i = 0; i < xg.length; i++) {
        if (xg[i] >= thresh) {
            color[i] = goal_flag[i] ? "#00e676" : "#ff5f52";
            alpha[i] = 0.85;
            size[i] = goal_flag[i] ? 12 : 9;
            shots++;
            goals += goal_flag[i];
            xgSum += xg[i];
        } else {
            color[i] = "#333333";
            alpha[i] = 0.1;
            size[i] = 4;
        }
    }
    source.change.emit();

    const lethality = xgSum > 0 ? (goals / xgSum) : 0;
    const xgDiff = goals - xgSum;
    const convPct = shots > 0 ? (goals / shots * 100) : 0;
    const diffColor = xgDiff >= 0 ? "#00e676" : "#ff5f52";
    let grade = "C";
    if (lethality > 1.2) grade = "S";
    else if (lethality > 1.05) grade = "A";
    else if (lethality > 0.95) grade = "B";

    stats_div.text = `
        <div style="background:#1a1d27; border:1px solid #2e3240; border-radius:12px; padding:20px; color:white; width:320px; font-family: sans-serif;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="color:#6b7280; font-size:12px; font-weight:bold;">EFFICIENCY LAB</span>
                <span style="background:#2e3240; padding:4px 12px; border-radius:8px; color:#FFD700; font-weight:bold;">GRADE: ${grade}</span>
            </div>
            <div style="margin-top:20px;">
                <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2e3240;">
                    <span style="color:#9ca3af;">Goals</span><span style="color:#00e676; font-size:20px; font-weight:bold;">${goals}</span>
                </div>
                <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2e3240;">
                    <span style="color:#9ca3af;">Total xG</span><span style="color:#a78bfa; font-size:20px; font-weight:bold;">${xgSum.toFixed(2)}</span>
                </div>
                <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2e3240;">
                    <span style="color:#9ca3af;">Lethality</span><span style="color:#FFD700; font-size:20px; font-weight:bold;">${lethality.toFixed(2)}x</span>
                </div>
                <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #2e3240;">
                    <span style="color:#9ca3af;">Over/Under</span><span style="color:${diffColor}; font-size:20px; font-weight:bold;">${xgDiff >= 0 ? '+' : ''}${xgDiff.toFixed(2)}</span>
                </div>
                <div style="display:flex; justify-content:space-between; padding:8px 0;">
                    <span style="color:#9ca3af;">Conversion %</span><span style="font-size:20px; font-weight:bold;">${convPct.toFixed(1)}%</span>
                </div>
            </div>
        </div>
    `;
"""

xg_slider = Slider(start=0, end=0.7, value=0, step=0.01, title="Minimum Shot Quality (xG)", bar_color="#ffcc00")
xg_slider.js_on_change("value", CustomJS(args=dict(source=source, stats_div=stats_div), code=STATS_JS))

# ─────────────────────────────────────────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────────────────────────────────────────
main_view = row(column(pitch, xg_slider), stats_div)
st.bokeh_chart(column(main_view, op_fig), use_container_width=False)
