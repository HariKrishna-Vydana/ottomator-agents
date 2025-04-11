import streamlit as st
import os
import asyncio
import json
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

from agents import Agent, Runner, function_tool, RunContextWrapper, handoff, HandoffInputData
from agents.extensions import handoff_filters

from dotenv import load_dotenv
import uuid
import ast
from formats.pydantic_utils import ServiceValidationResult, CollectDetails,Appointment, Appointment_Customer
from tool_defs.tool_utils import verify_email, verify_mobile_no, verify_services, book_appointment, cancel_appointment, get_filled_appointments, details_formatter_fn, handoff_message_filter, appointment_reporter, arrange_dropoff,check_dropoff_availability, call_record_logger
from agents.extensions.visualization import draw_graph
from prompts.prompt_utils import BOOKINGAGENT_BASIC_PROMPT


from datetime import datetime, timezone
now_utc = datetime.now(timezone.utc)
datetime_iso_format = now_utc.isoformat()


from tinydb import TinyDB, Query
# Initialize DB file
APPOINTMENTS_DB = TinyDB("appointments.json")
DROPOFF_DB=TinyDB("pickup_drop_off.json")

from UI_helpers.pickup_dropoff import render_dropoff_editor


update_dropoff_data=render_dropoff_editor(json.load(open("pickup_drop_off.json",'r')))
print(f"update_dropoff_data {update_dropoff_data}")

# Function: Add an appointment
# Load environment variables
load_dotenv()


class Appointment(BaseModel):
    startTime: str | None = '2025-04-10T16:30:00Z'
    endTime: str | None = '2025-04-10T17:00:00Z'
    subject: str | None = 'Booing appointment foroil change'
    user: str | None = 'hari.vydana@telepathy.ai'
    body : str | None = 'Booing appointment foroil change'
   


class Appointment_Customer(BaseModel):
    progress:Optional[List[str]] = Field(default=["details_collected", "summary_appended", "appointment_booked"], description="Excution history")
    conv_context: Optional[List[Dict]] = Field(default=None, description="conversation histroy of an LLM")
    Name: str | None = "Hari"
    Email: str | None = "hari.vydana@telepathy.ai"
    Phone_number: str | None = "1234567810"
    Services: Optional[List[str]] = ["oil change", "tire rotation"]
    Booked_appointment: Appointment | None = None
    Dropoff: Optional[bool] = None
    Satisfaction: Optional[int] = None






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

def _handoff_message_filter(handoff_message_data: HandoffInputData) -> HandoffInputData:
    # First, we'll remove any tool-related messages from the message history
    handoff_message_data = handoff_filters.remove_all_tools(handoff_message_data)

    # Second, we'll also remove the first two items from the history, just for demonstration
    history = (
        tuple(handoff_message_data.input_history[2:])
        if isinstance(handoff_message_data.input_history, tuple)
        else handoff_message_data.input_history)

    return HandoffInputData(input_history=history, 
                            pre_handoff_items=tuple(handoff_message_data.pre_handoff_items),
                            new_items=tuple(handoff_message_data.new_items),)





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




#details_collector.handoffs.append(handoff(agent=time_slot_negotiator))
#time_slot_negotiator.handoffs.append(handoff(agent=pickup_dropoff_agent))
#pickup_dropoff_agent.handoffs.append()
 


agent=details_collector
#agent=Orchestrator_Agent
#draw_graph(agent).view()
draw_graph(agent, filename="agent_graph")


@dataclass
class UserContext:
    user_id: str
    Name: str
    email: str
    phone_number: str
    services: List[str] = Field(default_factory=list)


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

async def run_agent_and_update_context(messages, user_id: str) -> UserContext:
    result = await Runner.run(agent, input=messages)
    details: CollectDetails = result.final_output

    # Populate UserContext using collected details
    context = UserContext(
        user_id=user_id,
        Name=details.Name,
        email=details.email,
        phone_number=details.phone_number,
        services=details.services
    )
    return context





def main():
    import streamlit as st
    import uuid
    import asyncio
    

    # Set page configuration
    st.set_page_config(page_title="Telepathy AI Assistant", page_icon="💬", layout="wide")

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

        with st.expander("💬 Conversation History", expanded=False):
            st.json(st.session_state.messages)

        st.markdown("---")
        st.caption(f"Session ID: `{st.session_state.session_id}`")

        if st.button("🔄 Reset Session"):
            st.session_state.clear()
            st.rerun()
        with st.expander("🚗 Dropoff Car Inventory", expanded=False):
            dropoff_data = json.load(open("pickup_drop_off.json","r"))
            st.json(dropoff_data)
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