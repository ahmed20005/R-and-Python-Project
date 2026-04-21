from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import User
from app.schemas import (
    StudentCreate, 
    StudentUpdate, 
    StudentResponse, 
    StudentListResponse
)
from app.services import student_service, user_service
from app.utils.security import get_current_user, get_current_admin_user
from app.utils.logger import get_logger
from app.utils.cache import get_cache

router = APIRouter(prefix="/students", tags=["Students"])
logger = get_logger()
cache = get_cache()


@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    student_data: StudentCreate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new student (Admin only)"""
    # Verify the user_id exists
    user = user_service.get_user_by_id(db, user_id=student_data.user_id)
    if not user:
        logger.warning(f"Failed to create student - user not found: {student_data.user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if user already has a student profile
    existing_student = student_service.get_student_by_user_id(db, user_id=student_data.user_id)
    if existing_student:
        logger.warning(f"Failed to create student - user already has profile: {student_data.user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has a student profile"
        )
    
    student = student_service.create_student(db=db, student_data=student_data)
    
    # Invalidate cache
    cache.delete_pattern("students:*")
    
    logger.info(f"Admin created student: {student.id} for user: {student_data.user_id}")
    return student


@router.get("/", response_model=StudentListResponse)
def get_all_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    department: Optional[str] = None,
    gpa_min: Optional[float] = None,
    gpa_max: Optional[float] = None,
    enrollment_year: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all students with filtering and pagination"""
    # Try to get from cache
    cache_key = f"students:list:{skip}:{limit}:{department}:{gpa_min}:{gpa_max}:{enrollment_year}"
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.debug(f"Cache hit for students list")
        return cached_data
    
    students, total = student_service.get_all_students(
        db=db,
        skip=skip,
        limit=limit,
        department=department,
        gpa_min=gpa_min,
        gpa_max=gpa_max,
        enrollment_year=enrollment_year
    )
    
    response = StudentListResponse(
        students=students,
        total=total,
        page=(skip // limit) + 1,
        page_size=limit
    )
    
    # Cache the response
    cache.set(cache_key, response.model_dump())
    
    logger.info(f"Retrieved students list (total={total}, skip={skip}, limit={limit})")
    return response


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific student by ID"""
    # Try to get from cache
    cache_key = f"student:{student_id}"
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.debug(f"Cache hit for student: {student_id}")
        return cached_data
    
    student = student_service.get_student_by_id(db, student_id=student_id)
    if not student:
        logger.warning(f"Student not found: {student_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Students can only view their own profile unless they are admin
    if current_user.role != "admin" and student.user_id != current_user.id:
        logger.warning(f"Unauthorized access attempt to student {student_id} by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. You can only view your own profile."
        )
    
    # Cache the response
    cache.set(cache_key, model_to_dict(student))
    
    logger.info(f"Retrieved student: {student_id}")
    return student


def model_to_dict(model_obj):
    """Convert SQLAlchemy model to dict"""
    return {c.name: getattr(model_obj, c.name) for c in model_obj.__table__.columns}


@router.put("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: int,
    student_data: StudentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a student's information"""
    student = student_service.get_student_by_id(db, student_id=student_id)
    if not student:
        logger.warning(f"Student not found for update: {student_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Students can only update their own profile unless they are admin
    if current_user.role != "admin" and student.user_id != current_user.id:
        logger.warning(f"Unauthorized update attempt on student {student_id} by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. You can only update your own profile."
        )
    
    # Regular students have limited update capabilities
    if current_user.role != "admin":
        # Students can only update certain fields
        allowed_updates = ["phone", "address"]
        update_dict = student_data.model_dump(exclude_unset=True)
        for field in update_dict:
            if field not in allowed_updates:
                logger.warning(f"Student attempted to update restricted field: {field}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Students cannot update {field}. Only admins can."
                )
    
    updated_student = student_service.update_student(
        db=db,
        student_id=student_id,
        student_data=student_data,
        user_id=current_user.id
    )
    
    # Invalidate cache
    cache.delete(f"student:{student_id}")
    cache.delete_pattern("students:list:*")
    
    logger.info(f"Updated student: {student_id} by user: {current_user.username}")
    return updated_student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a student (Admin only)"""
    student = student_service.get_student_by_id(db, student_id=student_id)
    if not student:
        logger.warning(f"Student not found for deletion: {student_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    success = student_service.delete_student(
        db=db,
        student_id=student_id,
        user_id=current_user.id
    )
    
    if not success:
        logger.error(f"Failed to delete student: {student_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete student"
        )
    
    # Invalidate cache
    cache.delete(f"student:{student_id}")
    cache.delete_pattern("students:list:*")
    
    logger.info(f"Admin deleted student: {student_id}")


@router.get("/{student_id}/audit-logs")
def get_student_audit_logs(
    student_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get audit logs for a student (Admin only)"""
    student = student_service.get_student_by_id(db, student_id=student_id)
    if not student:
        logger.warning(f"Student not found for audit logs: {student_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    logs = student_service.get_student_audit_logs(db, student_id=student_id)
    logger.info(f"Admin retrieved audit logs for student: {student_id}")
    return logs
