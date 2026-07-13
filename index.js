const slides = document.querySelectorAll(".slide");

let currentSlide = 0;

function nextSlide(){

    slides[currentSlide].classList.remove("active");

    currentSlide++;

    if(currentSlide >= slides.length){
        currentSlide = 0;
    }

    slides[currentSlide].classList.add("active");

}

setInterval(nextSlide, 4000);
const cartButtons = document.querySelectorAll(".product-card button");

cartButtons.forEach(function(button){

    button.addEventListener("click", function(){

        alert("Product added to cart!");

    });

});