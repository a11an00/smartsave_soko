const API_BASE_URL = "http://127.0.0.1:8000";

// Fallback image shown when a product has no image_url yet
const FALLBACK_IMAGE = "images/no-image-placeholder.svg";

const CART_STORAGE_KEY = "soko_cart";

function getCart() {
    try {
        const raw = localStorage.getItem(CART_STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch (e) {
        return [];
    }
}

function saveCart(cart) {
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart));
}

function addToCart(product) {
    const cart = getCart();
    const existing = cart.find((item) => item.product_id === product.product_id);

    if (existing) {
        existing.quantity += 1;
    } else {
        cart.push({
            product_id: product.product_id,
            name: product.product_name,
            image_url: product.image_url || null,
            quantity: 1,
        });
    }

    saveCart(cart);
    alert(product.product_name + " added to cart!");
}

function buildProductCard(product) {
    const card = document.createElement("div");
    card.className = "product-card";
    card.style.cursor = "pointer";

    const img = document.createElement("img");
    img.src = product.image_url || FALLBACK_IMAGE;
    img.alt = product.product_name;
    img.onerror = () => {
        img.onerror = null;
        img.src = FALLBACK_IMAGE;
    };

    const title = document.createElement("h3");
    title.textContent = product.product_name;

    const price = document.createElement("p");
    price.textContent =
        product.price !== null && product.price !== undefined
            ? "KES " + Number(product.price).toFixed(2)
            : "Price unavailable";

    const addBtn = document.createElement("button");
    addBtn.textContent = "Add to Cart";
    addBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        addToCart(product);
    });

    card.addEventListener("click", () => {
        window.location.href = "product.html?id=" + product.product_id;
    });

    card.appendChild(img);
    card.appendChild(title);
    card.appendChild(price);
    card.appendChild(addBtn);
    return card;
}

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

async function loadPopularProducts() {
    const grid = document.getElementById("popular-products-grid");
    if (!grid) return;

    try {
        const response = await fetch(API_BASE_URL + "/items/popular?limit=8");
        if (!response.ok) throw new Error("Failed to load popular products.");

        const products = await response.json();
        grid.innerHTML = "";

        if (!products || products.length === 0) {
            grid.innerHTML = "<p>No products available right now.</p>";
            return;
        }

        products.forEach((product) => {
            grid.appendChild(buildProductCard(product));
        });
    } catch (error) {
        grid.innerHTML = "<p>Error loading products: " + error.message + "</p>";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadPopularProducts();

    const categoryButtons = document.querySelectorAll(".category-btn");
    categoryButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            const category = btn.getAttribute("data-category");
            runCategorySearch(category, btn.textContent);
        });
    });

    async function runCategorySearch(category, label) {
        const resultsSection = document.getElementById("search-results-section");
        const resultsGrid = document.getElementById("search-results-grid");
        const popularSection = document.getElementById("popular-products-section");

        resultsGrid.innerHTML = "<p>Loading " + label + "...</p>";
        resultsSection.style.display = "block";
        if (popularSection) popularSection.style.display = "none";

        try {
            const response = await fetch(
                API_BASE_URL + "/items/by-category?category=" + encodeURIComponent(category) + "&limit=20"
            );

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to load category.");
            }

            const products = await response.json();

            if (!products || products.length === 0) {
                resultsGrid.innerHTML = "<p>No products found in " + label + " yet.</p>";
                return;
            }

            resultsGrid.innerHTML = "";
            products.forEach((product) => {
                resultsGrid.appendChild(buildProductCard(product));
            });
        } catch (error) {
            resultsGrid.innerHTML = "<p>Error: " + error.message + "</p>";
        }
    }

    const searchInput = document.getElementById("search-input");
    const searchBtn = document.getElementById("search-btn");
    const resultsSection = document.getElementById("search-results-section");
    const resultsGrid = document.getElementById("search-results-grid");
    const popularSection = document.getElementById("popular-products-section");

    if (!searchInput || !searchBtn || !resultsSection || !resultsGrid) return;

    async function runSearch() {
        const query = searchInput.value.trim();

        if (query.length < 3) {
            alert("Please enter at least 3 characters to search.");
            return;
        }

        resultsGrid.innerHTML = "<p>Searching...</p>";
        resultsSection.style.display = "block";
        if (popularSection) popularSection.style.display = "none";

        try {
            const response = await fetch(
                API_BASE_URL + "/items/search?q=" + encodeURIComponent(query)
            );

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Search failed.");
            }

            const products = await response.json();
            renderResults(products);
        } catch (error) {
            resultsGrid.innerHTML = "<p>Error: " + error.message + "</p>";
        }
    }

    function renderResults(products) {
        if (!products || products.length === 0) {
            resultsGrid.innerHTML = "<p>No products found.</p>";
            return;
        }

        resultsGrid.innerHTML = "";
        products.forEach((product) => {
            resultsGrid.appendChild(buildProductCard(product));
        });
    }

    searchBtn.addEventListener("click", (e) => {
        e.preventDefault();
        runSearch();
    });

    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            runSearch();
        }
    });
});
