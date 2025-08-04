import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
import numpy as np
import base64
import os
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import json

st.set_page_config(layout="wide", page_title="Student Performance Analysis Dashboard")

# ---- Google Drive Setup ----
@st.cache_resource
def initialize_drive_service():
    """Initialize Google Drive service using service account credentials"""
    try:
        # Get credentials from Streamlit secrets
        credentials_info = st.secrets["google_service_account"]
        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        service = build('drive', 'v3', credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Failed to initialize Google Drive service: {str(e)}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def download_file_from_drive(_service, file_id, file_name):
    """Download file from Google Drive and return as bytes"""
    try:
        request = _service.files().get_media(fileId=file_id)
        file_io = io.BytesIO()
        downloader = MediaIoBaseDownload(file_io, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        file_io.seek(0)
        return file_io.getvalue()
    except Exception as e:
        st.error(f"Error downloading {file_name}: {str(e)}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_excel_from_drive(_service, file_id, file_name):
    """Load Excel file from Google Drive into pandas DataFrame"""
    file_content = download_file_from_drive(_service, file_id, file_name)
    if file_content:
        return pd.read_excel(io.BytesIO(file_content), sheet_name=None, engine='openpyxl')
    return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_image_from_drive(_service, file_id, file_name):
    """Load image file from Google Drive and convert to base64"""
    file_content = download_file_from_drive(_service, file_id, file_name)
    if file_content:
        return base64.b64encode(file_content).decode()
    return None

# ---- Custom CSS ----
st.markdown("""
    <style>
    .metric-header {
        background-color: #87cefa;
        color: black;
        text-align: center;
        font-weight: bold;
        font-size: 0.9em;
        border-radius: 5px 5px 0 0;
        padding: 4px 0 4px 0;
        margin-bottom: 0px;
    }
    .metric-card {
        background: white;
        border-radius: 0 0 5px 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        padding: 6px 0 3px 0;
        margin-bottom: 8px;
        text-align: center;
    }
    .metric-value {
        font-size: 1.5em;
        font-weight: 600;
        color: #222;
    }
    .metric-label {
        font-size: 0.8em;
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

# ---- Load Data from Google Drive ----
def load_data():
    """Load all data from Google Drive"""
    service = initialize_drive_service()
    if not service:
        st.error("Cannot connect to Google Drive. Please check your service account configuration.")
        st.stop()
    
    try:
        # Get file IDs from secrets
        file_ids = st.secrets["google_drive_files"]
        
        # Load team result files
        files_and_teams = [
            (file_ids["team_kathy"], "Team Kathy"),
            (file_ids["team_kelly"], "Team Kelly"),
            (file_ids["team_lissette"], "Team Lissette"),
        ]
        
        dfs = []
        for file_id, team in files_and_teams:
            try:
                all_sheets = load_excel_from_drive(service, file_id, f"{team} Results")
                if all_sheets:
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
                else:
                    st.warning(f"Could not load data for {team}")
            except Exception as e:
                st.error(f"Error loading {team} data: {str(e)}")
        
        if not dfs:
            st.error("No team data could be loaded.")
            st.stop()
        
        df_main = pd.concat(dfs, ignore_index=True)
        
        # Load High School Data Sheet (only if file ID is provided and not placeholder)
        high_school_file_id = file_ids.get("high_school_data", "")
        if high_school_file_id and high_school_file_id != "REPLACE_WITH_ACTUAL_FILE_ID":
            high_school_data = load_excel_from_drive(service, high_school_file_id, "High School Data")
            if high_school_data:
                # Get the first sheet if multiple sheets exist
                high_school_df = list(high_school_data.values())[0]
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
            else:
                st.warning("Could not load High School Data Sheet")
        else:
            st.info("High School Data Sheet not configured - using team data only")
        
        return df_main
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.stop()

# Function to load logo from local file
def get_logo_base64():
    """Load logo from local file and convert to base64"""
    try:
        logo_path = "SAM Elimu Logo-white_edited.png"
        with open(logo_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        st.warning(f"Could not load logo from local file: {str(e)}")
        return None

# Load data and logo
with st.spinner("Loading data from Google Drive..."):
    df_main = load_data()

# Load logo from local file
logo_base64 = get_logo_base64()

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
if logo_base64:
    st.markdown(f"""
        <div class="main-header">
            <div style='background-color: #FFC300; padding: 8px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); position: relative; display: flex; align-items: center; justify-content: space-between;'>
                <h1 style='color: black; margin: 0; font-size: 1.6em; font-weight: bold; flex: 1; text-align: center;'>Student Performance Analysis Dashboard</h1>
                <img src="data:image/png;base64,{logo_base64}" style="height: 80px; width: auto; margin: 10px; padding-top: 20px" alt="SAM Elimu Logo">
            </div>
        </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
        <div class="main-header">
            <div style='background-color: #FFC300; padding: 8px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); position: relative;'>
                <h1 style='color: black; margin: 0; font-size: 1.6em; font-weight: bold;'>Student Performance Analysis Dashboard</h1>
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
        
        # Step 1: Team selection
        team = st.selectbox("Team Name", options=["All"] + sorted([str(x) for x in df_main["Team Name"].dropna().unique().tolist()]))
        
        # Filter data based on team selection for subsequent filters
        filtered_for_options = df_main.copy()
        if team and team != "All":
            filtered_for_options = filtered_for_options[filtered_for_options["Team Name"].astype(str) == team]
        
        # Step 2: Form selection (based on available forms for selected team)
        if "Form" in filtered_for_options.columns:
            available_forms = sorted([str(x) for x in filtered_for_options["Form"].dropna().unique().tolist()])
            form = st.multiselect("Form", options=available_forms)
            
            # Further filter for subsequent options
            if form:
                filtered_for_options = filtered_for_options[filtered_for_options["Form"].astype(str).isin(form)]
        else:
            form = []
        
        # Step 3: Period selection (based on available periods for selected team/form)
        available_periods = sorted([str(x) for x in filtered_for_options["Period"].dropna().unique().tolist()])
        period = st.multiselect("Period (type to search)", options=available_periods, max_selections=5, help="Start typing to quickly find a period.")
        
        # Further filter for subsequent options
        if period:
            filtered_for_options = filtered_for_options[filtered_for_options["Period"].astype(str).isin(period)]
        
        # Step 4: School selection (based on available schools for current selection)
        if "School" in filtered_for_options.columns:
            available_schools = sorted([str(x) for x in filtered_for_options["School"].dropna().unique().tolist()])
            school = st.multiselect("School", options=available_schools)
            
            if school:
                filtered_for_options = filtered_for_options[filtered_for_options["School"].astype(str).isin(school)]
        else:
            school = []
        
        # Step 5: Mean Grade selection (based on available grades for current selection)
        if "Mean Grade" in filtered_for_options.columns:
            available_grades = sorted([str(x) for x in filtered_for_options["Mean Grade"].dropna().unique().tolist()])
            grade = st.multiselect("Mean Grade", options=available_grades)
            
            if grade:
                filtered_for_options = filtered_for_options[filtered_for_options["Mean Grade"].astype(str).isin(grade)]
        else:
            grade = []
        
        # Step 6: Donor selection (based on available donors for current selection)
        if "Donor" in filtered_for_options.columns:
            available_donors = sorted([str(x) for x in filtered_for_options["Donor"].dropna().unique().tolist()])
            donor = st.multiselect("Donor", options=available_donors)
            
            if donor:
                filtered_for_options = filtered_for_options[filtered_for_options["Donor"].astype(str).isin(donor)]
        else:
            donor = []
        
        # Step 7: Home County selection (based on available counties for current selection)
        if "Home County" in filtered_for_options.columns:
            available_counties = sorted([str(x) for x in filtered_for_options["Home County"].dropna().unique().tolist()])
            county = st.multiselect("Home County", options=available_counties)
        else:
            county = []
        
        # Step 8: Marks range slider
        marks_range = st.slider("% Marks", 0, 100, (0, 100))

    # ---- Apply Filters ----
    filtered = df_main.copy()
    
    if team and team != "All":
        filtered = filtered[filtered["Team Name"].astype(str) == team]
    
    if form:
        filtered = filtered[filtered["Form"].astype(str).isin(form)]
    
    if period:
        filtered = filtered[filtered["Period"].astype(str).isin(period)]
    
    if school:
        filtered = filtered[filtered["School"].astype(str).isin(school)]
    if grade:
        filtered = filtered[filtered["Mean Grade"].astype(str).isin(grade)]
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
        
        # First row: Number of Students, Sciences, Languages
        main_cols_row1 = st.columns(3)

        with main_cols_row1[0]:
            st.markdown('<div class="metric-header">Number of Students</div>', unsafe_allow_html=True)
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Total</div>
                    <div class="metric-value">{filtered.shape[0]}</div>
                </div>
            """, unsafe_allow_html=True)

        with main_cols_row1[1]:
            st.markdown('<div class="metric-header">Average Score in Sciences</div>', unsafe_allow_html=True)
            # Sciences: Mathematics, Biology, Chemistry, Physics
            science_subjects = ["Maths", "Biology", "Chemistry", "Physics"]
            science_metrics = []
            for subject in science_subjects:
                if subject in filtered.columns:
                    science_metrics.append((subject, filtered[subject].mean()))
            
            if science_metrics:
                sci_cols = st.columns(len(science_metrics))
                for i, (label, value) in enumerate(science_metrics):
                    display_value = f"{value:.0f}" if pd.notnull(value) else "--"
                    with sci_cols[i]:
                        st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-label">{label}</div>
                                <div class="metric-value">{display_value}</div>
                            </div>
                        """, unsafe_allow_html=True)

        with main_cols_row1[2]:
            st.markdown('<div class="metric-header">Average Score in Languages</div>', unsafe_allow_html=True)
            # Languages: English, Kiswahili, French
            language_subjects = ["English", "Kiswahili", "French"]
            language_metrics = []
            for subject in language_subjects:
                if subject in filtered.columns:
                    language_metrics.append((subject, filtered[subject].mean()))
            
            if language_metrics:
                lang_cols = st.columns(len(language_metrics))
                for i, (label, value) in enumerate(language_metrics):
                    display_value = f"{value:.0f}" if pd.notnull(value) else "--"
                    with lang_cols[i]:
                        st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-label">{label}</div>
                                <div class="metric-value">{display_value}</div>
                            </div>
                        """, unsafe_allow_html=True)

        # Second row: Humanities and Technical Subjects
        main_cols_row2 = st.columns([1, 2])  # Humanities gets 1/3, Technical gets 2/3

        with main_cols_row2[0]:
            st.markdown('<div class="metric-header">Average Score in Humanities</div>', unsafe_allow_html=True)
            # Humanities: History, Geography, CRE
            humanities_subjects = ["History", "Geography", "CRE"]
            humanities_metrics = []
            for subject in humanities_subjects:
                if subject in filtered.columns:
                    humanities_metrics.append((subject, filtered[subject].mean()))
            
            if humanities_metrics:
                # Display humanities in a single horizontal line
                hum_cols = st.columns(len(humanities_metrics))
                for i, (label, value) in enumerate(humanities_metrics):
                    display_value = f"{value:.0f}" if pd.notnull(value) else "--"
                    with hum_cols[i]:
                        st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-label">{label}</div>
                                <div class="metric-value">{display_value}</div>
                            </div>
                        """, unsafe_allow_html=True)

        with main_cols_row2[1]:
            st.markdown('<div class="metric-header">Average Score in Technical Subjects</div>', unsafe_allow_html=True)
            # Technical Subjects: Computer Studies, Business Studies, Woodwork, Home Science, Agriculture
            technical_subjects = ["Computer studies", "Business Studies", "Woodwork", "Home Science", "Agriculture"]
            technical_metrics = []
            for subject in technical_subjects:
                if subject in filtered.columns:
                    technical_metrics.append((subject, filtered[subject].mean()))
            
            if technical_metrics:
                # Display all technical subjects in a single horizontal line
                tech_cols = st.columns(len(technical_metrics))
                for i, (label, value) in enumerate(technical_metrics):
                    display_value = f"{value:.0f}" if pd.notnull(value) else "--"
                    with tech_cols[i]:
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

with tab2:
    st.markdown("### 👨‍🎓 Individual Student Analysis")
    
    # Student selector
    if "Student" in df_main.columns:
        # Filter out non-student entries like "Category Distribution" and other system entries
        student_list = []
        for student in df_main["Student"].dropna().unique():
            student_str = str(student).strip()
            # Skip entries that look like headers, categories, or system entries
            if (student_str and 
                student_str not in ["Category Distribution", "CATEGORY DISTRIBUTION", "category distribution"] and
                not student_str.lower().startswith("category") and
                not student_str.lower().startswith("total") and
                not student_str.lower().startswith("average") and
                len(student_str) > 2):  # Ensure it's a meaningful name
                student_list.append(student_str)
        
        student_list = sorted(student_list)
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
                                
                                # Add individual subject scores for all available subjects
                                for subject in subject_columns:
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
                                        xaxis=dict(type='category'),  # Treat x-axis as categorical to show actual period values
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
                                            xaxis=dict(type='category'),  # Treat x-axis as categorical to show actual period values
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
    if (team and team != "All") or form or period or school or grade or donor or county or marks_range != (0, 100):
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
