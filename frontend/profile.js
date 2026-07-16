const API_BASE_URL = "http://127.0.0.1:8000";

function getStoredToken() {
    return localStorage.getItem("soko_user_token") || sessionStorage.getItem("soko_user_token");
}

function clearStoredToken() {
    localStorage.removeItem("soko_user_token");
    localStorage.removeItem("soko_user_id");
    sessionStorage.removeItem("soko_user_token");
    sessionStorage.removeItem("soko_user_id");
}

document.addEventListener("DOMContentLoaded", async () => {
    const token = getStoredToken();

    if (!token) {
        alert("Please log in to view your profile.");
        window.location.href = "login.html";
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/users/me`, {
            headers: {
                "Authorization": `Bearer ${token}`,
            },
        });

        if (!response.ok) {
            // Token invalid or expired - clear it and send back to login
            clearStoredToken();
            alert("Your session has expired. Please log in again.");
            window.location.href = "login.html";
            return;
        }

        const data = await response.json();

        document.getElementById("profile-welcome").textContent = `Welcome back, ${data.email}!`;
        document.getElementById("profile-email").textContent = data.email;
        document.getElementById("profile-member-since").textContent = `Member since ${data.member_since}`;
    } catch (error) {
        console.error("Failed to load profile:", error);
    }

    const logoutBtn = document.querySelector(".logout");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", function () {
            const confirmLogout = confirm("Are you sure you want to logout?");
            if (confirmLogout) {
                clearStoredToken();
                window.location.href = "login.html";
            }
        });
    }
});
