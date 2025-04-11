#! /usr/bin/python
import os
import ast
import json
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

pickup_dropoff_agent = Agent(
    name="pickup_dropoff_agent", 
    instructions="You are a helpful Assistant. you provide pickup and drop-off service "
                "Keep responses short 1 sentence or less. Do not answer questions that do not belong to an appointment booking agent."
                "first use check_dropoff_availability tool to see if the dropoff service is available,"
                "if dropoff servie is available then ask user if a dropoff service is required"
                "if the user needs a dropoff use arrange_dropoff tool to arrange it"
                "After finsihing the dropoff arrangements, Ask the user to rate the conversation between 1-10, and call call_record_logger tool to finish conversation",
    model="gpt-4o-mini",
    tools=[arrange_dropoff, check_dropoff_availability, call_record_logger])


time_slot_negotiator = Agent(
    name="time_slot_negotiator", 
    handoff_description="you will be shceduling appointmnets based on users request.",
    instructions="You are a helpful assistant."
                "Keep responses short within a sentence or less. Do not answer questions that do not belong to an appointment booking agent."
                f"For reference time and date now is {datetime_iso_format}, format all the dates in ISO 8601 format"
                "You just ask the prefered dates and time window to book an appointent"
                "After prefered time slot, use get_filled_appointments tool to get a list of filled appointments and propose slots that do not overlap with them."
                "To book the appointment use book_appointment tool"
                "To cancel the appointment use cancel_appointment tool",
    model="gpt-4o-mini",
    tools=[get_filled_appointments, book_appointment, cancel_appointment]
    )
#


class AnalysisSummary(BaseModel):
    summary: str
    """Short text summary for this aspect of the analysis."""




details_collector = Agent(
    name="details_collector", 
    instructions="You are a helpful receptionist. When someone speaks to you, collect the following details: "
                "Keep responses short 1 sentence or less. Do not answer questions that do not belong to an appointment booking agent."
                f"The valid services you offer are {','.join(VALID_SERVICES)}, customer can book or more services"
                "Name, email, phone number, and services they want to book. Whenever you get any of the details first verify them"
                "To verify email, mobile number, services use the tools verify_email, verify_mobile_no and verify_services"
                "if they are not valid ask again and wait till you get valid, you can use as many function calls as you want"
                "Once all the details are filled call details_formatter_fn",
    model="gpt-4o-mini",
    tools=[verify_email, verify_mobile_no, verify_services, details_formatter_fn]
    )


summary_agent = Agent(
    name="summary_agent", 
    instructions="you need to summarize the conversation betwen a customer trying to book and appointment and LLM Agent",
    model="gpt-4o-mini",
    output_type=AnalysisSummary)


 


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

async def invoke_agent(agent, function, context):
    response = await agent.invoke(function, context)
    return response

class BookingAgent:
    def __init__(self):
        self.context = Appointment_Customer()
        self.messages = [{"role": "assistant", "content": "Hi, I am Richard, how can I help you?"}]
        self.details_agent = details_collector
        self.summary_agent = summary_agent
        self.time_agent = time_slot_negotiator
        self.dropoff_agent = pickup_dropoff_agent

    async def handle(self, user_input: str):
        self.messages.append({"role": "user", "content": user_input})
        current_step = self.context.progress[-1] if self.context.progress else "Initial_state"

        if current_step == "Initial_state":
            return await self._handle_details()

        if current_step == "details_collected":
            return await self._handle_summary()

        if current_step == "summary_appended":
            return await self._handle_timeslot()

        if current_step == "appointment_booked":
            return await self._handle_dropoff_check()

        if current_step == "Dropoff_arranged":
            return "Your Appointment is booked and Drop off is arranged, Bye, have a nice day!"

        return "I'm not sure how to proceed. Please try again."

    async def _handle_details(self):
        response = await Runner.run(self.details_agent, input=self.messages, context=self.context)
        final = response.final_output
        return self._append_response(final)

    async def _handle_summary(self):
        response = await Runner.run(self.summary_agent, input=self.messages, context=self.context)
        self.context.conv_context.append({"role": self.details_agent.name, "content": response.final_output.summary})
        self.context.progress.append("summary_appended")
        return self._append_response(response.final_output.summary)

    async def _handle_timeslot(self):
        response = await Runner.run(self.time_agent, input=self.messages, context=self.context)
        return self._append_response(response.final_output)

    async def _handle_dropoff_check(self):
        availability = await check_dropoff_availability(self.context)
        if availability == "dropoff available":
            response = await Runner.run(self.dropoff_agent, input=self.messages, context=self.context)
            return self._append_response(response.final_output)
        else:
            return "Dropoff not available. Appointment remains booked."

    def _append_response(self, content):
        self.messages.append({"role": "assistant", "content": str(content)})
        return content

    def get_context(self):
        return self.context

    def get_messages(self):
        return self.messages


booking_agent = st.session_state.get("booking_agent", BookingAgent())
response = await booking_agent.handle(user_input)
st.session_state["booking_agent"] = booking_agent




# Context initialization
now_utc = datetime.now()
datetime_iso_format = now_utc.isoformat()


def main():
    # Set page configuration
    st.set_page_config(page_title="Telepathy AI Assistant", page_icon="💬", layout="wide")
    
    # Load dropoff data
    try:
        dropoff_data = json.load(open("pickup_drop_off.json", "r"))
    except Exception as e:
        st.error(f"Error loading dropoff data: {e}")
        dropoff_data = {"_default": {}}

    # Initialize session variables
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "context" not in st.session_state:
        st.session_state.context = Appointment_Customer()

    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hi, I am Richard, how can I help you?"}]

    # Page layout with sidebar and main chat
    with st.sidebar:
        st.title("🧠 Telepathy AI - Debug Info")

        with st.expander("📌 Current Context", expanded=False):
            try:
                st.json(st.session_state.context.model_dump())
            except Exception:
                st.code(str(st.session_state.context), language="python")

        with st.expander("📈 Progress", expanded=True):
            progress_map = {
                "details_collected": "🟢 Details Collected",
                "summary_appended": "📝 Summary Appended",
                "appointment_booked": "✅ Appointment Booked",
                "appointment_cancelled": "❌ Appointment Cancelled",
                "call_record_updated": "📞 Call Record Updated",
            }
            for step in st.session_state.context.progress:
                st.markdown(f"- {progress_map.get(step, step)}")

        # Enhanced dropoff editor
        update_dropoff_data = render_dropoff_editor(dropoff_data)
        print(f"update_dropoff_data {update_dropoff_data}")

        with st.expander("💬 Conversation History", expanded=False):
            st.json(st.session_state.messages)

        with st.expander("🚗 Raw Dropoff Data", expanded=False):
            st.json(dropoff_data)

        st.markdown("---")
        st.caption(f"Session ID: `{st.session_state.session_id}`")

        if st.button("🔄 Reset Session"):
            st.session_state.clear()
            st.rerun()

    # Main chat area
    st.title("💬 Telepathy AI Assistant")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Type your message here..."):
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Assistant response handling
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                context = st.session_state.context
                if not context.conv_context:
                    context.conv_context = []

                if context.progress == []:
                    response = asyncio.run(run_agent(details_collector, st.session_state.messages, context))
                    if isinstance(response, CollectDetails):
                        st.markdown(response.model_dump())
                        st.session_state.messages.append({"role": "assistant", "content": str(response.model_dump())})
                    else:
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})

                elif context.progress[-1] == "details_collected":
                    response = asyncio.run(run_agent(summary_agent, st.session_state.messages, context))
                    context.conv_context.append({"role": details_collector.name, "content": response.summary})
                    context.progress.append("summary_appended")

                elif context.progress[-1] == "summary_appended":
                    response = asyncio.run(run_agent(time_slot_negotiator, st.session_state.messages, context))
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

                elif context.progress[-1] == "appointment_cancelled":
                    st.session_state.messages = [{"role": "assistant", "content": "Bye, have a nice day!"}]
                    st.session_state.clear()
                    st.rerun()

                elif context.progress[-1] == "appointment_booked":
                    response = invoke_agent(pickup_dropoff_agent, check_dropoff_availability, context)
                    response = asyncio.run(run_agent(pickup_dropoff_agent, st.session_state.messages, context))
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

                elif context.progress[-1] == "Dropoff_arrianged":
                    st.session_state.messages = [{"role": "assistant", "content": "Bye, have a nice day!"}]
                    st.session_state.clear()
                    st.rerun()

                else:
                    st.session_state.messages = [{"role": "assistant", "content": "Something went wrong..."}]


if __name__ == "__main__":
    main()
