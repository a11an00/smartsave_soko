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

function renderCart() {
    const cart = getCart();
    const cartItemsEl = document.getElementById("cart-items");
    const summaryEl = document.getElementById("cart-summary");
    const comparisonSection = document.getElementById("comparison-section");

    if (!cart || cart.length === 0) {
        cartItemsEl.innerHTML = "<p>Your cart is empty. Go find some deals on the homepage!</p>";
        summaryEl.style.display = "none";
        comparisonSection.style.display = "none";
        return;
    }

    cartItemsEl.innerHTML = "";

    cart.forEach((item) => {
        const row = document.createElement("div");
        row.className = "cart-item";

        const img = document.createElement("img");
        img.src = item.image_url || FALLBACK_IMAGE;
        img.alt = item.name;
        img.onerror = () => {
            img.onerror = null;
            img.src = FALLBACK_IMAGE;
        };

        const name = document.createElement("span");
        name.className = "cart-item-name";
        name.textContent = item.name;

        const qtyControls = document.createElement("div");
        qtyControls.className = "qty-controls";

        const minusBtn = document.createElement("button");
        minusBtn.textContent = "-";
        minusBtn.addEventListener("click", () => changeQuantity(item.product_id, -1));

        const qtyLabel = document.createElement("span");
        qtyLabel.textContent = item.quantity;

        const plusBtn = document.createElement("button");
        plusBtn.textContent = "+";
        plusBtn.addEventListener("click", () => changeQuantity(item.product_id, 1));

        qtyControls.appendChild(minusBtn);
        qtyControls.appendChild(qtyLabel);
        qtyControls.appendChild(plusBtn);

        const removeBtn = document.createElement("button");
        removeBtn.className = "remove-btn";
        removeBtn.textContent = "Remove";
        removeBtn.addEventListener("click", () => removeFromCart(item.product_id));

        row.appendChild(img);
        row.appendChild(name);
        row.appendChild(qtyControls);
        row.appendChild(removeBtn);
        cartItemsEl.appendChild(row);
    });

    summaryEl.style.display = "block";
}

function changeQuantity(productId, delta) {
    const cart = getCart();
    const item = cart.find((i) => i.product_id === productId);
    if (!item) return;

    item.quantity += delta;
    if (item.quantity < 1) {
        return removeFromCart(productId);
    }

    saveCart(cart);
    renderCart();
}

function removeFromCart(productId) {
    let cart = getCart();
    cart = cart.filter((i) => i.product_id !== productId);
    saveCart(cart);
    renderCart();
    document.getElementById("comparison-section").style.display = "none";
}

async function compareprices() {
    const cart = getCart();
    if (!cart || cart.length === 0) return;

    const thresholdInput = document.getElementById("threshold-input");
    const splitThreshold = parseFloat(thresholdInput.value) || 0;

    const comparisonSection = document.getElementById("comparison-section");
    const resultsEl = document.getElementById("comparison-results");

    comparisonSection.style.display = "block";
    resultsEl.innerHTML = "<p>Comparing prices across supermarkets...</p>";

    const payload = {
        items: cart.map((item) => ({
            product_id: item.product_id,
            quantity: item.quantity,
        })),
        split_threshold_kes: splitThreshold,
    };

    try {
        const response = await fetch(`${API_BASE_URL}/cart/optimize`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || "Comparison failed.");
        }

        const data = await response.json();
        renderComparison(data);
    } catch (error) {
        resultsEl.innerHTML = `<p>Error: ${error.message}</p>`;
    }
}

function renderComparison(data) {
    const resultsEl = document.getElementById("comparison-results");
    resultsEl.innerHTML = "";

    const metrics = data.arbitrage_metrics;

    const banner = document.createElement("div");
    banner.className = "recommendation-banner";

    if (data.recommendation === "SPLIT_SHOPPING_ORDER") {
        banner.innerHTML = `
            <h3>💡 Split your shopping to save KES ${metrics.potential_savings_kes.toFixed(2)}</h3>
            <p>Buying everything at one store (${metrics.recommended_single_store}) would cost
               KES ${metrics.single_store_total_kes !== null ? metrics.single_store_total_kes.toFixed(2) : "N/A"}.
               Splitting your list across stores costs KES ${metrics.optimized_split_total_kes.toFixed(2)} instead.</p>
        `;
    } else {
        banner.innerHTML = `
            <h3>🏪 Just go to ${metrics.recommended_single_store}</h3>
            <p>Total basket cost: KES ${metrics.single_store_total_kes !== null ? metrics.single_store_total_kes.toFixed(2) : "N/A"}.
               Splitting your shopping wouldn't save enough to be worth the extra trip.</p>
        `;
    }
    resultsEl.appendChild(banner);

    if (data.optimized_split_itinerary && data.optimized_split_itinerary.length > 0) {
        const itineraryTitle = document.createElement("h4");
        itineraryTitle.textContent = "Cheapest store per item:";
        resultsEl.appendChild(itineraryTitle);

        const table = document.createElement("table");
        table.className = "comparison-table";
        table.innerHTML = `
            <thead>
                <tr><th>Item</th><th>Qty</th><th>Cheapest At</th><th>Unit Price</th><th>Total</th></tr>
            </thead>
        `;
        const tbody = document.createElement("tbody");

        data.optimized_split_itinerary.forEach((entry) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${entry.name}</td>
                <td>${entry.quantity}</td>
                <td>${entry.cheapest_store}</td>
                <td>KES ${entry.unit_price.toFixed(2)}</td>
                <td>KES ${entry.total_cost.toFixed(2)}</td>
            `;
            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        resultsEl.appendChild(table);
    }

    const altTitle = document.createElement("h4");
    altTitle.textContent = "Full basket cost at each store:";
    resultsEl.appendChild(altTitle);

    Object.entries(data.single_store_alternatives).forEach(([storeName, storeData]) => {
        const storeBlock = document.createElement("details");
        storeBlock.className = "store-block";

        const cost = storeData.total_basket_cost;
        const costLabel = typeof cost === "number" ? `KES ${cost.toFixed(2)}` : cost;

        const summary = document.createElement("summary");
        summary.textContent = `${storeName} — ${costLabel}`;
        storeBlock.appendChild(summary);

        const itemList = document.createElement("ul");
        storeData.items.forEach((item) => {
            const li = document.createElement("li");
            if (item.status === "OUT_OF_STOCK") {
                li.textContent = `${item.name} (x${item.quantity}) — Out of stock`;
            } else {
                li.textContent = `${item.name} (x${item.quantity}) — KES ${item.total_cost.toFixed(2)}`;
            }
            itemList.appendChild(li);
        });
        storeBlock.appendChild(itemList);

        resultsEl.appendChild(storeBlock);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    renderCart();

    const compareBtn = document.getElementById("compare-btn");
    if (compareBtn) {
        compareBtn.addEventListener("click", compareprices);
    }
});
