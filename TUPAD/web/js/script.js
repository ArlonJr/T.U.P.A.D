// Global variables
let users = [];
let attendanceRecords = [];
let currentPage = 'dashboard';
let apiBaseUrl = '';  // Set to your ESP32 IP or domain

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    // Set today's date in attendance filter
    const today = new Date();
    const dateString = today.toISOString().split('T')[0];
    document.getElementById('attendance-date').value = dateString;
    
    // Add event listeners to navigation links
    const navLinks = document.querySelectorAll('nav a');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Change active page
            const targetPage = this.getAttribute('data-page');
            changePage(targetPage);
            
            // If this is the users or attendance page, load the data
            if (targetPage === 'users') {
                loadUsers();
            } else if (targetPage === 'attendance') {
                loadAttendance();
            } else if (targetPage === 'dashboard') {
                loadDashboard();
            }
        });
    });
    
    // Add event listeners to form inputs
    document.getElementById('user-search').addEventListener('input', filterUsers);
    document.getElementById('user-filter').addEventListener('change', filterUsers);
    document.getElementById('attendance-date').addEventListener('change', loadAttendance);
    document.getElementById('attendance-filter').addEventListener('change', filterAttendance);
    
    // Add event listeners to buttons
    document.getElementById('capture-btn').addEventListener('click', captureFace);
    document.getElementById('register-btn').addEventListener('click', registerUser);
    document.getElementById('save-settings-btn').addEventListener('click', saveSettings);
    document.getElementById('reset-system-btn').addEventListener('click', resetSystem);
    
    // Load initial dashboard data
    loadDashboard();
});

// Change the active page
function changePage(pageName) {
    // Update current page
    currentPage = pageName;
    
    // Hide all pages
    const pages = document.querySelectorAll('.page');
    pages.forEach(page => {
        page.classList.remove('active');
    });
    
    // Show the selected page
    document.getElementById(pageName).classList.add('active');
    
    // Update navigation
    const navLinks = document.querySelectorAll('nav a');
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('data-page') === pageName) {
            link.classList.add('active');
        }
    });
}

// Load dashboard data
function loadDashboard() {
    // Fetch users data
    fetch(`${apiBaseUrl}/api/users`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch users');
            }
            return response.json();
        })
        .then(data => {
            users = data;
            
            // Update user stats
            let totalUsers = users.length;
            let droppedUsers = users.filter(user => user.isDropped).length;
            
            document.getElementById('total-users').textContent = totalUsers;
            document.getElementById('dropped-count').textContent = droppedUsers;
            
            // Fetch attendance data
            return fetch(`${apiBaseUrl}/api/attendance`);
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch attendance');
            }
            return response.json();
        })
        .then(data => {
            attendanceRecords = data;
            
            // Get today's attendance
            const today = new Date();
            const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime() / 1000;
            const endOfDay = startOfDay + 86400; // Add 24 hours in seconds
            
            const todayRecords = attendanceRecords.filter(record => {
                return record.timestamp >= startOfDay && record.timestamp < endOfDay;
            });
            
            // Count by status
            let presentCount = todayRecords.filter(record => record.status === 'present').length;
            let lateCount = todayRecords.filter(record => record.status === 'late').length;
            let absentCount = todayRecords.filter(record => record.status === 'absent').length;
            
            document.getElementById('present-count').textContent = presentCount;
            document.getElementById('late-count').textContent = lateCount;
            document.getElementById('absent-count').textContent = absentCount;
            
            // Update recent activity
            updateRecentActivity(todayRecords);
        })
        .catch(error => {
            console.error('Error loading dashboard data:', error);
        });
}

// Update recent activity table
function updateRecentActivity(records) {
    const activityTable = document.querySelector('#activity-table tbody');
    activityTable.innerHTML = '';
    
    // Sort records by timestamp (newest first)
    records.sort((a, b) => b.timestamp - a.timestamp);
    
    // Take only the most recent 10 records
    const recentRecords = records.slice(0, 10);
    
    // Create table rows
    recentRecords.forEach(record => {
        const row = document.createElement('tr');
        
        // Create time cell
        const timeCell = document.createElement('td');
        const date = new Date(record.timestamp * 1000);
        timeCell.textContent = date.toLocaleTimeString();
        row.appendChild(timeCell);
        
        // Create user cell
        const userCell = document.createElement('td');
        userCell.textContent = record.name || record.userId;
        row.appendChild(userCell);
        
        // Create status cell
        const statusCell = document.createElement('td');
        statusCell.textContent = record.status.charAt(0).toUpperCase() + record.status.slice(1);
        
        // Add status class
        statusCell.classList.add(record.status);
        
        row.appendChild(statusCell);
        
        // Add row to table
        activityTable.appendChild(row);
    });
    
    // If no records, show a message
    if (recentRecords.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 3;
        cell.textContent = 'No activity today';
        cell.style.textAlign = 'center';
        row.appendChild(cell);
        activityTable.appendChild(row);
    }
}

// Load users data
function loadUsers() {
    fetch(`${apiBaseUrl}/api/users`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch users');
            }
            return response.json();
        })
        .then(data => {
            users = data;
            displayUsers(users);
        })
        .catch(error => {
            console.error('Error loading users:', error);
        });
}

// Display users in the table
function displayUsers(usersToDisplay) {
    const usersTable = document.querySelector('#users-table tbody');
    usersTable.innerHTML = '';
    
    usersToDisplay.forEach(user => {
        const row = document.createElement('tr');
        
        // Create ID cell
        const idCell = document.createElement('td');
        idCell.textContent = user.id;
        row.appendChild(idCell);
        
        // Create name cell
        const nameCell = document.createElement('td');
        nameCell.textContent = user.name;
        row.appendChild(nameCell);
        
        // Create absences cell
        const absencesCell = document.createElement('td');
        absencesCell.textContent = user.absenceCount;
        row.appendChild(absencesCell);
        
        // Create status cell
        const statusCell = document.createElement('td');
        statusCell.textContent = user.isDropped ? 'Dropped' : 'Active';
        statusCell.classList.add(user.isDropped ? 'dropped' : 'active');
        row.appendChild(statusCell);
        
        // Create actions cell
        const actionsCell = document.createElement('td');
        
        // Create delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = 'Delete';
        deleteBtn.classList.add('danger');
        deleteBtn.addEventListener('click', () => deleteUser(user.id));
        
        // Create reset button (only for dropped users)
        const resetBtn = document.createElement('button');
        resetBtn.textContent = 'Reset';
        resetBtn.addEventListener('click', () => resetUserAbsences(user.id));
        
        if (user.isDropped) {
            actionsCell.appendChild(resetBtn);
        }
        
        actionsCell.appendChild(deleteBtn);
        row.appendChild(actionsCell);
        
        // Add row to table
        usersTable.appendChild(row);
    });
    
    // If no users, show a message
    if (usersToDisplay.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 5;
        cell.textContent = 'No users found';
        cell.style.textAlign = 'center';
        row.appendChild(cell);
        usersTable.appendChild(row);
    }
}

// Filter users based on search and filter
function filterUsers() {
    const searchText = document.getElementById('user-search').value.toLowerCase();
    const filterValue = document.getElementById('user-filter').value;
    
    let filteredUsers = users;
    
    // Apply text search
    if (searchText) {
        filteredUsers = filteredUsers.filter(user => {
            return (
                user.id.toLowerCase().includes(searchText) ||
                user.name.toLowerCase().includes(searchText)
            );
        });
    }
    
    // Apply status filter
    if (filterValue === 'active') {
        filteredUsers = filteredUsers.filter(user => !user.isDropped);
    } else if (filterValue === 'dropped') {
        filteredUsers = filteredUsers.filter(user => user.isDropped);
    }
    
    // Display filtered users
    displayUsers(filteredUsers);
}

// Delete a user
function deleteUser(userId) {
    if (confirm(`Are you sure you want to delete user ${userId}?`)) {
        fetch(`${apiBaseUrl}/api/users/${userId}`, {
            method: 'DELETE'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to delete user');
            }
            return response.json();
        })
        .then(data => {
            // Reload users
            loadUsers();
        })
        .catch(error => {
            console.error('Error deleting user:', error);
            alert('Failed to delete user. Please try again.');
        });
    }
}

// Reset a user's absence count
function resetUserAbsences(userId) {
    if (confirm(`Are you sure you want to reset absences for user ${userId}?`)) {
        fetch(`${apiBaseUrl}/api/users/${userId}/reset`, {
            method: 'POST'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to reset user absences');
            }
            return response.json();
        })
        .then(data => {
            // Reload users
            loadUsers();
        })
        .catch(error => {
            console.error('Error resetting user absences:', error);
            alert('Failed to reset user absences. Please try again.');
        });
    }
}

// Load attendance data
function loadAttendance() {
    const dateFilter = document.getElementById('attendance-date').value;
    
    fetch(`${apiBaseUrl}/api/attendance`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch attendance');
            }
            return response.json();
        })
        .then(data => {
            attendanceRecords = data;
            
            // Filter by date
            if (dateFilter) {
                const filterDate = new Date(dateFilter);
                const startOfDay = new Date(filterDate.getFullYear(), filterDate.getMonth(), filterDate.getDate()).getTime() / 1000;
                const endOfDay = startOfDay + 86400; // Add 24 hours in seconds
                
                attendanceRecords = attendanceRecords.filter(record => {
                    return record.timestamp >= startOfDay && record.timestamp < endOfDay;
                });
            }
            
            displayAttendance(attendanceRecords);
        })
        .catch(error => {
            console.error('Error loading attendance:', error);
        });
}

// Display attendance records in the table
function displayAttendance(recordsToDisplay) {
    const attendanceTable = document.querySelector('#attendance-table tbody');
    attendanceTable.innerHTML = '';
    
    // Sort records by timestamp (newest first)
    recordsToDisplay.sort((a, b) => b.timestamp - a.timestamp);
    
    recordsToDisplay.forEach(record => {
        const row = document.createElement('tr');
        
        // Create time cell
        const timeCell = document.createElement('td');
        const date = new Date(record.timestamp * 1000);
        timeCell.textContent = date.toLocaleTimeString();
        row.appendChild(timeCell);
        
        // Create user ID cell
        const userIdCell = document.createElement('td');
        userIdCell.textContent = record.userId;
        row.appendChild(userIdCell);
        
        // Create name cell
        const nameCell = document.createElement('td');
        nameCell.textContent = record.name || 'Unknown';
        row.appendChild(nameCell);
        
        // Create status cell
        const statusCell = document.createElement('td');
        statusCell.textContent = record.status.charAt(0).toUpperCase() + record.status.slice(1);
        statusCell.classList.add(record.status);
        row.appendChild(statusCell);
        
        // Add row to table
        attendanceTable.appendChild(row);
    });
    
    // If no records, show a message
    if (recordsToDisplay.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 4;
        cell.textContent = 'No attendance records found for the selected date';
        cell.style.textAlign = 'center';
        row.appendChild(cell);
        attendanceTable.appendChild(row);
    }
}

// Filter attendance based on status
function filterAttendance() {
    const filterValue = document.getElementById('attendance-filter').value;
    
    let filteredRecords = attendanceRecords;
    
    // Apply status filter
    if (filterValue !== 'all') {
        filteredRecords = filteredRecords.filter(record => record.status === filterValue);
    }
    
    // Display filtered records
    displayAttendance(filteredRecords);
}

// Capture face for user registration
function captureFace() {
    const userId = document.getElementById('user-id').value.trim();
    
    if (!userId) {
        alert('Please enter a user ID first');
        return;
    }
    
    // Show capturing status
    document.getElementById('camera-status').textContent = 'Capturing face... Please look at the camera.';
    
    // Request face capture from ESP32
    fetch(`${apiBaseUrl}/api/capture-face`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ userId })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to capture face');
        }
        return response.json();
    })
    .then(data => {
        // Update camera status
        document.getElementById('camera-status').textContent = 'Face captured successfully. You can now register the user.';
        
        // Enable register button
        document.getElementById('register-btn').disabled = false;
    })
    .catch(error => {
        console.error('Error capturing face:', error);
        document.getElementById('camera-status').textContent = 'Failed to capture face. Please try again.';
    });
}

// Register a new user
function registerUser() {
    const userId = document.getElementById('user-id').value.trim();
    const userName = document.getElementById('user-name').value.trim();
    
    // Validate inputs
    if (!userId) {
        alert('Please enter a user ID');
        return;
    }
    
    if (!userName) {
        alert('Please enter a name');
        return;
    }
    
    // Register user
    fetch(`${apiBaseUrl}/api/users`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ id: userId, name: userName })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to register user');
        }
        return response.json();
    })
    .then(data => {
        // Show success message
        const messageDiv = document.getElementById('registration-message');
        messageDiv.textContent = `User ${userName} registered successfully!`;
        messageDiv.className = 'success';
        
        // Reset form
        document.getElementById('user-id').value = '';
        document.getElementById('user-name').value = '';
        document.getElementById('camera-status').textContent = 'Camera feed not available';
        document.getElementById('register-btn').disabled = true;
        document.getElementById('capture-btn').disabled = true;
        
        // Reload users data in case users page is viewed next
        loadUsers();
    })
    .catch(error => {
        console.error('Error registering user:', error);
        
        // Show error message
        const messageDiv = document.getElementById('registration-message');
        messageDiv.textContent = 'Failed to register user. Please try again.';
        messageDiv.className = 'error';
    });
}

// Save system settings
function saveSettings() {
    const attendanceStart = document.getElementById('attendance-start').value;
    const lateThreshold = document.getElementById('late-threshold').value;
    const absentThreshold = document.getElementById('absent-threshold').value;
    const maxAbsences = document.getElementById('max-absences').value;
    
    // Validate inputs
    if (!attendanceStart || !lateThreshold || !absentThreshold || !maxAbsences) {
        alert('Please fill all fields');
        return;
    }
    
    // Parse attendance start time
    const [hours, minutes] = attendanceStart.split(':');
    
    // Prepare settings object
    const settings = {
        attendanceStartHour: parseInt(hours),
        attendanceStartMinute: parseInt(minutes),
        lateThresholdMinutes: parseInt(lateThreshold),
        absentThresholdMinutes: parseInt(absentThreshold),
        maxAbsencesBeforeDrop: parseInt(maxAbsences)
    };
    
    // Save settings
    fetch(`${apiBaseUrl}/api/settings`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to save settings');
        }
        return response.json();
    })
    .then(data => {
        alert('Settings saved successfully');
    })
    .catch(error => {
        console.error('Error saving settings:', error);
        alert('Failed to save settings. Please try again.');
    });
}

// Reset the system
function resetSystem() {
    if (confirm('Are you sure you want to reset the entire system? This will delete all users and attendance records.')) {
        fetch(`${apiBaseUrl}/api/reset`, {
            method: 'POST'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to reset system');
            }
            return response.json();
        })
        .then(data => {
            alert('System reset successfully');
            
            // Reload dashboard
            loadDashboard();
        })
        .catch(error => {
            console.error('Error resetting system:', error);
            alert('Failed to reset system. Please try again.');
        });
    }
} 