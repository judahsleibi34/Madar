from pydantic import BaseModel, EmailStr, Field
from typing import Any, Optional, Literal

class ContactMessage(BaseModel):
    name: str = Field(..., max_length=120)
    phone: Optional[str] = Field(default=None, max_length=40)
    message: str = Field(..., max_length=5000)

class SignUpRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str

class LogIn(BaseModel): 
    email: EmailStr
    password: str

class OnboardingSignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    business_name: str
    business_type: str
    subdomain: str
    selected_plan: Optional[dict[str, Any]] = None
    selected_base_plan: Optional[dict[str, Any]] = None
    selected_features: Optional[list[dict[str, Any]]] = None

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
    
class BillingCheckoutRequest(BaseModel):
    subscription_type: Literal["full_platform", "individual_builder"]
    plan: Literal["starter", "pro", "business", "basic", "premium"]
    builder_type: Optional[
        Literal["website", "forms", "quiz", "reservation", "reports", "data"]
    ] = None


class AdminBillingUpdateRequest(BillingCheckoutRequest):
    tenant_id: int
    payment_status: Literal["pending", "active", "past_due", "canceled"] = "active"


class BillingWebhookUpdateRequest(AdminBillingUpdateRequest):
    provider_event_id: Optional[str] = None


class AdminUserTypeUpdateRequest(BaseModel):
    user_type: Literal["admin", "user"]
    
class UpdatePassword(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
    
    
