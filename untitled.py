import streamlit as st
import pandas as pd
import os
from langchain.llms import OpenAI  # Replace with your preferred LLM provider
from langchain.prompts import Chain, Q, A

# Replace with your access credentials for the chosen LLM provider
llm = OpenAI(temperature=0.7, api_key=os.environ.get("OPENAI_API_KEY"))  # Adjust temperature as needed

# Replace "path/to/your/file.xlsx" with the actual path to your Excel file
data = pd.read_excel("path/to/your/file.xlsx")

# Access all columns as a DataFrame
all_data = data.copy()  # Avoid modifying the original data

# Define a function to summarize major events from notes
def summarize_major_events(notes):
    chain = Chain.from_prompts([
        Q("What are the major events described in this patient note?"),
        A("{notes}"),  # Inject retrieved notes into the second prompt
    ])

    # Call the LLM chain for the loaded notes
    summary = llm.run(chain, notes=notes)["text"]
    return summary

# Streamlit app logic
st.title("Patient Events Summary Generator")

# Input fields for the patient to select the type of clinician, the duration, and a button to generate the summary
clinician_type = st.selectbox("Select Clinician Type", ["all", "doctor", "nurse", "therapist"])
duration = st.selectbox("Select Duration", ["Last 2 weeks", "Last month", "Last 3 months"])

duration_days_map = {
    "Last 2 weeks": 14,
    "Last month": 30,
    "Last 3 months": 90
}

if st.button("Generate Summary"):
    duration_days = duration_days_map[duration]
    end_date = pd.Timestamp.now().normalize()
    start_date = end_date - pd.Timedelta(days=duration_days)
    
    # Filter events based on clinician type and duration
    filtered_data = all_data[
        (all_data["Clinician"].str.lower() == clinician_type.lower()) | (clinician_type == "all")
    ]
    filtered_data = filtered_data[
        (pd.to_datetime(filtered_data["Date"]) >= start_date) &
        (pd.to_datetime(filtered_data["Date"]) <= end_date)
    ]

    major_events_per_consultation = []
    for index, row in filtered_data.iterrows():
        consultation_notes = row["Notes Entry"]  # Assuming "Notes Entry" is your notes column
        summary = summarize_major_events(consultation_notes)
        major_events_per_consultation.append({"date": row["Date"], "summary": summary})

    # Display extracted major events
    st.header("Major Events Summary (Per Consultation)")
    for i, consultation in enumerate(major_events_per_consultation):
        st.write(f"Consultation {i+1} ({consultation['date']}):")
        for event in consultation["summary"].splitlines():
            st.write(f"\t- {event}")

