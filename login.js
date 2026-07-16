const loginForm = document.querySelector("form");

if(loginForm){

    loginForm.addEventListener("submit", function(event){

        event.preventDefault();

        let email = document.querySelector('input[type="email"]').value;
        let password = document.querySelector('input[type="password"]').value;

        if(email === "" || password === ""){

            alert("Please fill in all fields.");

        }else{

            alert("Login Successful!");

            window.location.href = "index.html";

        }

    });

}