from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRoleEnum(str, Enum):
    admin = "admin"
    student = "student"


# User Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    role: UserRoleEnum = UserRoleEnum.student


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[UserRoleEnum] = None


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# Student Schemas
class StudentBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    date_of_birth: Optional[str] = None
    department: str = Field(..., min_length=2, max_length=100)
    gpa: float = Field(default=0.0, ge=0.0, le=4.0)
    enrollment_year: int = Field(..., ge=1900, le=2100)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None


class StudentCreate(StudentBase):
    user_id: int


class StudentUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    date_of_birth: Optional[str] = None
    department: Optional[str] = Field(None, min_length=2, max_length=100)
    gpa: Optional[float] = Field(None, ge=0.0, le=4.0)
    enrollment_year: Optional[int] = Field(None, ge=1900, le=2100)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None


class StudentResponse(StudentBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class StudentListResponse(BaseModel):
    students: list[StudentResponse]
    total: int
    page: int
    page_size: int


# Audit Log Schema
class AuditLogResponse(BaseModel):
    id: int
    student_id: int
    user_id: int
    action: str
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True
