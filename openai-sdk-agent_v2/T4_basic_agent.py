import streamlit as st
import os
import asyncio
import json
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel, Field

from agents import Agent, Runner, function_tool, RunContextWrapper, handoff
from dotenv import load_dotenv
import uuid
import ast
from formats.pydantic_utils import ServiceValidationResult, CollectDetails,Appointment, Appointment_Customer
from tool_defs.tool_utils import verify_email, verify_mobile_no, verify_services, book_appointment, cancel_appointment, get_filled_appointments, check_dropoff_availability, details_formatter_fn, handoff_message_filter, appointment_reporter
from agents.extensions.visualization import draw_graph




from datetime import datetime, timezone
now_utc = datetime.now(timezone.utc)
datetime_iso_format = now_utc.isoformat()



from tinydb import TinyDB, Query
# Initialize DB file
APPOINTMENTS_DB = TinyDB("appointments.json")

DROPOFF_DB=TinyDB("pickup_drop_off.json")
# Function: Add an appointment
# Load environment variables
load_dotenv()


VALID_SERVICES = ast.literal_eval(os.getenv("VALID_SERVICES", "[]"))


time_slot_negotiator = Agent(
    name="time_slot_negotiator", 
    instructions="You are a helpful assistant.You will be shceduling appointmnets based on users request."
                "Keep responses short within a sentence or less. Do not answer questions that do not belong to an appointment booking agent."
                f"For reference time and date now is {datetime_iso_format}, format all the dates in ISO 8601 format"
                "You just ask the prefered dates and time window to book an appointent"
                "After prefered time slot, look at the filled appointments and propose slots that do not overlap."
                "To book the appointment use book_appointment tool, while doing it use email as body"
                "To cancel the appointment use cancel_appointment tool"
                "To get a list of filled appointments use get_filled_appointments"
                "Once all the details are filled hand off to the appointment_reporter",
    model="gpt-4o-mini",
    tools=[get_filled_appointments, book_appointment, cancel_appointment, appointment_reporter]
    )

#"Ask if you need a pickup or dropoff and verify the availability before pickup/drop-off using dropoff_availability_tool"
#dropoff_availability_tool
class AnalysisSummary(BaseModel):
    summary: str
    """Short text summary for this aspect of the analysis."""



details_collector = Agent(
    name="details_collector", 
    instructions="You are a helpful receptionist. When someone speaks to you, collect the following details: "
                "Keep responses short 1 sentence or less. Do not answer questions that do not belong to an appointment booking agent."
                f"The valid services you offer are {','.join(VALID_SERVICES)}"
                "Name, email, phone number, and services they want to book. Whenever you get any of the details first verify them"
                "To verify email, mobile number, services use the tools verify_email, verify_mobile_no and verify_services"
                "if they are not valid ask again and wait till you get valid, you can use as many function calls as you want"
                "Once all the details are filled call details_formatter",
    model="gpt-4o-mini",
    handoffs=[handoff(agent=time_slot_negotiator, on_handoff=handoff_message_filter),],
    tools=[verify_email, verify_mobile_no, verify_services]
    )



'''
Orchestrator_Agent = Agent[Appointment_Customer](
    name="Orchestrator", 
    instructions="You are a helpful receptionist. When someone speaks to you, Ask about what they want"
                "Keep responses short 1 sentence or less. Do not answer questions that do not belong to an appointment booking agent."
                "Use the tools below complete the task"
                "Once all the details are filled hand off to the formatting agent",
    model="gpt-4o-mini",
    handoffs=[details_formatter],
    tools=[details_collector.as_tool(
            tool_name="collect_the_details",
            tool_description="collect the details about the booking an appointment",
        ),
        time_slot_negotiator.as_tool(
            tool_name="time_slot_negotiator",
            tool_description="collect the prefered time slots and book the appointments",
        )]
    )
'''

 


agent=details_collector
#agent=Orchestrator_Agent
#draw_graph(agent).view()
draw_graph(agent, filename="agent_graph.png")


@dataclass
class UserContext:
    user_id: str
    Name: str
    email: str
    phone_number: str
    services: List[str] = Field(default_factory=list)


async def run_agent(messages, context):
    result = await Runner.run(agent, input=messages, context=context)
    return result.final_output


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
    
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4()) 

    st.set_page_config(page_title="Telepathy AI Assistant", page_icon="💬", layout="wide")
    context=Appointment_Customer()

    

    if st.button("🔄 Reset Session"):
        st.session_state.clear()
        st.rerun()


    if "messages" not in st.session_state:
        st.session_state.messages =[{"role": "assistant", "content": "Hii, I am Richard, How can i help you."}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    if user_input := st.chat_input("type your message here..."):
        st.session_state.messages.append({"role":"user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = asyncio.run(run_agent(st.session_state.messages, context))
                print(context)
                if isinstance(response, CollectDetails):
                    st.markdown(response.model_dump())
                    st.session_state.messages.append({"role":"assistant", "content": str(response.model_dump())})
                else:
                    st.markdown(response)
                    st.session_state.messages.append({"role":"assistant", "content": response})
                #context = asyncio.run(run_agent_and_update_context(st.session_state.messages, user_id="user123"))
                #st.success("All details collected!")
                #st.json(context.__dict__)

        #st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()