from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    email_id: EmailStr 
    first_name: str
    last_name: Optional[str] = None  
    password: str
    phone_no: str
    organization: str

    @field_validator("phone_no")
    @classmethod
    def validate_phone_no(cls, value: str):
        if not value.isdigit():
            raise ValueError("Phone number must contain only digits")

        if len(value) != 10:
            raise ValueError("Phone number must be 10 digits")

        return value
    

class UserResponse(BaseModel):
    user_id: str 
    first_name: str
    last_name: Optional[str] = None
    email_id: EmailStr
    phone_no: str
    created_at: datetime
    organization: str

    model_config = ConfigDict(from_attributes=True)
