from sqlalchemy.orm import Session
from app.models import Student, AuditLog
from app.schemas import StudentCreate, StudentUpdate
from typing import Optional, List
from datetime import datetime
import json


def get_student_by_id(db: Session, student_id: int) -> Optional[Student]:
    return db.query(Student).filter(Student.id == student_id).first()


def get_student_by_user_id(db: Session, user_id: int) -> Optional[Student]:
    return db.query(Student).filter(Student.user_id == user_id).first()


def get_all_students(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    department: Optional[str] = None,
    gpa_min: Optional[float] = None,
    gpa_max: Optional[float] = None,
    enrollment_year: Optional[int] = None
) -> tuple[List[Student], int]:
    query = db.query(Student)
    
    # Apply filters
    if department:
        query = query.filter(Student.department.ilike(f"%{department}%"))
    if gpa_min is not None:
        query = query.filter(Student.gpa >= gpa_min)
    if gpa_max is not None:
        query = query.filter(Student.gpa <= gpa_max)
    if enrollment_year is not None:
        query = query.filter(Student.enrollment_year == enrollment_year)
    
    total = query.count()
    students = query.offset(skip).limit(limit).all()
    
    return students, total


def create_student(db: Session, student_data: StudentCreate) -> Student:
    db_student = Student(**student_data.model_dump())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    
    # Create audit log
    audit_log = AuditLog(
        student_id=db_student.id,
        user_id=student_data.user_id,
        action="CREATE",
        new_values=json.dumps(student_data.model_dump())
    )
    db.add(audit_log)
    db.commit()
    
    return db_student


def update_student(
    db: Session, 
    student_id: int, 
    student_data: StudentUpdate,
    user_id: int
) -> Optional[Student]:
    db_student = get_student_by_id(db, student_id)
    if not db_student:
        return None
    
    # Get old values for audit
    old_values = {
        "first_name": db_student.first_name,
        "last_name": db_student.last_name,
        "department": db_student.department,
        "gpa": db_student.gpa,
        "enrollment_year": db_student.enrollment_year,
        "phone": db_student.phone,
        "address": db_student.address
    }
    
    update_data = student_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_student, field, value)
    
    db.commit()
    db.refresh(db_student)
    
    # Create audit log
    audit_log = AuditLog(
        student_id=student_id,
        user_id=user_id,
        action="UPDATE",
        old_values=json.dumps(old_values),
        new_values=json.dumps(update_data)
    )
    db.add(audit_log)
    db.commit()
    
    return db_student


def delete_student(db: Session, student_id: int, user_id: int) -> bool:
    db_student = get_student_by_id(db, student_id)
    if not db_student:
        return False
    
    # Create audit log before deletion
    old_values = {
        "first_name": db_student.first_name,
        "last_name": db_student.last_name,
        "department": db_student.department,
        "gpa": db_student.gpa,
        "enrollment_year": db_student.enrollment_year,
        "phone": db_student.phone,
        "address": db_student.address
    }
    
    audit_log = AuditLog(
        student_id=student_id,
        user_id=user_id,
        action="DELETE",
        old_values=json.dumps(old_values)
    )
    db.add(audit_log)
    
    db.delete(db_student)
    db.commit()
    return True


def get_student_audit_logs(db: Session, student_id: int) -> List[AuditLog]:
    return db.query(AuditLog).filter(AuditLog.student_id == student_id).order_by(AuditLog.timestamp.desc()).all()
