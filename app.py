import streamlit as st
import pandas as pd
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, CustomJS, Slider, HoverTool, Div, Range1d
import os

st.set_page_config(page_title="Striker Efficiency Lab", layout="wide")

# ─── 1. Load Data ──────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    # Attempt to read the parquet file
    df = pd.read_parquet("datacompleta.parquet", engine='pyarrow')
    df.columns = df.columns.str.strip()
    return df[df["xG"] > 0].copy()

df = load_data()

# ─── 2. Selection & Toggles ────────────────────────────────────────────────
st.title("🎯 Striker Efficiency Lab")

all_players = sorted(df["player"].unique())
selected_player = st.selectbox("Select Striker", all_players, 
                               index=all_players.index("Cristiano Ronaldo") if "Cristiano Ronaldo" in all_players else 0)

st.write("### Filter Situations")
all_situations = sorted(df['situation'].unique())
cols = st.columns(len(all_situations))
selected_situations = []
for i, sit in enumerate(all_situations):
    if cols[i].checkbox(sit, value=True):
        selected_situations.append(sit)

# Apply Filter
player_df = df[(df["player"] == selected_player) & (df["situation"].isin(selected_situations))].copy()

# DEBUG: Check if data exists for this player
if player_df.empty:
    st.warning(f"No data found for {selected_player} with selected filters.")
    st.stop()
else:
    st.sidebar.success(f"Loaded {len(player_df)} shots for {selected_player}")

# ─── 3. Prep Sources ───────────────────────────────────────────────────────
# Cumulative Source
opdf = player_df.sort_values("xG", ascending=True).reset_index(drop=True)
opdf["is_goal"] = (opdf["GOAL"] == 1).astype(int)
idx_plot = [0] + [i + 1 for i in range(len(opdf))]
cum_expected = [0.0] + opdf["xG"].cumsum().tolist()
cum_actual = [0.0] + opdf["is_goal"].cumsum().astype(float).tolist()
op_source = ColumnDataSource(data=dict(idx=idx_plot, cum_expected=cum_expected, cum_actual=cum_actual))

# Map Source
source = ColumnDataSource(data=dict(
    x=player_df["Y"].tolist(),
    y=player_df["X"].tolist(),
    xg=player_df["xG"].tolist(),
    goal_flag=(player_df["GOAL"] == 1).astype(int).tolist(),
    color=["#00e676" if g == 1 else "#ff5f52" for g in player_df["GOAL"]],
    alpha=[0.85] * len(player_df),
    size=[12 if g == 1 else 8 for g in player_df["GOAL"]],
    line_color=["#00e676" if g == 1 else "white" for g in player_df["GOAL"]]
))

# ─── 4. Build Plots ────────────────────────────────────────────────────────

# A. The Stats HTML
stats_div = Div(width=350, height=300) # JS will fill this

# B. The Pitch
pitch = figure(height=550, width=450, toolbar_location=None,
               x_range=Range1d(-0.05, 1.05), y_range=Range1d(0.5, 1.05),
               background_fill_color="#0E1117", border_fill_color="#0E1117", 
               outline_line_color="#444444", match_aspect=True)

pitch.rect(x=0.5, y=0.75, width=1.0, height=0.50, fill_alpha=0, line_color="white", line_width=2)
pitch.rect(x=0.5, y=0.91, width=0.6, height=0.18, fill_alpha=0, line_color="white", line_width=2)
pitch.rect(x=0.5, y=0.965, width=0.3, height=0.07, fill_alpha=0, line_color="white", line_width=2)
pitch.segment(x0=0.45, y0=1.0, x1=0.55, y1=1.0, line_color="#00FF00", line_width=10)

glyph = pitch.circle("x", "y", size="size", source=source, fill_color="color", 
                     line_color="line_color", fill_alpha="alpha")
pitch.add_tools(HoverTool(renderers=[glyph], tooltips=[("xG", "@xg{0.00}")]))

# C. Cumulative Chart
op_fig = figure(height=300, title="Cumulative performance (Hardest to Easiest Shots)",
                toolbar_location=None, background_fill_color="#0E1117", border_fill_color="#0E1117")
op_fig.varea(x="idx", y1=0, y2="cum_actual", source=op_source, fill_alpha=0.1, fill_color="#00e676")
op_fig.line("idx", "cum_actual", source=op_source, color="#00e676", line_width=3, legend_label="Actual Goals")
op_fig.line("idx", "cum_expected", source=op_source, color="#a78bfa", line_width=2, line_dash="dashed", legend_label="Expected")
op_fig.legend.location = "top_left"
op_fig.legend.background_fill_alpha = 0
op_fig.legend.label_text_color = "white"

# ─── 5. JavaScript (Stability update) ───────────────────────────────────────
JS_CODE = """
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
            size[i] = goal_flag[i] ? 12 : 8;
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

    stats_div.text = '<div style="background:#1a1d27; border:1px solid #2e3240; border-radius:12px; padding:20px; color:white; font-family:sans-serif;">' +
        '<div style="display:flex; justify-content:space-between; align-items:center;">' +
        '<span style="color:#6b7280; font-size:12px; font-weight:bold;">EFFICIENCY LAB</span>' +
        '<span style="background:#2e3240; padding:4px 12px; border-radius:8px; color:#FFD700; font-weight:bold;">GRADE: ' + grade + '</span>' +
        '</div>' +
        '<div style="margin-top:20px;">' +
        '<p>Goals: <span style="color:#00e676; float:right;"><b>' + goals + '</b></span></p>' +
        '<p>Total xG: <span style="color:#a78bfa; float:right;"><b>' + xgSum.toFixed(2) + '</b></span></p>' +
        '<p>Lethality: <span style="color:#FFD700; float:right;"><b>' + lethality.toFixed(2) + 'x</b></span></p>' +
        '<p>Over/Under: <span style="color:' + diffColor + '; float:right;"><b>' + (xgDiff >= 0 ? '+' : '') + xgDiff.toFixed(2) + '</b></span></p>' +
        '<p>Conversion: <span style="float:right;"><b>' + convPct.toFixed(1) + '%</b></span></p>' +
        '</div></div>';
"""

xg_slider = Slider(start=0, end=0.7, value=0, step=0.01, title="Min xG Quality Filter", bar_color="#ffcc00")
callback = CustomJS(args=dict(source=source, stats_div=stats_div), code=JS_CODE)
xg_slider.js_on_change("value", callback)

# ─── 6. Render Layout (Using Streamlit Columns for Stability) ───────────────
col_map, col_stats = st.columns([1.5, 1])

with col_map:
    st.bokeh_chart(pitch, use_container_width=True)
    st.bokeh_chart(xg_slider, use_container_width=True)

with col_stats:
    st.bokeh_chart(stats_div, use_container_width=True)

st.bokeh_chart(op_fig, use_container_width=True)
