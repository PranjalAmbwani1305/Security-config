import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.rbac import Role


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)
    full_name: str = Field(min_length=1, max_length=200)
    organization_name: str | None = Field(default=None, max_length=200)
    invitation_token: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)
    organization_id: uuid.UUID | None = None


class SSORequest(BaseModel):
    credential: str = Field(min_length=10)
    organization_name: str | None = Field(default=None, max_length=200)
    invitation_token: str | None = None
    organization_id: uuid.UUID | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class AcceptInvitationRequest(BaseModel):
    invitation_token: str


class SwitchOrgRequest(BaseModel):
    organization_id: uuid.UUID


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str
    email_verified: bool
    is_platform_admin: bool


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool


class MembershipOut(BaseModel):
    organization: OrganizationOut
    role: Role


class SessionOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    organization: OrganizationOut | None
    role: Role | None
    permissions: list[str]


class MeOut(BaseModel):
    user: UserOut
    organization: OrganizationOut | None
    role: Role | None
    permissions: list[str]
    memberships: list[MembershipOut]


class ProvidersOut(BaseModel):
    providers: list[str]


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool


class MemberUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class InviteRequest(BaseModel):
    email: EmailStr
    role: Role


class InviteOut(BaseModel):
    invitation_id: uuid.UUID
    email: str
    role: Role
    expires_at: datetime
    # Shown once. Email delivery (SES) is a later increment; until then the
    # admin shares this token/link out-of-band.
    invitation_token: str


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    object_type: str
    object_id: str
    changes: dict | None
    created_at: datetime


class PlatformOrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    admin_email: EmailStr


class PlatformOrgUpdate(BaseModel):
    is_active: bool
