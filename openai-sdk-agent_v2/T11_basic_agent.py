#! /usr/bin/python
import os
import ast
import json
import time
import uuid
import asyncio
import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel,Field
from tinydb import TinyDB, Query
from typing import List, Optional, Dict
from datetime import datetime, timezone


# Importing custom utility modules
from UI_helpers.pickup_dropoff import render_dropoff_editor
from tool_defs.tool_utils import (
    verify_email, verify_mobile_no, verify_services, book_appointment,
    cancel_appointment, get_filled_appointments, details_formatter_fn,
    handoff_message_filter, appointment_reporter, arrange_dropoff,
    check_dropoff_availability, call_record_logger
)
from agents import Agent, Runner
from agents.extensions.visualization import draw_graph
from formats.pydantic_utils import CollectDetails, Appointment_Customer
from prompts.prompt_utils import BOOKINGAGENT_BASIC_PROMPT

# Load environment variables from .env file
load_dotenv()

# Database initialization
APPOINTMENTS_DB = TinyDB("appointments.json")
DROPOFF_DB = TinyDB("pickup_drop_off.json")

# Get current UTC time in ISO 8601 format
now_utc = datetime.now(timezone.utc)
datetime_iso_format = now_utc.isoformat()





VALID_SERVICES = ast.literal_eval(os.getenv("VALID_SERVICES", "[]"))
WAITING_SECS = ast.literal_eval(os.getenv("WAITING_SECS", 1))










pickup_dropoff_agent = Agent(
    name="pickup_dropoff_agent", 
    instructions="You are a helpful Assistant. you provide pickup and drop-off service "
                "Keep responses short 1 sentence or less. Do not answer questions that do not belong to an appointment booking agent."
                "ask user if the user needs a dropoff service"
                "to arrange dropoff use arrange_dropoff tool"
                "Ask the user to rate the conversation between 1-10, use 0 as default and call call_record_logger tool",
    model="gpt-4o-mini",
    tools=[arrange_dropoff,call_record_logger])


time_slot_negotiator = Agent(
    name="time_slot_negotiator", 
    handoff_description="you will be shceduling appointmnets based on users request.",
    instructions="You are a helpful assistant."
                "Keep responses short within a sentence or less. Do not answer questions that do not belong to an appointment booking agent."
                f"For reference time and date now is {datetime_iso_format}, format all the dates in ISO 8601 format"
                "You just ask the prefered dates and time window to book an appointent"
                "get the filled appointments and propose slots that do not overlap and proceed to booking"
                "To book the appointment use book_appointment tool"
                "To cancel the appointment use cancel_appointment tool"
                "Use get_filled_appointments tool to get the list of filled appointments",
    model="gpt-4o-mini",
    tools=[get_filled_appointments, book_appointment, cancel_appointment]
    )
#


class AnalysisSummary(BaseModel):
    summary: str
    """Short text summary for this aspect of the analysis."""




details_collector = Agent(
    name="details_collector", 
    instructions="You are a helpful Appointment booking assistant."
                "Keep responses short 1 sentence or less. Do not answer questions that do not belong to an appointment booking agent."
                f"The valid services you offer are {','.join(VALID_SERVICES)}, customer can book or more services"
                "You ask for the Name, email, phone number, and services the user need"
                "After every detail you first verify them"
                #"To verify email call , mobile number, services use the tools verify_email, verify_mobile_no and verify_services"
                #"To verify email, mobile number, services use the tools verify_email, verify_mobile_no and verify_services"
                "if the detail is not valid ask again and wait till you get valid information, you can use as many function calls as you want"
                "Once all the details are filled call details_formatter_fn",
    model="gpt-4o-mini",
    tools=[verify_email, verify_mobile_no, verify_services, details_formatter_fn]
    )


summary_agent = Agent(
    name="summary_agent", 
    instructions="you need to summarize the conversation betwen a customer trying to book and appointment and LLM Agent",
    model="gpt-4o-mini",
    output_type=AnalysisSummary)


function_holding_agent = Agent(
    name="function_holding_agent", 
    instructions="The purpose of this agent it to hold the tools",
    model="gpt-4o-mini",
    tools=[check_dropoff_availability]
    )


agent=details_collector
#agent=Orchestrator_Agent
#draw_graph(agent).view()
draw_graph(agent, filename="agent_graph")




async def run_agent(agent, messages, context):
    result = await Runner.run(agent, input=messages, context=context)
    #print(f"Inside run_agent ----> {result}")
    return result.final_output


async def run_summary_agent(agent, messages, context):
    result = await Runner.run(agent, input=messages, context=context)
    #print(f"Inside run_agent ----> {result}")
    return result.final_output







# Context initialization
now_utc = datetime.now()
datetime_iso_format = now_utc.isoformat()

# Set up the main layout


import streamlit as st
import json
import uuid
import asyncio
from typing import Dict, Any



async def main():
    # Set up Streamlit page configuration
    st.set_page_config(page_title="Telepathy AI Assistant", page_icon="💬", layout="wide")

    # Load data
    data = json.load(open("pickup_drop_off.json", 'r'))

    # Initialize session state
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "context" not in st.session_state:
        st.session_state.context = Appointment_Customer()

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hi, I am Richard, how can I help you?"}]

    # ---------- SIDEBAR ----------
    with st.sidebar:
        if st.button("🔄 Reset Session"):
            st.session_state.clear()
            st.rerun()

        st.title("🛠️ Debug Panel")
        # Dropoff Car Editor
        updated_data = render_dropoff_editor(data)
        print(f"Updated Dropoff Data: {updated_data}")

        # Current Context
        with st.expander("📌 Current Context"):
            st.json(st.session_state.context)

        # Progress Overview
        with st.expander("📈 Progress"):
            progress_map = {
                "details_collected": "🟢 Details Collected",
                "summary_appended": "📝 Summary Appended",
                "appointment_booked": "✅ Appointment Booked",
                "appointment_cancelled": "❌ Appointment Cancelled",
                "Dropoff_arranged": "❌ Dropoff Arranged",
                "call_record_updated": "📞 Call Record Updated",
            }
            for step in st.session_state.context.progress:
                st.markdown(f"- {progress_map.get(step, step)}")

        # Conversation History
        with st.expander("💬 Conversation History"):
            st.json(st.session_state.messages)

        st.caption(f"Session ID: `{st.session_state.session_id}`")

    # ---------- MAIN CHAT AREA ----------
    st.title("💬 Telepathy AI Assistant")

    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Display the context as a third message in the chat
    with st.chat_message("context"):  # Custom role for context
        st.markdown(f"**Context:**\n\n{st.session_state.context}")
    
    # Handle user input
    if user_input := st.chat_input("Type your message here..."):
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                context = st.session_state.context
                
                if context.progress[-1]=="Initial_state":
                    response = await run_agent(details_collector, st.session_state.messages, context)
                    if isinstance(response, CollectDetails):
                        st.markdown(response.model_dump())
                        st.session_state.messages.append({"role": "assistant", "content": str(response.model_dump())})
                    else:
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                
                if context.progress[-1] == "details_collected":
                    response = await run_agent(summary_agent, st.session_state.messages, context)
                    context.conv_context.append({"role": details_collector.name, "content": response.summary})
                    context.progress.append("summary_appended")

                if context.progress[-1] == "summary_appended":
                    response = await run_agent(time_slot_negotiator, st.session_state.messages, context)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

                if context.progress[-1] == "appointment_cancelled":
                    response="Your Appointment is cancelled, Bye, have a nice day!"
                    st.success(response)
                    Wait_Clear(WAITING_SECS)

                if context.progress[-1] == "appointment_booked":
                    response = await check_dropoff_availability(context)
                    
                    if response=="dropoff available":
                        response = await run_agent(pickup_dropoff_agent, st.session_state.messages, context)
                        st.markdown(response)
                        
                    else:
                        response="Your Appointment is cancelled, Bye, have a nice day!"
                        st.success(response)
                        Wait_Clear(WAITING_SECS)

                if context.progress[-1] == "Dropoff_arranged":
                    response="Your Appointment is booked and Drop off is arranged, Bye, have a nice day!"
                    st.success(response)
                    Wait_Clear(WAITING_SECS)
                

                # Updates for next
                st.session_state.context=context
                #print(context)
                st.markdown(f"**Context:**\n\n{st.session_state.context}")



def Wait_Clear(waiting_secs=WAITING_SECS):
    placeholder = st.empty()
    for i in range(waiting_secs, 0, -1):
        placeholder.markdown(f"⏳ Waiting... {i} sec")
        time.sleep(1)
    placeholder.empty()
    st.session_state.clear()
    st.rerun()













if __name__ == "__main__":
    asyncio.run(main())
