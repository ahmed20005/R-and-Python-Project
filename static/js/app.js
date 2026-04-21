// API Base URL
const API_BASE = '/api/v1';

// State
let currentUser = null;
let authToken = null;
let currentPage = 1;
const limit = 10;
let currentFilters = {};

// DOM Elements
const authSection = document.getElementById('auth-section');
const mainSection = document.getElementById('main-section');
const userInfo = document.getElementById('user-info');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const studentsTableBody = document.getElementById('students-tbody');
const studentModal = document.getElementById('student-modal');
const viewModal = document.getElementById('view-modal');
const studentForm = document.getElementById('student-form');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setupEventListeners();
});

// Check Authentication
function checkAuth() {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');
    
    if (token && user) {
        authToken = token;
        currentUser = JSON.parse(user);
        showMainSection();
    } else {
        showAuthSection();
    }
}

// Setup Event Listeners
function setupEventListeners() {
    // Auth tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            const tab = e.target.dataset.tab;
            if (tab === 'login') {
                loginForm.style.display = 'flex';
                registerForm.style.display = 'none';
            } else {
                loginForm.style.display = 'none';
                registerForm.style.display = 'flex';
            }
        });
    });

    // Login form
    loginForm.addEventListener('submit', handleLogin);
    
    // Register form
    registerForm.addEventListener('submit', handleRegister);
    
    // Logout
    document.getElementById('logout-btn').addEventListener('click', handleLogout);
    
    // Add student button
    document.getElementById('add-student-btn').addEventListener('click', () => openStudentModal());
    
    // Filter buttons
    document.getElementById('apply-filters-btn').addEventListener('click', applyFilters);
    document.getElementById('clear-filters-btn').addEventListener('click', clearFilters);
    
    // Pagination
    document.getElementById('prev-page-btn').addEventListener('click', () => changePage(-1));
    document.getElementById('next-page-btn').addEventListener('click', () => changePage(1));
    
    // Modal close buttons
    document.querySelectorAll('.close-btn, .cancel-btn').forEach(btn => {
        btn.addEventListener('click', closeModals);
    });
    
    // Student form
    studentForm.addEventListener('submit', handleStudentSubmit);
    
    // Close modal on outside click
    window.addEventListener('click', (e) => {
        if (e.target === studentModal || e.target === viewModal) {
            closeModals();
        }
    });
}

// API Helper
async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
        throw new Error(error.detail || 'An error occurred');
    }
    
    return response.json();
}

// Handle Login
async function handleLogin(e) {
    e.preventDefault();
    
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    
    try {
        const data = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        
        authToken = data.access_token;
        localStorage.setItem('token', data.access_token);
        
        // Get user info
        const user = await apiRequest('/auth/me');
        currentUser = user;
        localStorage.setItem('user', JSON.stringify(user));
        
        showNotification('Login successful!', 'success');
        showMainSection();
        loadStudents();
        
        loginForm.reset();
        document.getElementById('login-error').textContent = '';
    } catch (error) {
        document.getElementById('login-error').textContent = error.message;
    }
}

// Handle Register
async function handleRegister(e) {
    e.preventDefault();
    
    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const role = document.getElementById('register-role').value;
    
    try {
        await apiRequest('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, email, password, role })
        });
        
        showNotification('Registration successful! Please login.', 'success');
        
        // Switch to login tab
        document.querySelector('[data-tab="login"]').click();
        registerForm.reset();
        document.getElementById('register-error').textContent = '';
    } catch (error) {
        document.getElementById('register-error').textContent = error.message;
    }
}

// Handle Logout
function handleLogout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    showAuthSection();
    showNotification('Logged out successfully', 'success');
}

// Show Main Section
function showMainSection() {
    authSection.style.display = 'none';
    mainSection.style.display = 'block';
    userInfo.style.display = 'flex';
    
    document.getElementById('username-display').textContent = currentUser.username;
    const roleBadge = document.getElementById('role-badge');
    roleBadge.textContent = currentUser.role;
    roleBadge.className = `badge ${currentUser.role}`;
    
    // Show add button for admin only
    const addBtn = document.getElementById('add-student-btn');
    addBtn.style.display = currentUser.role === 'admin' ? 'block' : 'none';
    
    loadStudents();
}

// Show Auth Section
function showAuthSection() {
    authSection.style.display = 'block';
    mainSection.style.display = 'none';
    userInfo.style.display = 'none';
}

// Load Students
async function loadStudents() {
    try {
        const params = new URLSearchParams({
            skip: (currentPage - 1) * limit,
            limit: limit,
            ...currentFilters
        });
        
        const data = await apiRequest(`/students/?${params}`);
        renderStudents(data);
        updatePagination(data.total, data.skip, data.limit);
    } catch (error) {
        showNotification(`Error loading students: ${error.message}`, 'error');
    }
}

// Render Students
function renderStudents(data) {
    const students = data.students || data.items || [];
    
    if (students.length === 0) {
        studentsTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center;">No students found</td></tr>';
        return;
    }
    
    studentsTableBody.innerHTML = students.map(student => `
        <tr>
            <td>${student.id}</td>
            <td>${student.first_name} ${student.last_name}</td>
            <td>${student.department}</td>
            <td>${student.gpa.toFixed(2)}</td>
            <td>${student.enrollment_year}</td>
            <td>${student.phone || 'N/A'}</td>
            <td class="action-buttons">
                <button class="btn btn-secondary btn-sm" onclick="viewStudent(${student.id})">View</button>
                ${canEdit(student) ? `<button class="btn btn-primary btn-sm" onclick="editStudent(${student.id})">Edit</button>` : ''}
                ${currentUser.role === 'admin' ? `<button class="btn btn-danger btn-sm" onclick="deleteStudent(${student.id})">Delete</button>` : ''}
            </td>
        </tr>
    `).join('');
}

// Check if current user can edit student
function canEdit(student) {
    return currentUser.role === 'admin' || student.user_id === currentUser.id;
}

// Update Pagination
function updatePagination(total, skip, limit) {
    const totalPages = Math.ceil(total / limit);
    const currentPageNum = Math.floor(skip / limit) + 1;
    
    document.getElementById('page-info').textContent = `Page ${currentPageNum} of ${totalPages}`;
    document.getElementById('prev-page-btn').disabled = currentPageNum === 1;
    document.getElementById('next-page-btn').disabled = currentPageNum === totalPages;
}

// Change Page
function changePage(delta) {
    currentPage += delta;
    if (currentPage < 1) currentPage = 1;
    loadStudents();
}

// Apply Filters
function applyFilters() {
    const department = document.getElementById('filter-department').value.trim();
    const gpaMin = document.getElementById('filter-gpa-min').value;
    const gpaMax = document.getElementById('filter-gpa-max').value;
    const year = document.getElementById('filter-year').value;
    
    currentFilters = {};
    if (department) currentFilters.department = department;
    if (gpaMin) currentFilters.gpa_min = gpaMin;
    if (gpaMax) currentFilters.gpa_max = gpaMax;
    if (year) currentFilters.enrollment_year = year;
    
    currentPage = 1;
    loadStudents();
}

// Clear Filters
function clearFilters() {
    document.getElementById('filter-department').value = '';
    document.getElementById('filter-gpa-min').value = '';
    document.getElementById('filter-gpa-max').value = '';
    document.getElementById('filter-year').value = '';
    currentFilters = {};
    currentPage = 1;
    loadStudents();
}

// View Student
async function viewStudent(id) {
    try {
        const student = await apiRequest(`/students/${id}`);
        
        const content = document.getElementById('view-student-content');
        content.innerHTML = `
            <div class="view-detail">
                <label>ID</label>
                <span>${student.id}</span>
            </div>
            <div class="view-detail">
                <label>Name</label>
                <span>${student.first_name} ${student.last_name}</span>
            </div>
            <div class="view-detail">
                <label>Email</label>
                <span>${student.user?.email || 'N/A'}</span>
            </div>
            <div class="view-detail">
                <label>Department</label>
                <span>${student.department}</span>
            </div>
            <div class="view-detail">
                <label>GPA</label>
                <span>${student.gpa.toFixed(2)}</span>
            </div>
            <div class="view-detail">
                <label>Enrollment Year</label>
                <span>${student.enrollment_year}</span>
            </div>
            <div class="view-detail">
                <label>Phone</label>
                <span>${student.phone || 'N/A'}</span>
            </div>
            <div class="view-detail">
                <label>Address</label>
                <span>${student.address || 'N/A'}</span>
            </div>
            <div class="view-detail">
                <label>Created At</label>
                <span>${new Date(student.created_at).toLocaleDateString()}</span>
            </div>
            <div class="view-detail">
                <label>Last Updated</label>
                <span>${new Date(student.updated_at).toLocaleDateString()}</span>
            </div>
        `;
        
        viewModal.style.display = 'flex';
    } catch (error) {
        showNotification(`Error loading student: ${error.message}`, 'error');
    }
}

// Edit Student
async function editStudent(id) {
    try {
        const student = await apiRequest(`/students/${id}`);
        openStudentModal(student);
    } catch (error) {
        showNotification(`Error loading student: ${error.message}`, 'error');
    }
}

// Open Student Modal
function openStudentModal(student = null) {
    document.getElementById('modal-title').textContent = student ? 'Edit Student' : 'Add Student';
    document.getElementById('student-id').value = student?.id || '';
    document.getElementById('student-first-name').value = student?.first_name || '';
    document.getElementById('student-last-name').value = student?.last_name || '';
    document.getElementById('student-department').value = student?.department || '';
    document.getElementById('student-gpa').value = student?.gpa || '';
    document.getElementById('student-enrollment-year').value = student?.enrollment_year || new Date().getFullYear();
    document.getElementById('student-phone').value = student?.phone || '';
    document.getElementById('student-address').value = student?.address || '';
    
    studentModal.style.display = 'flex';
    document.getElementById('student-form-error').textContent = '';
}

// Close Modals
function closeModals() {
    studentModal.style.display = 'none';
    viewModal.style.display = 'none';
    studentForm.reset();
}

// Handle Student Submit
async function handleStudentSubmit(e) {
    e.preventDefault();
    
    const id = document.getElementById('student-id').value;
    const studentData = {
        first_name: document.getElementById('student-first-name').value,
        last_name: document.getElementById('student-last-name').value,
        department: document.getElementById('student-department').value,
        gpa: parseFloat(document.getElementById('student-gpa').value),
        enrollment_year: parseInt(document.getElementById('student-enrollment-year').value),
        phone: document.getElementById('student-phone').value,
        address: document.getElementById('student-address').value
    };
    
    try {
        if (id) {
            // Update existing student
            await apiRequest(`/students/${id}`, {
                method: 'PUT',
                body: JSON.stringify(studentData)
            });
            showNotification('Student updated successfully!', 'success');
        } else {
            // Create new student - need user_id
            const userId = prompt('Enter User ID for this student:');
            if (!userId) {
                document.getElementById('student-form-error').textContent = 'User ID is required';
                return;
            }
            studentData.user_id = parseInt(userId);
            
            await apiRequest('/students/', {
                method: 'POST',
                body: JSON.stringify(studentData)
            });
            showNotification('Student created successfully!', 'success');
        }
        
        closeModals();
        loadStudents();
    } catch (error) {
        document.getElementById('student-form-error').textContent = error.message;
    }
}

// Delete Student
async function deleteStudent(id) {
    if (!confirm('Are you sure you want to delete this student? This action cannot be undone.')) {
        return;
    }
    
    try {
        await apiRequest(`/students/${id}`, {
            method: 'DELETE'
        });
        showNotification('Student deleted successfully!', 'success');
        loadStudents();
    } catch (error) {
        showNotification(`Error deleting student: ${error.message}`, 'error');
    }
}

// Show Notification
function showNotification(message, type) {
    const notification = document.getElementById('notification');
    const messageEl = document.getElementById('notification-message');
    
    messageEl.textContent = message;
    notification.className = `notification ${type}`;
    notification.style.display = 'block';
    
    setTimeout(() => {
        notification.style.display = 'none';
    }, 3000);
}
