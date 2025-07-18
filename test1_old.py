import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
import numpy as np

st.set_page_config(layout="wide")

# ---- Custom CSS ----
st.markdown("""
    <style>
    .metric-header {
        background-color: #87cefa;
        color: black;
        text-align: center;
        font-weight: bold;
        border-radius: 5px 5px 0 0;
        padding: 6px 0 6px 0;
        margin-bottom: 0px;
    }
    .metric-card {
        background: white;
        border-radius: 0 0 5px 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        padding: 8px 0 4px 0;
        margin-bottom: 10px;
        text-align: center;
    }
    .metric-value {
        font-size: 2em;
        font-weight: 600;
        color: #222;
    }
    .metric-label {
        font-size: 1em;
        color: #666;
    }
    .block-container {
        padding-top: 0rem;
    }
    </style>
""", unsafe_allow_html=True)

# ---- Load Data ----
files_and_teams = [
    ("Team Kathy Results.xlsx", "Team Kathy"),
    ("Team Kelly A. Results.xlsx", "Team Kelly"),
    ("Team Lissette A.Results.xlsx", "Team Lissette"),
]
dfs = []
for file, team in files_and_teams:
    all_sheets = pd.read_excel(file, sheet_name=None, engine='openpyxl')
    for df in all_sheets.values():
        df["Team Name"] = team
        dfs.append(df)
df_main = pd.concat(dfs, ignore_index=True)

# ---- Merge High School Data Sheet ----
high_school_df = pd.read_excel("High School Data Sheet.xlsx", engine='openpyxl')
high_school_df = high_school_df.rename(columns={"Name": "Student"})
df_main = df_main.merge(high_school_df, how="left", on="Student")

# ---- Clean up duplicate columns after merge ----
if "Form_x" in df_main.columns or "Form_y" in df_main.columns:
    df_main["Form"] = df_main.get("Form_x", pd.Series(dtype=object)).combine_first(df_main.get("Form_y", pd.Series(dtype=object)))
    df_main = df_main.drop(columns=[col for col in ["Form_x", "Form_y"] if col in df_main.columns])
if "School_x" in df_main.columns or "School_y" in df_main.columns:
    df_main["School"] = df_main.get("School_x", pd.Series(dtype=object)).combine_first(df_main.get("School_y", pd.Series(dtype=object)))
    df_main = df_main.drop(columns=[col for col in ["School_x", "School_y"] if col in df_main.columns])

# ---- Data Cleaning ----
if "School" in df_main.columns and "Student" in df_main.columns:
    df_main = df_main[~(df_main["School"].isna() & df_main["Student"].isna())]
    df_main = df_main[~((df_main["School"].astype(str).str.strip() == "") & (df_main["Student"].astype(str).str.strip() == ""))]
elif "Student" in df_main.columns:
    df_main = df_main[~(df_main["Student"].isna())]
    df_main = df_main[~(df_main["Student"].astype(str).str.strip() == "")]

subject_columns = [
    "Maths", "English", "Kiswahili", "Chemistry", "Biology", "Physics", "CRE", "Geography",
    "History", "Agriculture", "Business Studies", "French", "Computer studies", "Home Science",
    "Business studies", "Woodwork"
]
def all_subjects_empty(row):
    found_na = False
    for col in subject_columns:
        val = row.get(col, np.nan)
        sval = str(val).strip().upper()
        if sval in ["N.A", "N/A"]:
            found_na = True
        elif pd.notna(val) and sval != "":
            return False
    return not found_na
df_main = df_main[~df_main.apply(all_subjects_empty, axis=1)].reset_index(drop=True)

# ---- Add Remark Column Based on Mean Grade ----
def grade_to_remark(grade):
    if pd.isna(grade):
        return "Unknown"
    grade = str(grade).strip().upper()
    if grade in ["B", "B+", "A-", "A"]:
        return "Exceeding Expectation"
    elif grade in ["C+", "B-"]:
        return "Meeting Expectation"
    elif grade in ["C", "C-", "D+", "D", "D-", "E"]:
        return "Below Expectation"
    else:
        return "Unknown"
if "Mean Grade" in df_main.columns:
    df_main["Remark"] = df_main["Mean Grade"].apply(grade_to_remark)

# ---- Page Title ----
st.markdown("""
    <div style='background-color: #FFC300; padding: 8px; border-radius: 5px; text-align: center; margin-top: 0.2px; margin-bottom: 0.1px;'>
        <h2 style='color: black; margin: 0; font-size: 1.2em;'>Student Performance Analysis Dashboard</h2>
    </div>
""", unsafe_allow_html=True)

# ---- Layout: Main Content and Filters Side by Side ----
main_col, filter_col = st.columns([4, 1])

with filter_col:
    st.markdown("""
        <div style='background-color: #87cefa; padding: 1px 0; border-radius: 1px; text-align: center; margin-bottom: 0.1px;'>
            <span style='color: black; font-weight: bold; font-size: 16px;'>🔍 Filter Students</span>
        </div>
    """, unsafe_allow_html=True)
    team = st.multiselect("Team Name", options=sorted([str(x) for x in df_main["Team Name"].dropna().unique().tolist()]))
    period_options = sorted([str(x) for x in df_main["Period"].dropna().unique().tolist()])
    period = st.multiselect("Period (type to search)", options=period_options, max_selections=5, help="Start typing to quickly find a period.")
    school = st.multiselect("School", options=sorted([str(x) for x in df_main["School"].dropna().unique().tolist()])) if "School" in df_main.columns else []
    grade = st.multiselect("Mean Grade", options=sorted([str(x) for x in df_main["Mean Grade"].dropna().unique().tolist()])) if "Mean Grade" in df_main.columns else []
    form = st.multiselect("Form", options=sorted([str(x) for x in df_main["Form"].dropna().unique().tolist()])) if "Form" in df_main.columns else []
    donor = st.multiselect("Donor", options=sorted([str(x) for x in df_main["Donor"].dropna().unique().tolist()])) if "Donor" in df_main.columns else []
    county = st.multiselect("Home County", options=sorted([str(x) for x in df_main["Home County"].dropna().unique().tolist()])) if "Home County" in df_main.columns else []
    marks_range = st.slider("% Marks", 0, 150, (0, 150))

# ---- Apply Filters ----
filtered = df_main.copy()
if team:
    filtered = filtered[filtered["Team Name"].astype(str).isin(team)]
if period:
    filtered = filtered[filtered["Period"].astype(str).isin(period)]
if school:
    filtered = filtered[filtered["School"].astype(str).isin(school)]
if grade:
    filtered = filtered[filtered["Mean Grade"].astype(str).isin(grade)]
if form:
    filtered = filtered[filtered["Form"].astype(str).isin(form)]
if donor:
    filtered = filtered[filtered["Donor"].astype(str).isin(donor)]
if county:
    filtered = filtered[filtered["Home County"].astype(str).isin(county)]
if "M%" in filtered.columns:
    filtered = filtered[(filtered["M%"] >= marks_range[0]) & (filtered["M%"] <= marks_range[1])]
filtered = filtered.copy()

# Ensure subject columns are numeric for calculations
for col in subject_columns:
    if col in filtered.columns:
        filtered[col] = pd.to_numeric(filtered[col], errors='coerce')

with main_col:
    # ---- Summary Metrics ----
    st.markdown("---")
    main_cols = st.columns(4)

    with main_cols[0]:
        st.markdown('<div class="metric-header">Number of Students</div>', unsafe_allow_html=True)
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Number of Students</div>
                <div class="metric-value">{filtered.shape[0]}</div>
            </div>
        """, unsafe_allow_html=True)

    with main_cols[1]:
        st.markdown('<div class="metric-header">Average Score in Languages</div>', unsafe_allow_html=True)
        lang_cols = st.columns(2)
        for i, (label, value) in enumerate([("English", filtered["English"].mean()), ("Kiswahili", filtered["Kiswahili"].mean())]):
            display_value = f"{value:.0f}" if pd.notnull(value) else "--"
            with lang_cols[i]:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">{label}</div>
                        <div class="metric-value">{display_value}</div>
                    </div>
                """, unsafe_allow_html=True)

    with main_cols[2]:
        st.markdown('<div class="metric-header">Average Score in Sciences</div>', unsafe_allow_html=True)
        sci_cols = st.columns(3)
        sci_metrics = [("Chemistry", filtered["Chemistry"].mean()), ("Biology", filtered["Biology"].mean()), ("Maths", filtered["Maths"].mean())]
        for i, (label, value) in enumerate(sci_metrics):
            display_value = f"{value:.0f}" if pd.notnull(value) else "--"
            with sci_cols[i]:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">{label}</div>
                        <div class="metric-value">{display_value}</div>
                    </div>
                """, unsafe_allow_html=True)

    with main_cols[3]:
        st.markdown('<div class="metric-header">Average Score in Humanities</div>', unsafe_allow_html=True)
        hum_metrics = []
        if "CS" in filtered.columns:
            hum_metrics.append(("CS", filtered["CS"].mean()))
        hum_metrics += [("Geography", filtered["Geography"].mean()), ("Agriculture", filtered["Agriculture"].mean())]
        hum_cols = st.columns(len(hum_metrics))
        for i, (label, value) in enumerate(hum_metrics):
            display_value = f"{value:.0f}" if pd.notnull(value) else "--"
            with hum_cols[i]:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">{label}</div>
                        <div class="metric-value">{display_value}</div>
                    </div>
                """, unsafe_allow_html=True)

    # ---- Charts ----
    st.markdown("---")
    chart1, chart2 = st.columns(2)

    if "Remark" in filtered.columns:
        remark_counts = filtered["Remark"].value_counts()
        fig1 = px.pie(
            values=remark_counts.values,
            names=remark_counts.index,
            title="Student Remarks",
            color_discrete_sequence=["#FFA500"]
        )
        chart1.plotly_chart(fig1, use_container_width=True)

    if "Mean Grade" in filtered.columns:
        grade_counts = filtered["Mean Grade"].value_counts()
        if len(grade_counts) > 0:
            fig2 = px.bar(
                x=grade_counts.index.tolist(),
                y=grade_counts.values.tolist(),
                labels={"x": "Grade", "y": "Count"},
                title="Student Count by Grade",
                color_discrete_sequence=["#3498db"]
            )
            chart2.plotly_chart(fig2, use_container_width=True)
        else:
            chart2.info("No grade data available for this selection.")

    chart3, chart4 = st.columns(2)
    existing_subjects = [sub for sub in subject_columns if sub in filtered.columns]
    if existing_subjects:
        subject_avg = filtered[existing_subjects].mean().sort_values()
        concern_subjects = subject_avg[subject_avg < 60]
        if not concern_subjects.empty:
            fig3 = px.bar(
                x=concern_subjects.index,
                y=concern_subjects.values,
                labels={"x": "Subject", "y": "Average Marks"},
                title="Subjects of Concern (Avg < 60%)",
                color_discrete_sequence=["#FFA500"]
            )
            chart3.plotly_chart(fig3, use_container_width=True)
        else:
            chart3.info("No subjects of concern (all averages >= 60%).")

    if "M%" in filtered.columns and "Student" in filtered.columns:
        top_students = filtered.sort_values(by="M%", ascending=False).head(5)
        fig4 = px.bar(
            top_students,
            x="Student",
            y="M%",
            title="Top 5 Students by M%",
            color_discrete_sequence=["#2ecc71"]
        )
        chart4.plotly_chart(fig4, use_container_width=True)

    # ---- Data Table ----
    st.markdown("---")
    st.subheader("📋 Detailed Student Data")
    st.dataframe(filtered)

    # ---- Box Plot for Subjects of Concern ----
    if not concern_subjects.empty:
        fig_box = px.box(
            filtered.melt(value_vars=concern_subjects.index, var_name="Subject", value_name="Score"),
            x="Subject",
            y="Score",
            title="Score Distribution for Subjects of Concern",
            color="Subject"
        )
        st.plotly_chart(fig_box, use_container_width=True)

        fig_violin = px.violin(
            filtered.melt(value_vars=concern_subjects.index, var_name="Subject", value_name="Score"),
            x="Subject",
            y="Score",
            box=True,
            points="all",
            title="Score Distribution (Violin) for Subjects of Concern",
            color="Subject"
        )
        st.plotly_chart(fig_violin, use_container_width=True)

        heatmap_data = filtered[concern_subjects.index]
        fig_heatmap = ff.create_annotated_heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns.tolist(),
            y=filtered["Student"].astype(str).tolist(),
            colorscale='YlOrRd'
        )
        fig_heatmap.update_layout(title="Student Scores Heatmap for Subjects of Concern")
        st.plotly_chart(fig_heatmap, use_container_width=True)

    # ---- 3D Scatter Plot ----
    if all(sub in filtered.columns for sub in ["Maths", "English", "Chemistry"]):
        fig_3d = px.scatter_3d(
            filtered,
            x="Maths",
            y="English",
            z="Chemistry",
            color="Mean Grade",
            hover_name="Student",
            title="3D Scatter: Maths vs English vs Chemistry"
        )
        st.plotly_chart(fig_3d, use_container_width=True)

    # ---- Parallel Coordinates Plot ----
    if all(sub in filtered.columns for sub in ["Maths", "English", "Chemistry", "Biology"]):
        fig_parallel = px.parallel_coordinates(
            filtered,
            dimensions=["Maths", "English", "Chemistry", "Biology"],
            color="M%" if "M%" in filtered.columns else None,
            labels={c: c for c in ["Maths", "English", "Chemistry", "Biology"]},
            title="Parallel Coordinates: Subject Scores"
        )
        st.plotly_chart(fig_parallel, use_container_width=True)

    # ---- Radar Chart for Average Subject Scores ----
    avg_scores = filtered[subject_columns].mean()
    categories = [sub for sub in subject_columns if sub in filtered.columns]
    if categories:
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=avg_scores[categories],
            theta=categories,
            fill='toself',
            name='Average Score'
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            title="Average Subject Scores (Radar Chart)"
        )
        st.plotly_chart(fig_radar, use_container_width=True)

