from pydantic import BaseModel, EmailStr
from typing import Optional

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

class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None

class PasswordReset(BaseModel):
    access_token: str
    password: str

class WebsiteSettingsUpdate(BaseModel):
    subdomain: Optional[str] = None
    brand: Optional[str] = None
    footer_store_name: Optional[str] = None
    logo_url: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    phone: Optional[str] = None
    description: Optional[str] = None