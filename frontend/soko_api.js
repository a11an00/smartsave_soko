const API_BASE_URL = "http://127.0.0.1:8000";

// Retrieve current authentication token
function getToken() {
    return localStorage.getItem("soko_user_token");
}