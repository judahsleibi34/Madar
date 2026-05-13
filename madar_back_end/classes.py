from pydantic import BaseModel, EmailStr

class ContactMessage(BaseModel):
    name: str
    email: EmailStr
    message: str

class SignUpRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str

class LogIn(BaseModel): 
    email: EmailStr
    password: str

class PasswordReset(BaseModel):
    access_token: str
    password: str