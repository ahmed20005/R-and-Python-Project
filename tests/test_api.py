import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db, User, Student, UserRole
from app.main import app
from app.utils.security import get_password_hash
import json

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with overridden database dependency"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    """Create an admin user"""
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("admin123"),
        role=UserRole.admin
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def student_user(db_session):
    """Create a regular student user"""
    user = User(
        username="student1",
        email="student1@example.com",
        hashed_password=get_password_hash("student123"),
        role=UserRole.student
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def student_profile(db_session, student_user):
    """Create a student profile"""
    student = Student(
        user_id=student_user.id,
        first_name="John",
        last_name="Doe",
        department="Computer Science",
        gpa=3.5,
        enrollment_year=2022,
        phone="1234567890",
        address="123 Main St"
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


class TestAuthentication:
    """Test authentication functionality"""
    
    def test_register_user(self, client, db_session):
        """Test user registration"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "password123",
                "role": "student"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "student"
    
    def test_register_duplicate_username(self, client, admin_user):
        """Test registering with duplicate username"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "admin",
                "email": "different@example.com",
                "password": "password123",
                "role": "student"
            }
        )
        assert response.status_code == 400
        assert "Username already registered" in response.json()["detail"]
    
    def test_register_duplicate_email(self, client, admin_user):
        """Test registering with duplicate email"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "differentuser",
                "email": "admin@example.com",
                "password": "password123",
                "role": "student"
            }
        )
        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]
    
    def test_login_success(self, client, admin_user):
        """Test successful login"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]
    
    def test_get_current_user(self, client, admin_user):
        """Test getting current user info"""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        # Get current user
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert data["role"] == "admin"
    
    def test_unauthorized_access(self, client):
        """Test accessing protected endpoint without token"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestRoleBasedAccess:
    """Test role-based access control"""
    
    def test_admin_can_access_admin_endpoints(self, client, admin_user):
        """Test that admin can access admin-only endpoints"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
    
    def test_student_cannot_access_admin_endpoints(self, client, student_user):
        """Test that regular students cannot access admin-only endpoints"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "student1",
                "password": "student123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]
    
    def test_student_can_only_view_own_profile(self, client, student_user, student_profile, admin_user):
        """Test that students can only view their own profile"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "student1",
                "password": "student123"
            }
        )
        token = login_response.json()["access_token"]
        
        # Try to access another student's profile (should fail)
        response = client.get(
            f"/api/v1/students/999",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should be 404 (not found) or 403 (forbidden)
        assert response.status_code in [403, 404]


class TestStudentCRUD:
    """Test CRUD operations for students"""
    
    def test_admin_create_student(self, client, admin_user, student_user):
        """Test admin creating a student profile"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.post(
            "/api/v1/students/",
            json={
                "user_id": student_user.id,
                "first_name": "Jane",
                "last_name": "Doe",
                "department": "Mathematics",
                "gpa": 3.8,
                "enrollment_year": 2023,
                "phone": "0987654321",
                "address": "456 Oak Ave"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "Jane"
        assert data["department"] == "Mathematics"
    
    def test_student_cannot_create_student(self, client, student_user):
        """Test that regular students cannot create student profiles"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "student1",
                "password": "student123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.post(
            "/api/v1/students/",
            json={
                "user_id": student_user.id,
                "first_name": "Test",
                "last_name": "User",
                "department": "CS",
                "gpa": 3.0,
                "enrollment_year": 2023
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
    
    def test_get_all_students(self, client, admin_user, student_profile):
        """Test getting all students with pagination"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.get(
            "/api/v1/students/?skip=0&limit=10",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "students" in data
        assert "total" in data
        assert data["total"] >= 1
    
    def test_filter_students_by_department(self, client, admin_user, student_profile):
        """Test filtering students by department"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.get(
            "/api/v1/students/?department=Computer%20Science",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
    
    def test_get_student_by_id(self, client, student_user, student_profile):
        """Test getting a student by ID"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "student1",
                "password": "student123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.get(
            f"/api/v1/students/{student_profile.id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == student_profile.id
        assert data["first_name"] == "John"
    
    def test_update_student_own_profile(self, client, student_user, student_profile):
        """Test student updating their own profile (limited fields)"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "student1",
                "password": "student123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.put(
            f"/api/v1/students/{student_profile.id}",
            json={
                "phone": "9999999999",
                "address": "New Address"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["phone"] == "9999999999"
        assert data["address"] == "New Address"
    
    def test_student_cannot_update_gpa(self, client, student_user, student_profile):
        """Test that students cannot update their GPA"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "student1",
                "password": "student123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.put(
            f"/api/v1/students/{student_profile.id}",
            json={
                "gpa": 4.0
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert "cannot update gpa" in response.json()["detail"].lower()
    
    def test_admin_update_student(self, client, admin_user, student_profile):
        """Test admin updating a student profile"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.put(
            f"/api/v1/students/{student_profile.id}",
            json={
                "gpa": 3.9,
                "department": "Updated Department"
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["gpa"] == 3.9
        assert data["department"] == "Updated Department"
    
    def test_admin_delete_student(self, client, admin_user, student_profile):
        """Test admin deleting a student"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.delete(
            f"/api/v1/students/{student_profile.id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 204
        
        # Verify deletion
        response = client.get(
            f"/api/v1/students/{student_profile.id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
    
    def test_student_cannot_delete(self, client, student_user, student_profile):
        """Test that students cannot delete students"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "student1",
                "password": "student123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.delete(
            f"/api/v1/students/{student_profile.id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403


class TestValidationAndErrors:
    """Test validation and error handling"""
    
    def test_invalid_email_format(self, client):
        """Test invalid email format"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "invalid-email",
                "password": "password123",
                "role": "student"
            }
        )
        assert response.status_code == 422
    
    def test_invalid_gpa_range(self, client, admin_user, student_user):
        """Test invalid GPA range"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.post(
            "/api/v1/students/",
            json={
                "user_id": student_user.id,
                "first_name": "Test",
                "last_name": "User",
                "department": "CS",
                "gpa": 5.0,  # Invalid: > 4.0
                "enrollment_year": 2023
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422
    
    def test_invalid_enrollment_year(self, client, admin_user, student_user):
        """Test invalid enrollment year"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.post(
            "/api/v1/students/",
            json={
                "user_id": student_user.id,
                "first_name": "Test",
                "last_name": "User",
                "department": "CS",
                "gpa": 3.0,
                "enrollment_year": 3000  # Invalid year
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422
    
    def test_nonexistent_user_for_student_creation(self, client, admin_user):
        """Test creating student for nonexistent user"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.post(
            "/api/v1/students/",
            json={
                "user_id": 99999,
                "first_name": "Test",
                "last_name": "User",
                "department": "CS",
                "gpa": 3.0,
                "enrollment_year": 2023
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]
    
    def test_get_nonexistent_student(self, client, admin_user):
        """Test getting nonexistent student"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        response = client.get(
            "/api/v1/students/99999",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
        assert "Student not found" in response.json()["detail"]


class TestAuditLogging:
    """Test audit logging functionality"""
    
    def test_audit_log_created_on_student_creation(self, client, admin_user, student_user):
        """Test that audit log is created when student is created"""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            }
        )
        token = login_response.json()["access_token"]
        
        # Create student
        response = client.post(
            "/api/v1/students/",
            json={
                "user_id": student_user.id,
                "first_name": "Audit",
                "last_name": "Test",
                "department": "CS",
                "gpa": 3.5,
                "enrollment_year": 2023
            },
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 201
        student_id = response.json()["id"]
        
        # Get audit logs
        response = client.get(
            f"/api/v1/students/{student_id}/audit-logs",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) >= 1
        assert logs[0]["action"] == "CREATE"


class TestHealthAndMetrics:
    """Test health check and metrics endpoints"""
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_metrics_endpoint(self, client):
        """Test metrics endpoint"""
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
