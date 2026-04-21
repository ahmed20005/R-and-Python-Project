from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db, User
from app.schemas import UserCreate, UserResponse, UserLogin, Token, UserUpdate
from app.services import user_service
from app.utils.security import (
    verify_password, 
    create_access_token, 
    get_current_user, 
    get_current_admin_user
)
from app.utils.logger import get_logger
from datetime import timedelta
from app.utils.config import get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger()
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if username already exists
    existing_user = user_service.get_user_by_username(db, username=user_data.username)
    if existing_user:
        logger.warning(f"Registration failed - username already exists: {user_data.username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_email = user_service.get_user_by_email(db, email=user_data.email)
    if existing_email:
        logger.warning(f"Registration failed - email already exists: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user = user_service.create_user(db=db, user_data=user_data)
    logger.info(f"User registered successfully: {user.username} (role: {user.role})")
    return user


@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Login and get access token"""
    user = user_service.get_user_by_username(db, username=login_data.username)
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        logger.warning(f"Login failed - invalid credentials for username: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    logger.info(f"User logged in successfully: {user.username}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    logger.debug(f"Retrieved current user info: {current_user.username}")
    return current_user


@router.put("/me", response_model=UserResponse)
def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user information"""
    # Regular users can only update their email
    if user_data.role and current_user.role != "admin":
        logger.warning(f"Unauthorized role update attempt by: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update roles"
        )
    
    updated_user = user_service.update_user(db, user_id=current_user.id, user_data=user_data)
    logger.info(f"User updated: {current_user.username}")
    return updated_user


@router.get("/users", response_model=list[UserResponse])
def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get all users (Admin only)"""
    logger.info(f"Admin retrieved all users (skip={skip}, limit={limit})")
    users = user_service.get_all_users(db, skip=skip, limit=limit)
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get a specific user by ID (Admin only)"""
    user = user_service.get_user_by_id(db, user_id=user_id)
    if not user:
        logger.warning(f"User not found: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    logger.info(f"Admin retrieved user: {user.username}")
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a user (Admin only)"""
    if user_id == current_user.id:
        logger.warning(f"Admin attempted to delete themselves: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    success = user_service.delete_user(db, user_id=user_id)
    if not success:
        logger.warning(f"User not found for deletion: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    logger.info(f"Admin deleted user: {user_id}")
