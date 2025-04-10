# /usr/bin/python

from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class ServiceValidationResult(BaseModel):
    valid_services: List[str]
    invalid_services: List[str]
    message: str


class CollectDetails(BaseModel):
    Name: str
    email: str
    phone_number: str
    services: List[str] = Field(description="List of valid services")



class Appointment(BaseModel):
    startTime: str | None = None
    endTime: str | None = None
    subject: str | None = None
    user: str | None = None
    body : str | None = None
   


class Appointment_Customer(BaseModel):
    progress:Optional[List[str]] = Field(default=[], description="Excution history")
    conv_context: Optional[List[Dict]] = Field(default=[], description="conversation histroy of an LLM")
    Name: str | None = None
    Email: str | None = None
    Phone_number: str | None = None
    Services: Optional[List[str]] = Field(default=None, description="List of valid services")
    Booked_appointment: Appointment | None = None
    Dropoff: Optional[bool] = None
    Satisfaction: Optional[int] = None