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
# http://35.184.85.28:8501/

# Load environment variables from .env file
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

# Configure the Google Generative AI with the API key
genai.configure(api_key=api_key)


def get_all_notes_text(df, nhs_id):
    # note = ''
    # r = df[df["NHS Number"] == nhs_id]
    r = df.query("`NHS Number` == @nhs_id")
    r1 = ", ".join(df["Combined"].astype(str))
    return r1


def color_priority(val):
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
    #"gemini-1.5-flash-001", "gemini-1.5-pro-001"
    text_model_pro = genai.GenerativeModel("gemini-1.5-flash-001")
    return text_model_pro

@st.cache_resource
def load_chatbot_agent():
    agent = genai.GenerativeModel("gemini-1.5-pro-001")
    chat = agent.start_chat(history = [])
    return chat

def get_gemini_pro_text_response(
    model: genai.GenerativeModel,
    contents: str,
    generation_config: GenerationConfig,
    stream: bool = True,
):

    safety_settings = {
    #     generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_NONE,
    #     generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_NONE,
    #     generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_NONE,
    #     generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_NONE,
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


def get_chatbot_response(model, question):
    responses = model.send_message(question, stream=True)

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

#####################################################################################################################################
#**************************************** Streamlit app starting ********************************************************************
#####################################################################################################################################

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
        Welcome to FloWell!

        FloWell is an advanced discharge navigation tool designed to enhance integrated care and discharge processes by summarizing patient information from electronic health records (EHR) into a clear, concise timeline. Using **Streamlit**, **Vertex AI**, and **Gemini API**, FloWell turns complex patient notes into an accurate timeline of events, allowing you to understand a patient's journey in seconds.

        By aggregating all patient notes, FloWell generates key summaries and constructs a comprehensive timeline from admission to discharge. This innovative tool identifies the necessary steps required for a patient’s discharge, addressing challenges related to synthesizing large volumes of data entries from various healthcare professionals. FloWell enhances resource allocation, improves communication among healthcare staff, reduces clinical errors, and ultimately optimizes patient outcomes and hospital efficiency.
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

# Clinical notes section
else:
    df_patients = pd.read_csv("data/patients.csv")
    ids = df_patients["NHS Number"].unique()
    text_model_pro = load_model()

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
    df_notes['Combined'] = df_notes['Date'].astype(str) +":"+ df_notes["Notes Entry"]
    patient_note = get_all_notes_text(df_notes, nhs_id=2233445671)

    # print(df_notes.head())
    specialities = df_notes["Clinician Type"].unique()

    # *************** Checklist for problems, put the firts prompt here*********************
    st.header("Patient problem list:", divider="rainbow")

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
        "Priority": [
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
    edited_df = st.data_editor(df_problems.style.map(color_priority, subset=[
                               'Priority']), use_container_width=True, disabled=["Priority"])

    st.header("Vertex AI Gemini API", divider="rainbow")
    tab1, tab2, tab3 = st.tabs(
        ["📑 Notes Summary", "⌛ Patient Timeline", "📩 Discharge Section"])

    #####################################################################################################################################
    # *********************************** Summarize LLM, put the firts prompt here ******************************************************
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

        # ------------------------------------ Summary prompt section----------------------------------------------------------------------------
        prompt = f"""
            You are tasked with being an assistant in healthcare. Write a coincise summary of the patient's journey from the following text delimited by tripple backquotes. 
            which consists of patient hospital notes/records. The length of the summary should be {length_of_summary}. The response should be returned as {type_of_text}.

            Patient Input Notes: ```{patient_note}``` \n

            Output Example:\n
            Patient 1, a 62-year-old female with a history of poorly controlled type 2 diabetes, hypertension, and hyperlipidemia, was admitted to the hospital for hyperglycemia, dehydration, and possible skin infection. She presented with excessive thirst, frequent urination, blurred vision, fatigue, and increased appetite. Upon admission, she received intravenous fluids and regular insulin drip, and her blood glucose levels gradually decreased. Her skin lesions were treated with topical antibiotics and showed signs of improvement. After a successful course of treatment, she was discharged home with instructions for self-monitoring blood glucose levels, medication regimen, and follow-up appointments.

        """

        config = {
            "max_output_tokens": 8192,
            "temperature": 1,
            "top_p": 0.95,
        }

        generate_t2t = st.button("Generate summary", key="generate_t2t")

        if generate_t2t and prompt:
            # st.write(prompt)
            with st.spinner("Generating your story using Gemini ..."):
                first_tab1, first_tab2 = st.tabs(
                    ["Generate summary", "Prompt"])
                
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
                    st.code(prompt)

    #####################################################################################################################################
    # *********************************** Timeline, put the firts prompt here ***********************************************************
    #####################################################################################################################################
    with tab2:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            start = st.date_input("Select start date",
                                  datetime.date(2019, 7, 6))

        with col2:
            end = st.date_input("Select end date", datetime.date(2019, 7, 6))

        with col3:
            options = st.multiselect("Specialist filter",specialities, ["Nurse", "Doctor"])

        with col4:
            filter_timeline = st.selectbox("Which stage you want to filter?",(None, "Admission", "Patient Care", "Discharge"))
            top_k = st.number_input("Top k events", min_value=3, max_value=15, value=7)
            

        # ------------------------------------ Timeline prompt section----------------------------------------------------------------------------
        example = """
                {
                    "events": [
                        {
                            "start_date": {
                                "year": "2023",
                                "month": "5",
                                "day": "1"
                            },
                            "text": {
                                "headline": "Patient Admission",
                                "text": "Patient was admitted to Hospital X on May 1, 2023 AM with complaints of chest pain and shortness of breath"
                            }
                        }
                    ]
                }
        """
        prompt = f"""
            Your task is to generate a patient timeline by summarising clinical notes in triple quotes below from a patient's stay in hospital\n

            Instructions:\n
            Highlight the key events from their visit: this includes admission, procedures, significant clinical events, clinical incidents or adverse reactions, and discharge. Base everything on the notes given only and do not make any medical assumptions.\n 
            Try to anonymize personal information\n
            Please make sure to provide RFC8259 compliant JSON with the key start_date, headline, text which is summary of headline and make sure that brackets and all delimiters are placed andclosed correctly so it doesnt throw an error, this is the most important check you need to do.\n
            Make sure that date is correct and complete with no spaces in each field.\n
            Give me only the top {top_k} key important events\n
            Please follow this as a correct example: {example}\n
            Output it as one bullet point per highlight that is a few words long.\n
            Output it in chronological order.\n
            Patient notes input to extract events: ```{patient_note}```\n
        """

        #--------------------------------Model with instructions: Emily -----------------------------------------------
        # system_instruct = """
        # You are summarising clinical notes from a patient's stay in hospital. Highlight the key events from their visit: this includes admission, procedures, significant clinical events, clinical incidents or adverse reactions, and discharge. Base everything on the notes given only and do not make any medical assumptions. Output it in chronological order. Output it as one bullet point per highlight that is a few words long.
        # Output it as a .json file. There should be an initial heading of "events". Each day should have a maximum of 3 items Each highlight should be an item which includes: "start_date" which breaks down to "day", "month", "year".  and then "text" which includes "headline", and "text" - which should contain verbatim snippets from the relevant notes. There should only be one highlight for each day.
        # """
        # # If you want to give instructions
        # timeline_model = genai.GenerativeModel("gemini-1.5-flash-001", system_instruction=[system_instruct])
        # prompt = patient_note
        
        config = {
            "temperature": 1,
            "top_p": 0.95,
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
                    # with open('data/patient_timeline.json', "r") as f:
                    #     response = f.read()

                    response = get_gemini_pro_text_response(
                        text_model_pro,
                        # timeline_model, #prompt with instruction
                        prompt,
                        generation_config=config,
                    )
                    if response:
                        # st.write(response)
                        # import pdb; pdb.set_trace()
                        temp = ''.join(response).replace('```', '').replace('\n', '').replace('\'', '').replace("json","").strip()
                        items = json.loads(temp)
                        # items = response

                        with st.expander("See raw response"):
                            st.write(response)

                        st.subheader("Patient event timeline:")

                        # render timeline
                        timeline(items, height=500)

                with first_tab2:
                    st.code(prompt)

    #####################################################################################################################################
    # *************************************************** Discharge *********************************************************************
    #####################################################################################################################################
    with tab3:
        st.subheader("Discharge section:")
        st.spinner('LLM is generating tasks, be patient...')

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
                # st.success("Patient Discharge!")
                st.toast('Patient Discharged!', icon='📤')

            tab1, tab2 = st.tabs(
                ["Discharge letter", "Patient Leaflet"])

            with tab1:
                with st.container(border=True):
                    st.header("Discharge letter")
                    if st.button("Generate letter"):
                        st.success("Patient letter created successfully!")
                        text_contents = '''\n

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
                        st.download_button("Download letter", text_contents,   file_name=f"{id_option}-{today}-letter.txt", type="primary", use_container_width=True)
            
            with tab2:
                with st.container(border=True):
                    st.header("Patient Leaflet")
                    if st.button("Generate summary"):
                        txt = """\n
                            You were admitted to the hospital with severe chest pain radiating to your left arm. This indicated a possible heart attack (myocardial infarction).
                            Upon arrival, an EKG was performed, which showed signs of a heart attack. Blood tests confirmed this diagnosis. A cardiologist recommended an urgent procedure called a coronary angioplasty with stent placement to open up a blocked artery.
                            The procedure was successful in opening the blocked artery in your left anterior descending artery (LAD) and placing a stent. You recovered well from the procedure, and your pain was managed with medication.
                            During your stay, you received physical therapy, occupational therapy, and education from a dietician to help you recover and regain your strength. You also had an echocardiogram, which showed good left ventricular function with minimal wall motion abnormality.
                            You were discharged home on May 27th with medication and a follow-up appointment scheduled. You were also given instructions for a home exercise program and advice on lifestyle changes to maintain good heart health. Please be sure to contact your doctor if you experience any chest pain, shortness of breath, dizziness, or swelling in your legs.
                            """

                        st.write(txt)
                        st.success("Patient leaflet summary created successfully!")
        else:
            st.warning(
                'Complete the remaining task to proceed discharge!', icon="⚠️")

#####################################################################################################################################
# ****************************************** Chatbot section in sidebar *************************************************************
#####################################################################################################################################

with st.sidebar:
    st.sidebar.markdown("<h1 style='text-align: center; color: red;'>Chat Bot Agent</h1>", unsafe_allow_html=True)
    with st.expander("**Expand Agent:**", expanded=True):
        messages = st.container(height=350, )

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # model = generative_models.GenerativeModel("gemini-pro") 
        chat = load_chatbot_agent()

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
            with messages.chat_message("assistant"):
                with st.spinner("Chatbot agent is answering ..."):
                    response = get_chatbot_response(model=chat, question=prompt)

                # Add assistant response to chat history
                st.session_state.messages.append(
                    {"role": "assistant", "content": response})
                messages.markdown(response)