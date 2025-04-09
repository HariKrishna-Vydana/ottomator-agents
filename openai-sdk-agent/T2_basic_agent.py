import streamlit as st
import os
import asyncio
import json
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel, Field

from agents import Agent, Runner
from dotenv import load_dotenv


# Load environment variables
load_dotenv()




class CollectDetails(BaseModel):
    Name: str
    email: str
    phone_number: str
    services: List[str] = Field(description="List of valid services")


valid_services=["oil change", "Service", "Tire rotation", "General check", "Quote", "Sales"]


agent = Agent(
    name="Assistant", 
    instructions="You are a helpful receptionist. When someone speaks to you, collect the following details: "
                "Name, email, phone number, and services they want to book. "
                "Keep responses short (1-2 sentences). "
    f"Valid services include: {', '.join(valid_services)}.",
    model="gpt-4o-mini"
    )



# instructions="You are a helpful receptionist. When someone speaks to you, you need to collect the details. keep the response simple and do not speak more than 2 sentences "
# "Always be polite, you need to collect the name, email, phone number, and ask the services they want to book. "
# f"Check if the services are valid and if they are valid then proceed, the valid services are: {' '.join(valid_services)}."







@dataclass
class UserContext:
    user_id: str
    Name: str
    email: str
    phone_number: str
    services: List[str] = Field(default_factory=list)


async def run_agent(messages):
    result = await Runner.run(agent, input=messages)
    return result.final_output


async def run_agent_and_update_context(messages, user_id: str) -> UserContext:
    result = await Runner.run(agent, input=messages)
    details: CollectDetails = result.final_output
    print(details)
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
    st.set_page_config(page_title="Telepathy AI Assistant", page_icon="💬", layout="wide")

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
                #response = asyncio.run(run_agent(st.session_state.messages))
                #st.markdown(response)

                context = asyncio.run(run_agent_and_update_context(st.session_state.messages, user_id="user123"))
                st.success("All details collected!")
                st.json(context.__dict__)

        #st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()