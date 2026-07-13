from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
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
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    subdomain: Optional[str] = None
    selected_plan: Optional[dict[str, Any]] = None
    terms_accepted: bool = False

class LogIn(BaseModel): 
    email: EmailStr
    password: str

class OnboardingSignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    subdomain: Optional[str] = None
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
    request_token: Optional[str] = Field(default=None, min_length=20, max_length=500)


class EmailVerificationResendRequest(BaseModel):
    email: Optional[EmailStr] = None

class WebsiteSettingsUpdate(BaseModel):
    subdomain: Optional[str] = None
    brand: Optional[str] = None
    footer_store_name: Optional[str] = None
    logo_url: Optional[str] = None
    # Empty contact details are valid and are normalized by website_routes.
    # EmailStr rejects "" during request parsing, preventing users from
    # intentionally clearing an optional contact email.
    contact_email: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    
class BillingCheckoutRequest(BaseModel):
    subscription_type: Literal["full_platform", "individual_builder"]
    plan: Literal[
        "starter",
        "pro",
        "business",
        "cms",
        "forms_data",
        "cms_plus",
        "complete",
        "basic",
        "premium",
    ]
    builder_type: Optional[
        Literal["website", "forms", "quiz", "reservation", "reports", "data"]
    ] = None


class AdminBillingUpdateRequest(BillingCheckoutRequest):
    tenant_id: int
    payment_status: Literal["pending", "active", "past_due", "canceled", "expired"] = "active"


class BillingWebhookUpdateRequest(AdminBillingUpdateRequest):
    provider_event_id: str = Field(..., min_length=1, max_length=200)
    provider_occurred_at: Optional[datetime] = None


class AdminUserTypeUpdateRequest(BaseModel):
    user_type: Literal["admin", "user"]


class AdminAccountAccessGenerateRequest(BaseModel):
    email: EmailStr


class AdminAccountAccessVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^[A-Za-z0-9!@#$%&*?]{6}$",
    )
    
class UpdatePassword(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str

class MfaEnrollRequest(BaseModel):
    friendly_name: Optional[str] = Field(default=None, max_length=64)


class MfaEnrollVerifyRequest(BaseModel):
    factor_id: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=6, max_length=12)


class MfaLoginChallengeRequest(BaseModel):
    factor_id: str = Field(..., min_length=1, max_length=200)


class MfaLoginVerifyRequest(BaseModel):
    factor_id: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=6, max_length=12)
    challenge_id: Optional[str] = Field(default=None, max_length=200)
