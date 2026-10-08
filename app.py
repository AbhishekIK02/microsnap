import json

import streamlit as st
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient

from prompts import (
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
    SUMMARY_REQUEST_PROMPT,
)


# ============================================================
# API / SECRET CONFIGURATION
# ============================================================

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]


# ============================================================
# CLIENT SETUP
# ============================================================

@st.cache_resource
def get_gemini_client():
    return genai.Client(
        api_key=GEMINI_API_KEY
    )


@st.cache_resource
def get_twilio_client():
    return TwilioClient(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN,
    )


gemini_client = get_gemini_client()
twilio_client = get_twilio_client()


# ============================================================
# GEMINI MODEL
# ============================================================

MODEL_NAME = "gemini-3.7-flash"


# ============================================================
# CLEAN WHATSAPP TEXT
# ============================================================

def clean_whatsapp_text(text):

    if not text:
        return "No nutrition summary available."

    text = " ".join(text.split())

    if len(text) > 1500:
        return text[:1500] + "..."

    return text


# ============================================================
# SEND WHATSAPP MESSAGE
# ============================================================

def send_whatsapp(to_number, user_name, summary):

    try:

        content_variables = json.dumps(
            {
                "1": user_name,
                "2": clean_whatsapp_text(summary),
            },
            ensure_ascii=False,
        )

        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_number}",
            content_sid=TWILIO_CONTENT_SID,
            content_variables=content_variables,
        )

        return True, message.sid

    except Exception as error:

        return False, str(error)


# ============================================================
# RENDER CHAT MESSAGE
# ============================================================

def render_message(message):

    with st.chat_message(message["role"]):

        if message["kind"] == "text":

            st.markdown(message["content"])

        elif message["kind"] == "image":

            st.image(
                message["content"],
                use_container_width=True,
            )

        elif message["kind"] == "audio":

            st.audio(message["content"])

        elif message["kind"] == "video":

            st.video(message["content"])

        else:

            st.warning(
                f"Unknown message kind: {message['kind']}"
            )


# ============================================================
# ADD MESSAGE TO CHAT
# ============================================================

def add_message(role, kind, content):

    st.session_state.messages.append(
        {
            "role": role,
            "kind": kind,
            "content": content,
        }
    )

    render_message(
        st.session_state.messages[-1]
    )


# ============================================================
# GEMINI FUNCTION
# ============================================================

def ask_gemini(parts):

    try:

        response = st.session_state.chat.send_message(
            parts
        )

        return response.text

    except Exception as error:

        return (
            f"Sorry, something went wrong: {error}"
        )


# ============================================================
# ONBOARDING
# ============================================================

if "onboarded" not in st.session_state:

    st.title("Welcome to MacroSnap 🥗")

    st.caption(
        "Your friendly AI nutrition buddy! "
        "Snap a photo of your meal or describe it, "
        "and I'll estimate the calories and macros for you!"
    )

    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name"
        )

        whatsapp_number = st.text_input(
            "WhatsApp number (with country code)",
            placeholder="+91XXXXXXXXXX",
            help=(
                "This is the number MacroSnap will send "
                "your meal summaries to. Make sure to "
                "include your country code."
            ),
        )

        submitted = st.form_submit_button(
            "Start using MacroSnap"
        )

    if submitted:

        if (
            not name.strip()
            or not whatsapp_number.strip()
        ):

            st.warning(
                "Please fill in both your name and "
                "WhatsApp number to proceed."
            )

        else:

            st.session_state.name = name.strip()

            st.session_state.whatsapp_number = (
                whatsapp_number.strip()
            )

            # Create Gemini chat
            st.session_state.chat = (
                gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    ),
                )
            )

            st.session_state.messages = []

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# ============================================================
# CREATE CHAT INTERFACE
# ============================================================

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center",
)


# ============================================================
# HEADER
# ============================================================

with header_col:

    st.title("MacroSnap 🥗")


# ============================================================
# WHATSAPP SUMMARY BUTTON
# ============================================================

with button_col:

    send_disabled = (
        len(st.session_state.messages) <= 1
    )

    if st.button(
        "📤 Send to WhatsApp",
        disabled=send_disabled,
        use_container_width=True,
    ):

        with st.spinner(
            "Summarizing your day..."
        ):

            summary = ask_gemini(
                [SUMMARY_REQUEST_PROMPT]
            )

        success, info = send_whatsapp(
            st.session_state.whatsapp_number,
            st.session_state.name,
            summary,
        )

        if success:

            st.success(
                "Sent! Check your WhatsApp 📲"
            )

        else:

            st.error(
                f"Couldn't send that: {info}"
            )


# ============================================================
# USER INFORMATION
# ============================================================

st.caption(
    f"Logged in as {st.session_state.name} | "
    f"WhatsApp: {st.session_state.whatsapp_number} - "
    f"updates go to {st.session_state.whatsapp_number}"
)


# ============================================================
# DISPLAY WELCOME MESSAGE / PREVIOUS MESSAGES
# ============================================================

if not st.session_state.messages:

    add_message(
        "assistant",
        "text",
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        ),
    )

else:

    for message in st.session_state.messages:

        render_message(message)


# ============================================================
# CHAT INPUT
# ============================================================

user_input = st.chat_input(
    "Ask a question, or attach a photo of your meal",
    accept_file=True,
    file_type=[
        "jpg",
        "jpeg",
        "png",
    ],
)


# ============================================================
# PROCESS USER INPUT
# ============================================================

if user_input:

    photo = (
        user_input.files[0]
        if user_input.files
        else None
    )

    text = user_input.text

    parts = []


    # --------------------------------------------------------
    # PROCESS PHOTO
    # --------------------------------------------------------

    if photo is not None:

        photo_bytes = photo.getvalue()

        # Display uploaded image
        add_message(
            "user",
            "image",
            photo_bytes,
        )

        # Send image to Gemini
        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type,
            )
        )


    # --------------------------------------------------------
    # PROCESS TEXT
    # --------------------------------------------------------

    if text:

        add_message(
            "user",
            "text",
            text,
        )

        parts.append(text)


    # --------------------------------------------------------
    # PHOTO WITHOUT TEXT
    # --------------------------------------------------------

    elif photo is not None:

        parts.append(
            "What is this meal? "
            "Give me the calories and macros."
        )


    # --------------------------------------------------------
    # ASK GEMINI
    # --------------------------------------------------------

    if parts:

        with st.spinner(
            "Crunching the numbers..."
        ):

            answer = ask_gemini(parts)

    else:

        answer = (
            "Please enter a question or upload "
            "a meal photo."
        )


    # --------------------------------------------------------
    # DISPLAY GEMINI ANSWER
    # --------------------------------------------------------

    add_message(
        "assistant",
        "text",
        answer,
    )