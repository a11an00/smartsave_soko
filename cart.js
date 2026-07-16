const removeButtons = document.querySelectorAll(".remove-btn");

removeButtons.forEach(function(button){

    button.addEventListener("click", function(){

        this.parentElement.remove();

        alert("Item removed from cart.");

    });

});