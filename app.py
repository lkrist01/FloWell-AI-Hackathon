import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu
from streamlit_timeline import st_timeline
import datetime
import time
from fpdf import FPDF
import json
from dotenv import load_dotenv
import google.generativeai as genai 
import vertexai
from vertexai.generative_models import (
    GenerationConfig,
    GenerativeModel,
    HarmBlockThreshold,
    HarmCategory,
    Part,
)
import vertexai.preview.generative_models as generative_models

import os
from docx import Document
from io import BytesIO, StringIO
# http://34.42.44.59:8081/

# Load environment variables from .env file
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

# Configure the Google Generative AI with the API key
genai.configure(api_key=api_key)

def get_all_notes_text(df, nhs_id):
    #note = ''
    r = df[df["NHS Number"] == 2233445671]
    r1 = ", ".join(r["Notes Entry"].astype(str))
    return r1

def create_word_doc(text):
    doc = Document()
    doc.add_heading('Document Title', 0)
    doc.add_paragraph(text)
    
    byte_io = BytesIO()
    doc.save(byte_io)
    byte_io.seek(0)
    return byte_io

# Function to update the value in session state
def clicked(button):
    st.session_state.clicked[button] = True


def download_text(text, filename="text_file.txt"):
    """Downloads the given text as a text file."""
    try:
        os.makedirs("discharges", exist_ok=True)
        filepath = os.path.join("discharges", filename)
        with open(filepath, "w", encoding="utf-8") as file:
            file.write(text)
        st.success(f"File '{filename}' downloaded successfully!")
        st.download_button(
            label="Download Text File",
            data=open(filepath, "rb").read(),
            file_name=filename,
            mime="text/plain"
        )
    except Exception as e:
        st.error(f"Error downloading file: {e}")


def create_text_file(text):
    # Create an in-memory text stream
    text_io = BytesIO()
    
    # Write the text to the stream
    text_io.write(text)
    
    # Move the cursor to the beginning of the stream
    text_io.seek(0)
    
    return text_io

@st.cache_resource
def load_model():
    """
    Load the generative models for text and multimodal generation.

    Returns:
        Tuple: A tuple containing the text model and multimodal model.
    """
    text_model_pro = genai.GenerativeModel("gemini-1.5-pro-latest")
    return text_model_pro

def get_gemini_pro_text_response(
    model: genai.GenerativeModel,
    contents: str,
    generation_config: GenerationConfig,
    stream: bool = True,
):
    safety_settings = {
        # generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    #     generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    #     generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    #     generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }

    responses = model.generate_content(
        prompt,
        generation_config=generation_config,
        safety_settings=safety_settings,
        stream=stream,
    )

    final_response = []
    for response in responses:
        try:
            # st.write(response.text)
            final_response.append(response.text)
        except IndexError:
            # st.write(response)
            final_response.append("")
            continue
    return " ".join(final_response)



def generate_pdf(text):
    """Generate an example pdf file and save it to example.pdf"""
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=text, ln=1, align="C") 
    pdf.output("example.pdf")


st.set_page_config(
    page_title="FloWell App",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "# This is a header. This is an *extremely* cool app!"
    }
)

with st.sidebar:
    selected = option_menu("Main Menu", ["Home", 'Admissions', "Clinical Notes"], 
        icons=['house', 'hospital', "clipboard"], menu_icon="cast", default_index=2)


if selected == "Home":
    """
    # Flowell

    Welcome to Flowell! An application designed to enhance integrated care and discharge processes by summarising information from patient electronic health records into an accurate timeline of events, creating a more productive pipeline that flows well!
    """

elif selected == "Admissions": 
    pass
else:
    
    
    df_patients = pd.read_csv("data/patients.csv")
    ids = df_patients["NHS Number"].unique()
    text_model_pro = load_model()
    
    #Patient selector
    id_option = st.selectbox("Select the patient nhsID:",(ids))
    st.write("You selected:", id_option)

    # patient info
    with st.expander("See patient details:"):
        st.dataframe(df_patients[df_patients["NHS Number"] == id_option].T) 
            
    # Read notes dataframe
    df_notes = pd.read_csv("data/updated_patient_notes.csv")
    patient_note = get_all_notes_text(df_notes, int(id_option))
    specialities = df_notes["Clinician Type"].unique()
    
    #*************** Checklist for problems, put the firts prompt here*********************
    st.subheader("Patient problem list:")
    
    problems = {
        'Problem': [
            'Hypertension',
            'Type 2 Diabetes',
            'Hyperlipidemia',
            'Osteoarthritis (left knee)',
            'Depression',
            'GERD'
        ],
        'Information': [
            'Controlled with medication, last blood pressure reading 125/80 mmHg',
            'Well-controlled with diet and medication, HbA1c 7.2%',
            'Total cholesterol 220 mg/dL, LDL 130 mg/dL',
            'Pain exacerbated by activity, managed with over-the-counter pain relievers',
            'Currently receiving therapy, patient reports improved mood',
            'Occasional heartburn, relieved with antacids'
        ]
    }

    df_problems = pd.DataFrame(problems)
    edited_df = st.data_editor(df_problems)
    
    st.header("Vertex AI Gemini API", divider="rainbow")
    tab1, tab2, tab3 = st.tabs(
    ["Generate Note Summary", "Patient Timeline", "Discharge"]
    )
    
    #*************** Summarize LLM, put the firts prompt here*********************    
    with tab1:
        st.subheader("LMM Summary:")
        
        length_of_summary = st.radio(
        "Select the length of the summary: \n\n",
        ["Short", "Medium", "Long"],
        key="length_of_summary",
        horizontal=True,
        )
        
        type_of_text = st.radio(
        "Select the type of the summary: \n\n",
        ["Bulletpoint", "Paragraph"],
        key="type_of_text",
        horizontal=True,
        )
        
        prompt = f""" Generate a current, up to date summary of the patient's journey. The length of the summary should be {length_of_summary}. The response should be returned as {type_of_text}.

Patient Input Notes: {patient_note} \n

Output Example:\n
Mrs. Johnson, a 62-year-old female with a history of poorly controlled type 2 diabetes, hypertension, and hyperlipidemia, was admitted to the hospital for hyperglycemia, dehydration, and possible skin infection. She presented with excessive thirst, frequent urination, blurred vision, fatigue, and increased appetite. Upon admission, she received intravenous fluids and regular insulin drip, and her blood glucose levels gradually decreased. Her skin lesions were treated with topical antibiotics and showed signs of improvement. After a successful course of treatment, she was discharged home with instructions for self-monitoring blood glucose levels, medication regimen, and follow-up appointments.

        """

        config = {
            "temperature": 0.9,
            "max_output_tokens": 2048,
        }

        generate_t2t = st.button("Generate summary", key="generate_t2t")

        if generate_t2t and prompt:
            # st.write(prompt)
            with st.spinner("Generating your story using Gemini ..."):
                first_tab1, first_tab2 = st.tabs(["Generate summary", "Prompt"])
                with first_tab1:
                    
                    response = get_gemini_pro_text_response(
                        text_model_pro,
                        prompt,
                        generation_config=config,
                    )
                    if response:
                        st.write("Your summary:")
                        with st.chat_message("user"):
                            container = st.container(border=True)
                            st.write(response)
                with first_tab2:
                    st.text(prompt)

    with tab2:
    #*************** Timeline, put the firts prompt here*********************   
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            start = st.date_input("Select start date", datetime.date(2019, 7, 6))
            st.write("Start is:", start)

        with col2:
            end= st.date_input("Select end date", datetime.date(2019, 7, 6))
            st.write("End is:", end)

        with col3:
            timeline = st.selectbox("Which stage you want to filter?",
                                    ("Admission", "Patient Care", "Discharge"))
            st.write("Selected timeline:", timeline)

        with col4:
            options = st.multiselect("Specialist filter",
                             specialities,
                             ["Nurse", "Doctor"])
        
        # Timeline
#         prompt = f"""
#         Give me a list of key events in max 3 words from the patients notes below. These will be put onto the timeline in our app. Make sure to have a start and end which represents the day of the event are in datetime. The start and end should be the same day. Give me the results in json format. So that I can easily convert it to dictionary in python. The field name for the key events should be called content. Convert json index to id field. This is an example: "id": 1, "content": "Admission", "start": "2022-10-09:19:00:00", "end":"2022-10-09:20:00:00 \n

#         Patient notes input: {patient_note}\n
#         """

        prompt = f"""
        Give me a list of key events in max 3 words from the patients notes below. These will be put onto the timeline in our app. Make sure to have a start and end which represents the day of the event are in datetime. The start and end should be the same day. Give me the results in json format. So that I can easily convert it to dictionary in python. The field name for the key events should be called content. Convert json index to id field. This is an example how the type of response might look: "id": 1, "content": "Admission", "start": "2022-10-09T:19:00:00", "end":"2022-10-09T:20:00:00 \n

Instructions for the content:\n 
Dont put patient names, just procedures\n
Dont put confidential data\n
Give me the 6 most important events\n
End Date be between 1 day to 2 days length\n

Patient notes input that you need to extract the data from: {patient_note}
        """

        config = {
            "temperature": 0.9,
            "max_output_tokens": 2048,
        }

        generate_timeline = st.button("Generate the timeline", key="generate_timeline")
        
        if generate_timeline and prompt:
            # st.write(prompt)
            with st.spinner("Generating your story using Gemini ..."):
                first_tab1, first_tab2 = st.tabs(["Timeline", "Prompt"])
                with first_tab1:
                    response = get_gemini_pro_text_response(
                        text_model_pro,
                        prompt,
                        generation_config=config,
                    )
                    if response:
                        
                        st.write("Timeline:")
                        # st.write(response)
                        # import pdb; pdb.set_trace()
                        temp = ''.join(response).replace('```', '').replace('\n', '').replace(' ', '').replace("'",'"').replace("json","")
                        items = json.loads(temp)
                        
                        with st.expander("see raw response"):
                            st.write(items)
                        
                        st.subheader("Patient event timeline:")
                        events = st_timeline(items, groups=[], options={}, height="300px")
                        st.subheader("Selected note:")
                        st.write(events)

                        with st.chat_message("user"):
                            container = st.container(border=True)
                            st.write(f"You wrote {len(response)} characters.")
                with first_tab2:
                    st.text(prompt)

        # items = [
        #     {"id": 1, "content": "Admission", "start": "2022-10-09"},
        # ]
        
    with tab3:
        #********************Discharge***********************************
        st.subheader("Discharge section:")
        st.write("LLM is generating tasks, be patient...")

        discharge_tasks = {
            'Task': 
            [   
                "TTA (Medications on discharge)",
                "Discharge Summary",
                "Package of Care restarted",
                "Essential equipment delivered",
                "Follow-up clinic appointments booked",
                "Outpatient physiotherapy",
                "District Nurse Referral",
            ],
            'Department': [
                "Pharmacy",
                "Medical Records",
                "Social Work",
                "Physiotherapy",
                "Secretaries",
                "Physiotherapy",
                "Nursing",
            ],
            "Completed":[
                True,
                True,
                True,
                False,
                True,
                False,
                True,
            ]
        }

        df_discharge = pd.DataFrame(discharge_tasks)
        discharge_edited = st.data_editor(df_discharge)

        if discharge_edited['Completed'].all() == True:

            if st.button("Discharge", type="primary"):
                st.success("Patient Discharge!")
                
            st.header("Print patient procedure")
            if st.button("Generate Text"):
             
                txt ="""
                    You were admitted to the hospital with severe chest pain radiating to your left arm. This indicated a possible heart attack (myocardial infarction).

Upon arrival, an EKG was performed, which showed signs of a heart attack. Blood tests confirmed this diagnosis. A cardiologist recommended an urgent procedure called a coronary angioplasty with stent placement to open up a blocked artery.

The procedure was successful in opening the blocked artery in your left anterior descending artery (LAD) and placing a stent. You recovered well from the procedure, and your pain was managed with medication.

During your stay, you received physical therapy, occupational therapy, and education from a dietician to help you recover and regain your strength. You also had an echocardiogram, which showed good left ventricular function with minimal wall motion abnormality.

You were discharged home on May 27th with medication and a follow-up appointment scheduled. You were also given instructions for a home exercise program and advice on lifestyle changes to maintain good heart health. Please be sure to contact your doctor if you experience any chest pain, shortness of breath, dizziness, or swelling in your legs.
                    """

                st.write(txt)
                st.button("Download Text", on_click=lambda: download_text(txt, filename="patient_1.txt"))
                st.success("The text file has been created successfully!")
            
        else:
            st.write("Complete the remaining task to proceed discharge!")


with st.sidebar:
    with st.expander("Chat Bot:", expanded=True):
        messages = st.container(height=300)
        messages.chat_message("user").write("Hello!")
        messages.chat_message("assistant").write(f"Echo: Hello, how can i help you?")
        if prompt := st.chat_input("Say something"):
            messages.chat_message("user").write(prompt)
            messages.chat_message("assistant").write(f"Echo: {prompt}")

