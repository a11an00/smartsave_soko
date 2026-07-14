// Change this to your deployed backend URL if you host it online later!
const API_BASE_URL = "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("login-form");

  if (!loginForm) return;

  loginForm.addEventListener("submit", async (event) => {
    // Prevent page from reloading natively on submit
    event.preventDefault();

    // Target the email and password values
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const rememberMe = document.getElementById("remember-me").checked;

    // Visual feedback state for the button
    const submitBtn = loginForm.querySelector(".login-btn");
    const originalBtnText = submitBtn.innerText;
    submitBtn.disabled = true;
    submitBtn.innerText = "Signing in...";

    try {
      // Post authorization payload to FastAPI user login endpoint
      const response = await fetch(`${API_BASE_URL}/users/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email,
          password: password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        // Throw error returned from FastAPI (e.g., "Invalid email or password.")
        throw new Error(data.detail || "Authentication failed.");
      }

      // Save the JWT token securely based on "Remember Me" preference
      if (rememberMe) {
        localStorage.setItem("soko_user_token", data.access_token);
        localStorage.setItem("soko_user_id", data.user_id);
      } else {
        sessionStorage.setItem("soko_user_token", data.access_token);
        sessionStorage.setItem("soko_user_id", data.user_id);
      }

      alert("Successfully logged in! Redirecting to dashboard...");

      // Redirect to your main application interface
      window.location.href = "index.html";
    } catch (error) {
      alert(`Login Error: ${error.message}`);
    } finally {
      // Restore button state
      submitBtn.disabled = false;
      submitBtn.innerText = originalBtnText;
    }
  });
});
