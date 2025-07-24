import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
import numpy as np
import base64

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
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    .main-header {
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: white;
        padding: 10px 0;
        margin-bottom: 20px;
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
    try:
        all_sheets = pd.read_excel(file, sheet_name=None, engine='openpyxl')
        
        for sheet_name, df in all_sheets.items():
            df["Team Name"] = team
            
            # Replace NA, N/A, and similar values with "Not Appeared" across all columns
            df = df.replace({
                'NA': 'Not Appeared',
                'N/A': 'Not Appeared',
                'N.A': 'Not Appeared',
                'n/a': 'Not Appeared',
                'na': 'Not Appeared',
                'n.a': 'Not Appeared',
                'N.A.': 'Not Appeared',
                'N/A/': 'Not Appeared'
            })
            dfs.append(df)
    except Exception as e:
        st.error(f"Error loading {file}: {str(e)}")
        
df_main = pd.concat(dfs, ignore_index=True)

# ---- Merge High School Data Sheet ----
high_school_df = pd.read_excel("High School Data Sheet.xlsx", engine='openpyxl')
high_school_df = high_school_df.rename(columns={"Name": "Student"})
# Also replace NA/N/A values in the high school data sheet
high_school_df = high_school_df.replace({
    'NA': 'Not Appeared',
    'N/A': 'Not Appeared',
    'N.A': 'Not Appeared',
    'n/a': 'Not Appeared',
    'na': 'Not Appeared',
    'n.a': 'Not Appeared',
    'N.A.': 'Not Appeared',
    'N/A/': 'Not Appeared'
})
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
    "Woodwork"
]
def all_subjects_empty(row):
    # Check if all subjects are either empty/NaN or "Not Appeared"
    found_data = False
    for col in subject_columns:
        val = row.get(col, np.nan)
        if pd.notna(val):
            sval = str(val).strip()
            # If value is not empty and not "Not Appeared", we have valid data
            if sval != "" and sval != "Not Appeared":
                found_data = True
                break
    return not found_data  # Return True if no valid data found (should be dropped)

df_main = df_main[~df_main.apply(all_subjects_empty, axis=1)].reset_index(drop=True)

# ---- Calculate M% (Overall Percentage) from Subject Scores ----
def calculate_m_percentage(row):
    """Calculate overall percentage (M%) from subject scores, ignoring empty/NA/Not Appeared values"""
    valid_scores = []
    
    for col in subject_columns:
        if col in row.index:  # Check if column exists
            val = row[col]
            if pd.notna(val):  # Not NaN/None
                sval = str(val).strip()
                # Skip empty strings and "Not Appeared"
                if sval != "" and sval != "Not Appeared":
                    try:
                        # Try to convert to numeric
                        numeric_val = float(sval)
                        if 0 <= numeric_val <= 100:  # Valid score range
                            valid_scores.append(numeric_val)
                    except (ValueError, TypeError):
                        # Skip non-numeric values
                        continue
    
    # Calculate average if we have valid scores
    if len(valid_scores) > 0:
        return round(sum(valid_scores) / len(valid_scores), 2)
    else:
        return 0.0  # Return 0 if no valid scores found

# Apply M% calculation to all rows
df_main["M%"] = df_main.apply(calculate_m_percentage, axis=1)

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

# Function to convert image to base64 for embedding
def get_base64_of_image(path):
    try:
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return None

# Get logo as base64
logo_base64 = get_base64_of_image("SAM Elimu Logo-white_edited.png")

if logo_base64:
    st.markdown(f"""
        <div class="main-header">
            <div style='background-color: #FFC300; padding: 12px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); position: relative; display: flex; align-items: center; justify-content: space-between;'>
                <h1 style='color: black; margin: 0; font-size: 1.8em; font-weight: bold; flex: 1; text-align: center;'>Student Performance Analysis Dashboard</h1>
                <img src="data:image/png;base64,{logo_base64}" style="height: 120px; width: auto; margin-left: auto; padding-left: 30px;" alt="SAM Elimu Logo">
            </div>
        </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <div class="main-header">
            <div style='background-color: #FFC300; padding: 12px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); position: relative;'>
                <h1 style='color: black; margin: 0; font-size: 1.8em; font-weight: bold;'>Student Performance Analysis Dashboard</h1>
            </div>
        </div>
    """, unsafe_allow_html=True)

# ---- Tab Structure ----
tab1, tab2, tab3 = st.tabs(["📊 Overall Analysis", "👨‍🎓 Student Analysis", "📋 Detailed Data"])

with tab1:
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
        marks_range = st.slider("% Marks", 0, 100, (0, 100))

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
            # Replace "Not Appeared" with NaN for numeric calculations
            filtered[col] = filtered[col].replace("Not Appeared", np.nan)
            filtered[col] = pd.to_numeric(filtered[col], errors='coerce')

    with main_col:
        # ---- Summary Metrics ----
        st.markdown("---")
        main_cols = st.columns(4)

        with main_cols[0]:
            st.markdown('<div class="metric-header">Number of Students</div>', unsafe_allow_html=True)
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Total</div>
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
            sci_metrics = [("Chem", filtered["Chemistry"].mean()), ("Bio", filtered["Biology"].mean()), ("Math", filtered["Maths"].mean())]
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
                title="Performance Level Distribution",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig1.update_traces(hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>')
            chart1.plotly_chart(fig1, use_container_width=True)

        if "Mean Grade" in filtered.columns:
            grade_counts = filtered["Mean Grade"].value_counts()
            if len(grade_counts) > 0:
                # Define grade order for proper sorting
                grade_order = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "E"]
                # Sort grades according to the defined order
                ordered_grades = [grade for grade in grade_order if grade in grade_counts.index]
                ordered_counts = [grade_counts[grade] for grade in ordered_grades]
                
                fig2 = px.bar(
                    x=ordered_grades,
                    y=ordered_counts,
                    labels={"x": "Grade", "y": "Number of Students"},
                    title="Student Distribution by Grade",
                    color=ordered_counts,
                    color_continuous_scale="viridis"
                )
                fig2.update_traces(hovertemplate='<b>Grade %{x}</b><br>Students: %{y}<extra></extra>')
                fig2.update_layout(
                    xaxis={'categoryorder': 'array', 'categoryarray': ordered_grades},
                    showlegend=False
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
                    labels={"x": "Subject", "y": "Average Score (%)"},
                    title="Subjects Needing Attention (Avg < 60%)",
                    color=concern_subjects.values,
                    color_continuous_scale="Reds"
                )
                fig3.update_traces(hovertemplate='<b>%{x}</b><br>Average: %{y:.1f}%<extra></extra>')
                fig3.update_layout(showlegend=False, xaxis_tickangle=-45)
                chart3.plotly_chart(fig3, use_container_width=True)
            else:
                chart3.info("No subjects of concern (all averages >= 60%).")

        if "M%" in filtered.columns and "Student" in filtered.columns:
            top_students = filtered.sort_values(by="M%", ascending=False).head(5)
            if not top_students.empty:
                fig4 = px.bar(
                    top_students,
                    x="Student",
                    y="M%",
                    title="Top 5 Students by Overall Performance",
                    color="M%",
                    color_continuous_scale="Greens"
                )
                fig4.update_traces(hovertemplate='<b>%{x}</b><br>Overall Score: %{y:.1f}%<extra></extra>')
                fig4.update_layout(showlegend=False, xaxis_tickangle=-45)
                chart4.plotly_chart(fig4, use_container_width=True)

        # # ---- Box Plot for Subjects of Concern ----
        # if existing_subjects:
        #     subject_avg = filtered[existing_subjects].mean().sort_values()
        #     concern_subjects = subject_avg[subject_avg < 60]
        #     if not concern_subjects.empty:
        #         st.markdown("---")
        #         st.subheader("📈 Detailed Analysis for Subjects Needing Attention")
                
        #         fig_box = px.box(
        #             filtered.melt(value_vars=concern_subjects.index, var_name="Subject", value_name="Score"),
        #             x="Subject",
        #             y="Score",
        #             title="Score Distribution for Subjects Needing Attention",
        #             color="Subject",
        #             color_discrete_sequence=px.colors.qualitative.Set2
        #         )
        #         fig_box.update_traces(hovertemplate='<b>%{x}</b><br>Score: %{y}<extra></extra>')
        #         fig_box.update_layout(showlegend=False)
        #         st.plotly_chart(fig_box, use_container_width=True)

        #         fig_violin = px.violin(
        #             filtered.melt(value_vars=concern_subjects.index, var_name="Subject", value_name="Score"),
        #             x="Subject",
        #             y="Score",
        #             box=True,
        #             points="all",
        #             title="Score Distribution (Violin Plot) for Subjects Needing Attention",
        #             color="Subject",
        #             color_discrete_sequence=px.colors.qualitative.Pastel
        #         )
        #         fig_violin.update_traces(hovertemplate='<b>%{x}</b><br>Score: %{y}<extra></extra>')
        #         fig_violin.update_layout(showlegend=False)
        #         st.plotly_chart(fig_violin, use_container_width=True)


with tab2:
    st.markdown("### 👨‍🎓 Individual Student Analysis")
    
    # Student selector
    if "Student" in df_main.columns:
        student_list = sorted([str(x) for x in df_main["Student"].dropna().unique().tolist()])
        selected_student = st.selectbox("Select a Student", options=student_list)
        
        if selected_student:
            # Filter data for selected student
            student_data = df_main[df_main["Student"] == selected_student]
            
            if not student_data.empty:
                # Student info section
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 📊 Student Information")
                    if "School" in student_data.columns:
                        st.write(f"**School:** {student_data['School'].iloc[0] if not pd.isna(student_data['School'].iloc[0]) else 'N/A'}")
                    if "Form" in student_data.columns:
                        st.write(f"**Form:** {student_data['Form'].iloc[0] if not pd.isna(student_data['Form'].iloc[0]) else 'N/A'}")
                    if "Team Name" in student_data.columns:
                        st.write(f"**Team:** {student_data['Team Name'].iloc[0] if not pd.isna(student_data['Team Name'].iloc[0]) else 'N/A'}")
                    if "Home County" in student_data.columns:
                        st.write(f"**Home County:** {student_data['Home County'].iloc[0] if not pd.isna(student_data['Home County'].iloc[0]) else 'N/A'}")
                
                with col2:
                    st.markdown("#### 🎯 Performance Metrics")
                    if "Mean Grade" in student_data.columns:
                        st.write(f"**Mean Grade:** {student_data['Mean Grade'].iloc[0] if not pd.isna(student_data['Mean Grade'].iloc[0]) else 'N/A'}")
                    if "M%" in student_data.columns:
                        st.write(f"**Overall Percentage:** {student_data['M%'].iloc[0] if not pd.isna(student_data['M%'].iloc[0]) else 'N/A'}%")
                    if "Remark" in student_data.columns:
                        st.write(f"**Remark:** {student_data['Remark'].iloc[0] if not pd.isna(student_data['Remark'].iloc[0]) else 'N/A'}")
                
                # Subject scores visualization
                st.markdown("#### 📚 Subject Performance")
                
                # Get subject scores for the student
                subject_scores = []
                subject_names = []
                for subject in subject_columns:
                    if subject in student_data.columns:
                        score = student_data[subject].iloc[0]
                        if pd.notna(score) and str(score).strip() not in ["Not Appeared", ""]:
                            try:
                                numeric_score = float(score)
                                subject_scores.append(numeric_score)
                                subject_names.append(subject)
                            except:
                                pass
                
                if subject_scores and subject_names:
                    # Bar chart of subject scores
                    fig_subjects = px.bar(
                        x=subject_names,
                        y=subject_scores,
                        title=f"Subject Scores for {selected_student}",
                        labels={"x": "Subject", "y": "Score"},
                        color=subject_scores,
                        color_continuous_scale="viridis"
                    )
                    
                    fig_subjects.update_traces(hovertemplate='<b>%{x}</b><br>Subject Score: %{y}<extra></extra>')
                    fig_subjects.add_hline(y=60, line_dash="dash", line_color="red", 
                                         annotation_text="Pass Mark (60%)")
                    st.plotly_chart(fig_subjects, use_container_width=True)
                    
                    # Performance analysis
                    avg_score = np.mean(subject_scores)
                    subjects_below_60 = [name for name, score in zip(subject_names, subject_scores) if score < 60]
                    subjects_above_80 = [name for name, score in zip(subject_names, subject_scores) if score >= 80]
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Average Score", f"{avg_score:.1f}%")
                    with col2:
                        st.metric("Subjects Below 60%", len(subjects_below_60))
                    with col3:
                        st.metric("Subjects Above 80%", len(subjects_above_80))
                    
                    if subjects_below_60:
                        st.warning(f"**Subjects needing improvement:** {', '.join(subjects_below_60)}")
                    
                    if subjects_above_80:
                        st.success(f"**Strong subjects:** {', '.join(subjects_above_80)}")
                
                # Show subjects with "Not Appeared" status
                not_appeared_subjects = []
                for subject in subject_columns:
                    if subject in student_data.columns:
                        score = student_data[subject].iloc[0]
                        if pd.notna(score) and str(score).strip() == "Not Appeared":
                            not_appeared_subjects.append(subject)
                
                if not_appeared_subjects:
                    st.info(f"**Subjects not appeared:** {', '.join(not_appeared_subjects)}")
                    
                # Show subjects with no data
                no_data_subjects = []
                for subject in subject_columns:
                    if subject in student_data.columns:
                        score = student_data[subject].iloc[0]
                        if pd.isna(score) or str(score).strip() == "":
                            no_data_subjects.append(subject)
                    else:
                        no_data_subjects.append(subject)
                
                if no_data_subjects:
                    st.warning(f"**Subjects with no data:** {', '.join(no_data_subjects)}")
                
                # Student progress over time (if multiple periods available)
                st.markdown("#### 📈 Progress Over Time")
                student_all_periods = df_main[df_main["Student"] == selected_student]
                
                if "Period" in student_all_periods.columns:
                    unique_periods = student_all_periods["Period"].dropna().unique()
                    
                    # Convert periods to numeric for proper sorting (e.g., "2.1" -> 2.1)
                    def period_to_float(period_str):
                        try:
                            return float(str(period_str).strip())
                        except:
                            return 0.0
                    
                    # Sort periods numerically
                    sorted_periods = sorted(unique_periods, key=period_to_float)
                    
                    if len(unique_periods) > 1:
                        # Create progress data for different metrics
                        progress_data = []
                        
                        for period in sorted_periods:
                            period_data = student_all_periods[student_all_periods["Period"] == period]
                            if not period_data.empty:
                                # Get the most recent record for this period (in case of duplicates)
                                latest_record = period_data.iloc[-1]
                                
                                row_data = {"Period": str(period)}
                                
                                # Add M% if available and valid
                                if "M%" in period_data.columns and pd.notna(latest_record["M%"]):
                                    try:
                                        m_percent = float(latest_record["M%"])
                                        if m_percent > 0 and m_percent <= 100:  # Valid percentage range
                                            row_data["Overall %"] = m_percent
                                    except:
                                        pass
                                
                                # Add individual subject scores
                                for subject in ["Maths", "English", "Chemistry", "Biology", "Physics"]:
                                    if subject in period_data.columns and pd.notna(latest_record[subject]):
                                        try:
                                            score_val = str(latest_record[subject]).strip()
                                            if score_val != "Not Appeared" and score_val != "":
                                                score = float(score_val)
                                                if score > 0 and score <= 100:  # Valid score range
                                                    row_data[subject] = score
                                        except:
                                            pass
                                
                                # Only add if we have at least one valid metric
                                if len(row_data) > 1:
                                    progress_data.append(row_data)
                        
                        if len(progress_data) > 1:
                            progress_df = pd.DataFrame(progress_data)
                            
                            # Plot overall percentage trend if available
                            if "Overall %" in progress_df.columns and progress_df["Overall %"].notna().sum() > 1:
                                # Filter out any NaN values
                                overall_df = progress_df.dropna(subset=["Overall %"])
                                if len(overall_df) > 1:
                                    fig_overall = px.line(
                                        overall_df,
                                        x="Period",
                                        y="Overall %",
                                        title=f"Overall Performance Trend for {selected_student}",
                                        markers=True,
                                        line_shape="linear"
                                    )
                                    fig_overall.update_layout(
                                        xaxis_title="Period",
                                        yaxis_title="Overall Percentage (%)",
                                        showlegend=True
                                    )
                                    st.plotly_chart(fig_overall, use_container_width=True)
                                    
                                    # Show progress summary with valid data
                                    first_score = overall_df["Overall %"].iloc[0]
                                    last_score = overall_df["Overall %"].iloc[-1]
                                    change = last_score - first_score
                                    
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("First Period", f"{first_score:.1f}%")
                                    with col2:
                                        st.metric("Latest Period", f"{last_score:.1f}%")
                                    with col3:
                                        st.metric("Change", f"{change:+.1f}%", delta=f"{change:+.1f}%")
                                else:
                                    st.info("Overall percentage data available but insufficient valid data points for trend.")
                            else:
                                st.info("Overall percentage data not available or insufficient for trend analysis.")
                            
                            # Plot subject-wise trends if available
                            subject_cols = [col for col in progress_df.columns if col not in ["Period", "Overall %"]]
                            if subject_cols:
                                # Create a melted dataframe, but handle NaN values properly
                                melted_data = []
                                for _, row in progress_df.iterrows():
                                    for subject in subject_cols:
                                        if pd.notna(row[subject]):
                                            melted_data.append({
                                                "Period": row["Period"],
                                                "Subject": subject,
                                                "Score": row[subject]
                                            })
                                
                                if melted_data:
                                    melted_df = pd.DataFrame(melted_data)
                                    
                                    # Only plot subjects that have at least 2 data points
                                    subject_counts = melted_df.groupby("Subject").size()
                                    valid_subjects = subject_counts[subject_counts >= 2].index.tolist()
                                    
                                    if valid_subjects:
                                        filtered_melted = melted_df[melted_df["Subject"].isin(valid_subjects)]
                                        
                                        fig_subjects = px.line(
                                            filtered_melted,
                                            x="Period",
                                            y="Score",
                                            color="Subject",
                                            title=f"Subject-wise Performance Trend for {selected_student}",
                                            markers=True
                                        )
                                        fig_subjects.update_layout(
                                            xaxis_title="Period",
                                            yaxis_title="Score (%)",
                                            showlegend=True
                                        )
                                        st.plotly_chart(fig_subjects, use_container_width=True)
                                    else:
                                        st.info("Insufficient subject data points for trend analysis.")
                                else:
                                    st.info("No valid subject scores found for trend analysis.")
                        else:
                            st.info("Not enough valid data points to show progress trend.")
                    else:
                        st.info("Only one period of data available for this student.")
                else:
                    st.info("Period information not available in the data.")
                
                # Detailed data table for the student
                st.markdown("#### 📋 Detailed Records")
                
                # Clean up unwanted columns for student data display
                columns_to_remove = [
                    'Unnamed: 0_x', 'Unnamed: 18', 'Unnamed: 20', 'Woodwork', 'M %', 'MM/MP', 
                    'Guardian', 'Contact', 'Unnamed: 6', 'Unnamed: 0_y', 'Unnamed: 9', 
                    'Unnamed: 10', 'Unnamed: 11'
                ]
                
                # Create a display dataframe without unwanted columns
                student_display_df = student_data.copy()
                
                # Remove unwanted columns if they exist
                existing_unwanted_cols = [col for col in columns_to_remove if col in student_display_df.columns]
                if existing_unwanted_cols:
                    student_display_df = student_display_df.drop(columns=existing_unwanted_cols)
                
                # Remove the first column if it looks like an unnamed index
                if len(student_display_df.columns) > 0:
                    first_col = student_display_df.columns[0]
                    if 'Unnamed' in str(first_col) or first_col == 0:
                        student_display_df = student_display_df.drop(columns=[first_col])
                
                # Handle duplicate column names more robustly
                seen_columns = set()
                columns_to_keep = []
                columns_to_drop = []
                
                for col in student_display_df.columns:
                    col_lower = str(col).lower().strip()
                    # Check for Business Studies variations
                    if 'business' in col_lower and 'studies' in col_lower:
                        if 'business_studies' not in seen_columns:
                            seen_columns.add('business_studies')
                            columns_to_keep.append(col)
                        else:
                            columns_to_drop.append(col)
                    else:
                        if col_lower not in seen_columns:
                            seen_columns.add(col_lower)
                            columns_to_keep.append(col)
                        else:
                            columns_to_drop.append(col)
                
                # Drop duplicate columns
                if columns_to_drop:
                    student_display_df = student_display_df.drop(columns=columns_to_drop)
                
                st.dataframe(student_display_df, use_container_width=True)
            
            else:
                st.error("No data found for the selected student.")
    else:
        st.error("Student data not available.")


with tab3:
    st.markdown("### 📋 Detailed Student Data")
    
    # Note about filtering
    if team or period or school or grade or form or donor or county or marks_range != (0, 100):
        st.info("📊 Data shown below reflects the current filter settings from the Overall Analysis tab.")
    
    # Clean up unwanted columns for display
    columns_to_remove = [
        'Unnamed: 0_x', 'Unnamed: 18', 'Unnamed: 20', 'Woodwork', 'M %', 'MM/MP', 
        'Guardian', 'Contact', 'Unnamed: 6', 'Unnamed: 0_y', 'Unnamed: 9', 
        'Unnamed: 10', 'Unnamed: 11'
    ]
    
    # Create a display dataframe without unwanted columns
    display_df = filtered.copy()
    
    # Remove unwanted columns if they exist
    existing_unwanted_cols = [col for col in columns_to_remove if col in display_df.columns]
    if existing_unwanted_cols:
        display_df = display_df.drop(columns=existing_unwanted_cols)
    
    # Remove the first column if it looks like an unnamed index
    if len(display_df.columns) > 0:
        first_col = display_df.columns[0]
        if 'Unnamed' in str(first_col) or first_col == 0:
            display_df = display_df.drop(columns=[first_col])
    
    # Handle duplicate column names more robustly
    seen_columns = set()
    columns_to_keep = []
    columns_to_drop = []
    
    for col in display_df.columns:
        col_lower = str(col).lower().strip()
        # Check for Business Studies variations
        if 'business' in col_lower and 'studies' in col_lower:
            if 'business_studies' not in seen_columns:
                seen_columns.add('business_studies')
                columns_to_keep.append(col)
            else:
                columns_to_drop.append(col)
        else:
            if col_lower not in seen_columns:
                seen_columns.add(col_lower)
                columns_to_keep.append(col)
            else:
                columns_to_drop.append(col)
    
    # Drop duplicate columns
    if columns_to_drop:
        display_df = display_df.drop(columns=columns_to_drop)
    
    # Show summary statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Records", len(display_df))
    with col2:
        if "M%" in display_df.columns:
            avg_performance = display_df["M%"].mean()
            st.metric("Average Performance", f"{avg_performance:.1f}%")
    with col3:
        if "School" in display_df.columns:
            unique_schools = display_df["School"].nunique()
            st.metric("Schools Represented", unique_schools)
    
    st.markdown("---")
    
    # Add search functionality
    search_term = st.text_input("🔍 Search in data (student name, school, etc.)", "")
    if search_term:
        # Search across text columns
        text_columns = display_df.select_dtypes(include=['object']).columns
        mask = False
        for col in text_columns:
            mask |= display_df[col].astype(str).str.contains(search_term, case=False, na=False)
        display_df = display_df[mask]
        st.info(f"Found {len(display_df)} records matching '{search_term}'")
    
    # Display the data
    st.dataframe(display_df, use_container_width=True, height=600)
    
    # Download option
    if st.button("📥 Download Filtered Data as CSV"):
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"student_data_filtered_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

