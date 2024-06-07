import random
import datetime
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu
from streamlit_timeline import timeline
import datetime
import time
import json
# from dotenv import load_dotenv
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
# load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

# Configure the Google Generative AI with the API key
# genai.configure(api_key=api_key)


def get_all_notes_text(df, nhs_id):
    # note = ''
    r = df[df["NHS Number"] == nhs_id]
    r1 = ", ".join(r["Notes Entry"].astype(str))
    return r1


def color_severity(val):
    color = 'red' if val == "High" else 'yellow' if val == "Moderate" else 'green'
    return f'background-color: {color}'

# Function to update the value in session state


def clicked(button):
    st.session_state.clicked[button] = True


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
        # generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        # generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        # generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
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


st.set_page_config(
    page_title="FloWell App",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    logo_url = "data/logo.jpg"
    st.markdown("<h1 style='text-align: center; font-size: 50px; font-family: Serif;, color: #141A46;'>FloWell</h1>", unsafe_allow_html=True)
    st.sidebar.image(logo_url, use_column_width=True)
    selected = option_menu("Main Menu", ["Home", 'Admissions', "Clinical Notes"],
                           icons=['house', 'hospital', "clipboard"], menu_icon="cast", default_index=2)


if selected == "Home":
    st.title(':blue[_Flowell_]')
    desc = """
        Welcome to Flowell! An application designed to enhance integrated care and discharge processes by summarising information from patient electronic health records into an accurate timeline of events, creating a more productive pipeline that flows well!
        
        FloWell provides exactly that. Using StreamLit, Vertex AI and Gemini API, we created a dynamic navigator of the patient’s journey, turning complex notes into a clear, concise timeline, so you can understand their journey in seconds.
        """
    st.write(desc)

elif selected == "Admissions":

    st.subheader("NHS Hospitals Admissions:")

    df_hospitals = pd.read_csv("data/Hospital.csv")
    df_hospitals.dropna(inplace=True)
    st.map(df_hospitals,
           latitude='Latitude',
           longitude='Longitude',
           )

    df_admissions = pd.read_csv("data/admissions.csv")[:100]

    tab1, tab2 = st.tabs(["📈 Chart", "🗃 Data"])
    tab1.subheader("A tab with a chart")
    tab1.line_chart(df_admissions["Ip Elect Total"])

    tab2.subheader("A tab with the data")
    tab2.dataframe(df_admissions)

else:
    df_patients = pd.read_csv("data/patients.csv")
    ids = df_patients["NHS Number"].unique()
    # text_model_pro = load_model()

    # Patient selector
    id_option = st.selectbox("Select the patient nhsID:", (ids))
    # st.write("You selected:", id_option)

    # patient info
    with st.expander("See patient details:"):
        patient_details = df_patients[df_patients["NHS Number"] == id_option].T
        patient_details = patient_details.set_axis(['Details'], axis='columns')
        st.dataframe(patient_details, use_container_width=True)

    # Read notes dataframe
    df_notes = pd.read_csv("data/updated_patient_notes.csv")
    patient_note = get_all_notes_text(df_notes, int(id_option))
    specialities = df_notes["Clinician Type"].unique()

    # *************** Checklist for problems, put the firts prompt here*********************
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
        ],
        "Severity": [
            "Moderate",
            "Low",
            "Moderate",
            "High",
            "Low",
            "Low"
        ],
        'Status': [
            "Managed",
            "Active",
            "Resolved",
            "Active",
            "Resolved",
            "Managed"
        ],
    }

    df_problems = pd.DataFrame(problems)
    edited_df = st.data_editor(df_problems.style.applymap(color_severity, subset=[
                               'Severity']), use_container_width=True, disabled=["Severity"])

    st.header("Vertex AI Gemini API", divider="rainbow")
    tab1, tab2, tab3 = st.tabs(
        ["📑 Notes Summary", "⌛ Patient Timeline", "📩 Discharge Section"])

    #####################################################################################################################################
    # *********************************** Summarize LLM, put the firts prompt here *******************************************************
    #####################################################################################################################################
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

        prompt = f""" 
            Generate a current, up to date summary of the patient's journey. The length of the summary should be {length_of_summary}. The response should be returned as {type_of_text}.

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
                first_tab1, first_tab2 = st.tabs(
                    ["Generate summary", "Prompt"])
                with first_tab1:

                    response = ["hello this is the summary"]
                    # response = get_gemini_pro_text_response(
                    #     text_model_pro,
                    #     prompt,
                    #     generation_config=config,
                    # )
                    if response:
                        st.write("Your summary:")
                        with st.chat_message("user"):
                            container = st.container(border=True)
                            st.write(response)
                with first_tab2:
                    st.text(prompt)

    #####################################################################################################################################
    # *********************************** Timeline, put the firts prompt here ************************************************************
    #####################################################################################################################################
    with tab2:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            start = st.date_input("Select start date",
                                  datetime.date(2019, 7, 6))

        with col2:
            end = st.date_input("Select end date", datetime.date(2019, 7, 6))

        with col3:
            filter_timeline = st.selectbox("Which stage you want to filter?",
                                           (None, "Admission", "Patient Care", "Discharge"))

        with col4:
            options = st.multiselect("Specialist filter",
                                     specialities,
                                     ["Nurse", "Doctor"])

        # ------------------------------------ Timeline prompt section----------------------------------------------------------------------------
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

        # Create the session with button clicked
        if 'clicked' not in st.session_state:
            st.session_state.clicked = False

        def click_button():
            st.session_state.clicked = True

        generate_timeline = st.button(
            "Generate the timeline", on_click=click_button)

        if st.session_state.clicked and prompt:
            # The message and nested widget will remain on the page
            # st.write(prompt)
            with st.spinner("Generating your story using Gemini ..."):
                first_tab1, first_tab2 = st.tabs(["Timeline", "Prompt"])

                with first_tab1:

                    # TODO: load data static for now, change whith json when it comes
                    with open('data/patient_timeline.json', "r") as f:
                        response = f.read()

                    # response = get_gemini_pro_text_response(
                    #     text_model_pro,
                    #     prompt,
                    #     generation_config=config,
                    # )
                    if response:
                        # st.write(response)
                        # import pdb; pdb.set_trace()
                        # temp = ''.join(response).replace('```', '').replace('\n', '').replace(' ', '').replace("'",'"').replace("json","")
                        # items = json.loads(temp)
                        items = response

                        # with st.expander("See raw response"):
                        #     st.write(items)

                        st.subheader("Patient event timeline:")

                        # render timeline
                        timeline(items, height=500)

                with first_tab2:
                    st.text(prompt)

    #####################################################################################################################################
    # *************************************************** Discharge **********************************************************************
    #####################################################################################################################################
    with tab3:
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
            "Completed": [
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
        discharge_edited = st.data_editor(
            df_discharge, use_container_width=True)

        if discharge_edited['Completed'].all() == True:

            if st.button("Discharge", type="primary"):
                st.success("Patient Discharge!")

            tab1, tab2 = st.tabs(
                ["Discharge Summary", "Patient discharge letter"])

            with tab1:
                with st.container(border=True):
                    st.header("Discharge Summary")
                    if st.button("Generate summary"):
                        txt = """\n
                            You were admitted to the hospital with severe chest pain radiating to your left arm. This indicated a possible heart attack (myocardial infarction).
                            Upon arrival, an EKG was performed, which showed signs of a heart attack. Blood tests confirmed this diagnosis. A cardiologist recommended an urgent procedure called a coronary angioplasty with stent placement to open up a blocked artery.
                            The procedure was successful in opening the blocked artery in your left anterior descending artery (LAD) and placing a stent. You recovered well from the procedure, and your pain was managed with medication.
                            During your stay, you received physical therapy, occupational therapy, and education from a dietician to help you recover and regain your strength. You also had an echocardiogram, which showed good left ventricular function with minimal wall motion abnormality.
                            You were discharged home on May 27th with medication and a follow-up appointment scheduled. You were also given instructions for a home exercise program and advice on lifestyle changes to maintain good heart health. Please be sure to contact your doctor if you experience any chest pain, shortness of breath, dizziness, or swelling in your legs.
                            """

                        st.write(txt)
                        st.success("Discharge summary created successfully!")
            with tab2:
                with st.container(border=True):
                    st.header("Patient letter")
                    if st.button("Generate letter"):
                        st.success("Patient letter created successfully!")
                        text_contents = '''\n
                        Patient Discharge Letter

                        Dear [Patient Name],

                        We are pleased to inform you that you have been discharged from the hospital following your recent admission for severe chest pain.

                        Hospital Stay Summary:
                        You were admitted with chest pain radiating to your left arm, indicating a possible heart attack (myocardial infarction). An EKG and blood tests confirmed this. A coronary angioplasty with stent placement was successfully performed on your left anterior descending artery (LAD).

                        Recovery and Care:
                        You recovered well from the procedure, and your pain was managed with medication. You received physical and occupational therapy, and dietary education. An echocardiogram showed good heart function with minimal abnormalities.

                        Discharge Information:

                        Discharge Date: May 27, 2024
                        Medications: Take all prescribed medications as directed.
                        Follow-Up: Attend your scheduled follow-up appointment.
                        Exercise and Lifestyle: Follow the home exercise program and lifestyle changes advised to maintain good heart health.
                        Emergency Instructions:
                        Contact your doctor or seek immediate medical attention if you experience chest pain, shortness of breath, dizziness, or leg swelling.

                        Your health and recovery are our top priorities. Please reach out if you have any questions or concerns.

                        Wishing you a swift recovery,

                        Dr. [Doctor’s Name]
                        [Title]
                        [Hospital Name]

                        Contact Information:
                        [Hospital Contact Information]   
                        '''
                        today = str(datetime.date.today())
                        st.write(text_contents)
                        st.download_button("Download letter", text_contents,   file_name=f"{
                                           id_option}-{today}-letter.txt", type="primary", use_container_width=True)

        else:
            st.warning(
                'Complete the remaining task to proceed discharge!', icon="⚠️")

#####################################################################################################################################
# ****************************************** Chatbot section in sidebar **************************************************************
#####################################################################################################################################

# Streamed response emulator


def response_generator():
    response = random.choice(
        [
            "Hello there! How can I assist you today?",
            "Hi, human! Is there anything I can help you with?",
            "Do you need help?",
        ]
    )
    for word in response.split():
        yield word + " "
        time.sleep(0.05)


with st.sidebar:
    with st.expander("Chat Bot:", expanded=True):
        messages = st.container(height=350, )

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Display chat messages from history on app rerun
        for message in st.session_state.messages:
            with messages.chat_message(message["role"]):
                messages.markdown(message["content"])

        # Accept user input
        if prompt := st.chat_input("Ask something?"):
            # Add user message to chat history
            st.session_state.messages.append(
                {"role": "user", "content": prompt})
            # Display user message in chat message container
            with messages.chat_message("user"):
                messages.markdown(prompt)

            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                response = messages.write_stream(response_generator())
                # Add assistant response to chat history
                st.session_state.messages.append(
                    {"role": "assistant", "content": response})
