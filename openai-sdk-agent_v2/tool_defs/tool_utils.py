# /usr/bin/python

import os
from agents import function_tool, RunContextWrapper
import streamlit as st
import os
import asyncio
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional, Tuple,  Dict, Any
#from pydantic import BaseModel, Field
from formats.pydantic_utils import ServiceValidationResult, CollectDetails, Appointment, Appointment_Customer
import ast
import aiohttp
from dateutil import parser


from agents import Agent, HandoffInputData, Runner, function_tool, handoff, trace
from agents.extensions import handoff_filters


from dotenv import load_dotenv
load_dotenv()


VALID_SERVICES = ast.literal_eval(os.getenv("VALID_SERVICES", "[]"))
#print(VALID_SERVICES)
from tinydb import TinyDB, Query
APPOINTMENTS_DB = TinyDB("appointments.json")
DROPOFF_DB=TinyDB("pickup_drop_off.json")
CallRECORDS_DB=TinyDB("callrecords.json")


@function_tool
async def verify_email(context: RunContextWrapper[Appointment_Customer], email: str) -> str:
    """Check if the email is valid"""
    if '@' in email and email.count('@') == 1 and '.' in email.split('@')[-1]:
        context.context.Email=email
        return "email is valid"
    return "email is invalid"

@function_tool
async def verify_mobile_no(context: RunContextWrapper[Appointment_Customer], mobile_no: str) -> str:
    """Check if mobile number is valid"""
    digits = [char for char in mobile_no if char.isdigit()]
    if len(digits) == 10:
        context.context.Phone_number=mobile_no
        return "mobile number is valid"
    return "mobile number is invalid"


@function_tool
async def verify_services(context: RunContextWrapper[Appointment_Customer], services: List[str]) -> ServiceValidationResult:
    """Check if the services are valid and return structured feedback."""
    valid = [s for s in services if s in VALID_SERVICES]
    invalid = [s for s in services if s not in VALID_SERVICES]
    
    if not invalid:
        context.context.Services=services
        return "All selected services are valid."
    else:
        return f"selected services {invalid} are invalid, would you like to modify"
    

async def propose_slots_negotiator(activity: str, appointmentid: str, starttime: Optional[str], endingtime: Optional[str]):
    """This tool does interacts with the calender, 
    its expected to do these activities [propose, cancel, book, reschedule, retrive]"""
        # todo
    pass;

@function_tool
async def arrange_dropoff(context: RunContextWrapper[Appointment_Customer])->str:
    """ This tool arranges the dropoff service"""
    User=Query()
    context.context.Dropoff=True
    curr_ser=context.context.Services[0]
    curr_ser_row = DROPOFF_DB.search(User.service == curr_ser)[0]
    curr_ser_row['dropoff_cars']-=1
    DROPOFF_DB.update(curr_ser_row, User.service == curr_ser)
    print(f"Updated records: {DROPOFF_DB.all()}")
    context.context.progress.append('Dropoff_arrianged')
    return "dropoff has been updated"

@function_tool
async def check_dropoff_availability(context: RunContextWrapper[Appointment_Customer])-> str:
    """ This tool checks if the dropoff service is available"""
    cars_available=0
    User=Query()
    for s in context.context.Services:
        #breakpoint()
        result = DROPOFF_DB.search(User.service == s)
        print(result)
        if result:
            dropoff_info = result[0]
            cars_available+=dropoff_info.get('dropoff_cars', 0)
        print(cars_available)
    
    if cars_available > 0:
        return "The dropoff cars are available"
    else:
        return "The dropoff cars are not available"






@function_tool
async def details_formatter_fn(context: RunContextWrapper[Appointment_Customer], name: Optional[str], email: Optional[str], phone_number: Optional[str], services: Optional[List[str]])-> str:
    """format the colledted details and add it to the user context"""
    context.context.Name = name
    context.context.Email = email
    context.context.Phone_number = phone_number
    context.context.Services = services
    context.context.progress.append("details_collected")
    return f"finished collecting and your details"

@function_tool
async def appointment_reporter(context: RunContextWrapper[Appointment_Customer], startTime: Optional[str], endTime: Optional[str], subject: Optional[str], email: Optional[str], body: Optional[str]) -> str:
    """ after the appointment is filled report the parameters for adding it to the user context"""
    if context.context.Booked_appointment is None:
        context.context.Booked_appointment = Appointment()
    
    context.context.Booked_appointment.startTime=startTime
    context.context.Booked_appointment.endTime=endTime
    context.context.Booked_appointment.subject=subject
    context.context.Booked_appointment.user=email
    context.context.Booked_appointment.body=body
    return f"finished reporting the appointment"

    




@function_tool
async def call_record_logger(context: RunContextWrapper[Appointment_Customer], feedback:Optional[int])-> str:
    """This function logs the whole conversation to finish the conversation"""
    context.context.Satisfaction=feedback
    CallRECORDS_DB.insert(context.context.dict())
    context.context.progress.append("call_record_updated")
    return "call_record_updated"

async def retrive_appointment(email:str)->Dict[str, Any]:
    """The function retives the stored appointments from the database"""
    User=Query()
    result = APPOINTMENTS_DB.search(User.user == email)

    if not result:
        return "There are not booked appoinments with this email, can not be canceled"
    return result[-1];


@function_tool
async def get_filled_appointments(context: RunContextWrapper[Appointment_Customer])-> List[Tuple]:
    """The function interacts with calender and gives the list of already filled appointments"""
    User=Query()
    email=context.context.Email
    result = APPOINTMENTS_DB.search(User.user == email)
    time_slots=[(ele['startTime'], ele['endTime']) for ele in result]
    print(time_slots)
    if not time_slots:
        return []
    return time_slots


@function_tool
async def cancel_appointment(context: RunContextWrapper[Appointment_Customer])-> str:
    """The function cancels the appointment"""
    email = context.context.Email
    retrived_appointment_dict = await retrive_appointment(email)
    #print(retrived_appointment_dict['user'].strip("'"))
    #print(retrived_appointment_dict['id'].strip("'"))

    User=Query()
    result = APPOINTMENTS_DB.search(User.user == email)
    if result:
        remove_item=result[-1]
        APPOINTMENTS_DB.remove(doc_ids=[remove_item.doc_id])
        context.context.progress.append("appointment_cancelled")
        return "appointment cancellation succeeded!"
    else:
        return "There is no appointment booked did not proceed cancellation"



@function_tool
async def cancel_appointment_vorig(context: RunContextWrapper[Appointment_Customer])-> str:
    """The function cancels the appointment"""
    email = context.context.Email
    retrived_appointment_dict = await retrive_appointment(email)
    print(retrived_appointment_dict['user'].strip("'"))
    print(retrived_appointment_dict['id'].strip("'"))

    User=Query()
    result = APPOINTMENTS_DB.search(User.user == email)
    remove_item=result[-1]
    APPOINTMENTS_DB.remove(doc_ids=[remove_item.doc_id])


    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(
                "http://localhost:8000/meetings",
                params={
                    "id": retrived_appointment_dict['id'].strip("'"),
                    "user": retrived_appointment_dict['user'].strip("'"),
                },
            ) as resp:
                if resp.status == 204 :
                    resp_json=await resp.json()
                    return "appointment cancellation succeeded!"
                else:
                    resp_json=await resp.json()
                    return "appointment cancellation failed!"
        except Exception as e:
            return f"Error canceling the appointment: {e}"







@function_tool
async def book_appointment(context: RunContextWrapper[Appointment_Customer], startTime: str, endTime: str,) -> str:
    """The function books the appointment"""

    subject="Booing appointment for"+ ",".join(context.context.Services)
    email = context.context.Email
    body = subject

    input_json={"startTime": startTime, "endTime": endTime, "subject": subject, "user": email,"body": body,}
    
    
    new_endTime = datetime.fromisoformat(endTime)-timedelta(minutes=1)
    endTime=new_endTime.isoformat().replace("+00:00", "Z")

    new_startTime = datetime.fromisoformat(startTime)-timedelta(minutes=1)
    startTime=new_startTime.isoformat().replace("+00:00", "Z")

    print(f"Inside booking appointments........{input_json}")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "http://localhost:8000/meetings",
                json=input_json,
            ) as resp:
                if resp.status == 200:
                    resp_json=await resp.json()
                    input_json.update({"id": resp_json["id"], "user":email})
                    APPOINTMENTS_DB.insert(input_json)

                    if context.context.Booked_appointment is None:
                        context.context.Booked_appointment = Appointment()
                    context.context.Booked_appointment.startTime=startTime
                    context.context.Booked_appointment.endTime=endTime
                    context.context.Booked_appointment.subject=subject
                    context.context.Booked_appointment.user=email
                    context.context.Booked_appointment.body=body
                    CallRECORDS_DB.insert(context.context.dict())
                    context.context.progress.append("appointment_booked")
                    return "booking succeeded!"
                else:
                    return "booking failed!"
        except Exception as e:
            return f"Error booking meeting: {e}"
        


def handoff_message_filter(handoff_message_data: HandoffInputData) -> HandoffInputData:
    # First, we'll remove any tool-related messages from the message history
    handoff_message_data = handoff_filters.remove_all_tools(handoff_message_data)
    history=handoff_message_data
    """
    # Second, we'll also remove the first two items from the history, just for demonstration
    history = (
        tuple(handoff_message_data.input_history[2:])
        if isinstance(handoff_message_data.input_history, tuple)
        else handoff_message_data.input_history) """
    
    return HandoffInputData(
        input_history=history,
        pre_handoff_items=tuple(handoff_message_data.pre_handoff_items),
        new_items=tuple(handoff_message_data.new_items),
    )