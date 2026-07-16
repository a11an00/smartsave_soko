const API_BASE_URL = "http://127.0.0.1:8000";
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
    alert(`${product.product_name} added to cart!`);
}

function getProductIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const id = params.get("id");
    return id ? parseInt(id, 10) : null;
}

async function loadProductDetails() {
    const container = document.getElementById("product-details-section");
    const productId = getProductIdFromUrl();

    if (!productId) {
        container.innerHTML = "<p>No product specified.</p>";
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/items/${productId}`);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || "Product not found.");
        }

        const product = await response.json();
        renderProduct(product);
    } catch (error) {
        container.innerHTML = `<p>Error: ${error.message}</p>`;
    }
}

function renderProduct(product) {
    const container = document.getElementById("product-details-section");
    container.innerHTML = "";

    const wrapper = document.createElement("div");
    wrapper.className = "product-details-wrapper";

    const img = document.createElement("img");
    img.src = product.image_url || FALLBACK_IMAGE;
    img.alt = product.product_name;
    img.className = "product-details-img";
    img.onerror = () => {
        img.onerror = null;
        img.src = FALLBACK_IMAGE;
    };

    const info = document.createElement("div");
    info.className = "product-details-info";

    const title = document.createElement("h1");
    title.textContent = product.product_name;

    const meta = document.createElement("p");
    meta.className = "product-meta";
    const sizeText = product.size_value ? `${product.size_value}${product.size_unit || ""}` : null;
    const categoryText = product.category ? product.category.replace(/-/g, " ").replace(/\//g, " / ") : null;
    meta.textContent = [sizeText, categoryText].filter(Boolean).join(" · ") || "No additional details available.";

    const priceHeading = document.createElement("h3");
    priceHeading.textContent = "Prices by store:";

    const priceTable = document.createElement("table");
    priceTable.className = "product-price-table";

    if (product.prices && product.prices.length > 0) {
        priceTable.innerHTML = "<thead><tr><th>Store</th><th>Price</th></tr></thead>";
        const tbody = document.createElement("tbody");

        product.prices.forEach((entry) => {
            const tr = document.createElement("tr");
            if (entry.supermarket === product.cheapest_store) {
                tr.className = "cheapest-row";
            }
            tr.innerHTML = `<td>${entry.supermarket}${entry.supermarket === product.cheapest_store ? " (Cheapest)" : ""}</td><td>KES ${entry.price.toFixed(2)}</td>`;
            tbody.appendChild(tr);
        });

        priceTable.appendChild(tbody);
    } else {
        priceTable.innerHTML = "<tbody><tr><td>No price data available yet.</td></tr></tbody>";
    }

    const addBtn = document.createElement("button");
    addBtn.className = "add-to-cart-btn";
    addBtn.textContent = "Add to Cart";
    addBtn.addEventListener("click", () => addToCart(product));

    info.appendChild(title);
    info.appendChild(meta);
    info.appendChild(priceHeading);
    info.appendChild(priceTable);
    info.appendChild(addBtn);

    wrapper.appendChild(img);
    wrapper.appendChild(info);
    container.appendChild(wrapper);
}

document.addEventListener("DOMContentLoaded", loadProductDetails);
