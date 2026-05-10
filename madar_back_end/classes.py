from pydantic import BaseModel, EmailStr

class ContactMessage(BaseModel):
    name: str
    phone: str
    message: str

class SignUpRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str

class LogIn(BaseModel): 
    email: EmailStr
    password: str