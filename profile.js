const logoutBtn = document.querySelector(".logout-btn");

if(logoutBtn){

    logoutBtn.addEventListener("click", function(){

        let confirmLogout = confirm("Are you sure you want to logout?");

        if(confirmLogout){
            window.location.href = "login.html";
        }

    });

}