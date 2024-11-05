import streamlit as st
import pandas as pd
import psycopg2
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

# ---------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------
st.set_page_config(
    page_title="AD Clinical Trial Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
)
# ---------------------------------
# 2. DATABASE CONNECTION
# ---------------------------------
# Define the connection parameters
conn = psycopg2.connect(
    host="aact-db.ctti-clinicaltrials.org",
    port="5432",
    user="k07aa5",
    password="k07aa5",
    database="aact"
)
# ---------------------------------
# 3. AUTO REFRESH SETUP
# ---------------------------------
# Automatically refresh the page every 10 seconds
# st_autorefresh(interval=100 * 1000)  # interval in milliseconds


# ---------------------------------
# 4. DATA FETCHING FROM DATABASE
# ---------------------------------
# Query for Alzheimer's disease and MCI studies from AACT
query = """
SELECT s.nct_id, s.brief_title, s.start_date, s.completion_date, s.overall_status, 
       s.phase, s.enrollment, i.intervention_type, c.name AS condition, 
       s.primary_completion_date, sp.name AS study_sponsor
FROM studies s
JOIN conditions c ON s.nct_id = c.nct_id
LEFT JOIN interventions i ON s.nct_id = i.nct_id
LEFT JOIN sponsors sp ON s.nct_id = sp.nct_id
WHERE LOWER(c.name) LIKE '%alzheimer%'OR LOWER(c.name) LIKE '%mild cognitive%'
"""

# Fetch the data and store it in DataFrame
alzheimers_data = pd.read_sql(query, conn)

# A button to refresh data manually (if needed)
if st.button('Refresh Data'):
    alzheimers_data = pd.read_sql(query, conn)



# ---------------------------------
# 5. DATA CLEANING AND PROCESSING
# ---------------------------------
# Convert date columns to datetime format
alzheimers_data['start_date'] = pd.to_datetime(alzheimers_data['start_date'], errors='coerce')
alzheimers_data['completion_date'] = pd.to_datetime(alzheimers_data['completion_date'], errors='coerce')
alzheimers_data['primary_completion_date'] = pd.to_datetime(alzheimers_data['primary_completion_date'], errors='coerce')

# Filter to include only drug trials and clean up missing data in phase and completion date
active_trials = alzheimers_data[alzheimers_data['overall_status'].isin(['ACTIVE', 'NOT_YET_RECRUITING', 'RECRUITING'])]
drug_trials = alzheimers_data[alzheimers_data['intervention_type'].isin(['DRUG'])]
clean_df = drug_trials.dropna(subset=['phase', 'primary_completion_date'])
clean_df = clean_df[clean_df['phase'] != 'NA']

# Add start and completion year columns
clean_df['start_year'] = clean_df['start_date'].dt.year
clean_df['completion_year'] = clean_df['completion_date'].dt.year
clean_df['start_year'] = clean_df['start_year'].astype('Int64')
clean_df['completion_year'] = clean_df['completion_year'].astype('Int64')

# ---------------------------------
# 6. DATA STANDARDIZATION FUNCTIONS
# --------------------------------- 
# Function to return "University" if any part contains the term
def map_to_alzheimers(study_sponsor):
    if pd.Series(study_sponsor).str.contains(r"(?i)\bUniversity\b", regex=True).any():
        return "Univsrsity"
    elif pd.Series(study_sponsor).str.contains(r"(?i)\bInstitute\b", regex=True).any():
        return "Univsrsity"
    else:
        return study_sponsor

# Apply the function to the 'Conditions' column
clean_df['standardized_sponsor'] = clean_df['study_sponsor'].apply(map_to_alzheimers)

# Function to return "Alzheimer's Disease" if any part contains the term
def map_to_alzheimers(condition):
    if pd.Series(condition).str.contains(r"(?i)\bAlzheimer['s]?\b", regex=True).any():
        return "Alzheimer's Disease"
    if pd.Series(condition).str.contains(r"(?i)\bMild\b", regex=True).any():
        return "Mild Cognitive Impairment"    
    else: 
        return condition
# Apply the function to the 'condition' column
clean_df['standardized_condition'] = clean_df['condition'].apply(map_to_alzheimers)

# ---------------------------------
# 7. DASHBOARD LAYOUT AND USER CONTROLS
# ---------------------------------
# Title of the dashboard
st.title(":bar_chart: Alzheimer's Disease Clinical Trial Live Dashboard")
st.markdown('## Insight into Alzheimer’s Disease Trials')

# Streamlit slider for selecting the year range for completed trials
st.subheader("Select Year Range for Trials")
start_year, end_year = st.slider(
    "Select the range of years",
    min_value=int(clean_df['start_year'].min()),
    max_value=int(clean_df['completion_year'].max()),
    value=(2010, 2030)
)
# Streamlit multiselect for phase selection
phases = clean_df['phase'].unique()
selected_phases = st.multiselect("Select Trial Phases", options=phases, default=phases)

# Filter the data based on the selected year range and selected phases
df_complete = clean_df[
    (clean_df['start_year'] >= start_year) &
    (clean_df['completion_year'] <= end_year) &
    (clean_df['phase'].isin(selected_phases))
]

# ---------------------------------
# 8. VISUALIZATIONS
# ---------------------------------
# Trials over time
trials_over_time = clean_df[clean_df['phase'].isin(selected_phases)].groupby(clean_df['start_year']).size()
st.write("### New Alzheimer’s Trials Over Time")
st.line_chart(trials_over_time)


# Count the number of trials in the Selected Year Range
num_trials_complete = df_complete.shape[0]
st.subheader("Number of Trials the Selected Year Range")
st.metric(label="Trials (Selected Year Range)", value=num_trials_complete)

# Phase distribution
st.write("### Number of Trials by Phase")
phase_distribution = df_complete['phase'].value_counts()
st.bar_chart(phase_distribution)


# Plot 1: Pie Chart for Phases of trials in the Selected Year Range
st.subheader("Phases Distribution of Trials in the Selected Year Range")
phase_counts = df_complete['phase'].value_counts()
fig1, ax1 = plt.subplots()
ax1.pie(phase_counts, labels=phase_counts.index, autopct='%1.1f%%', startangle=40)
ax1.axis('equal')
st.pyplot(fig1)

# Plot 2: Bar Chart for Sponsor vs. Phases ( in the Selected Year Range)
st.subheader("Sponsor vs. Phases of Trials in the Selected Year Range")
sponsor_phase_counts = df_complete.groupby(['standardized_sponsor', 'phase']).size().reset_index(name='Counts')
fig2 = px.bar(sponsor_phase_counts, x='standardized_sponsor', y='Counts', color='phase', barmode='group',
               title="Number of Studies per Sponsor by Phases")
st.plotly_chart(fig2)

# Plot 3: Bar Chart for Conditions
st.subheader("Trials by Condition (in the Selected Year Range)")
condition_counts = df_complete.groupby('standardized_condition').size().reset_index(name='Counts')
fig3 = px.bar(condition_counts, x='standardized_condition', y='Counts',
               title="Number of Studies per Condition")
st.plotly_chart(fig3)

# Footer
st.write("### Data Source: [ClinicalTrials.gov](https://clinicaltrials.gov)")

# Close the connection
conn.close()

