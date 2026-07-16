import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.sql import text
from passlib.context import CryptContext
import jwt

from database import SessionLocal
from app.optimiser import CartOptimiser
from app.schemas import OptimizeRequest, BatchSearchRequest, UserAuthSchema, TokenSchema

app = FastAPI(
    title="SmartSave Soko Engine",
    description=" Production API Routing Control Center."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = "change-this-to-a-long-random-secret-string"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

security_scheme = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT id, email, created_at FROM users WHERE id = :id"),
            {"id": int(user_id)}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="User no longer exists.")
        return {"id": row[0], "email": row[1], "created_at": row[2]}
    finally:
        db.close()


@app.get("/users/me", tags=["Auth"])
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user["id"],
        "email": current_user["email"],
        "member_since": current_user["created_at"].strftime("%B %Y"),
    }


@app.get("/", tags=["Root"])
async def root_welcome():
    return {
        "status": "online",
        "message": "Welcome to SmartSave Soko API Engine. Head over to /docs for interactive testing!"
    }


@app.post("/users/register", response_model=TokenSchema, tags=["Auth"])
async def register_user(payload: UserAuthSchema):
    db = SessionLocal()
    try:
        existing = db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": payload.email}
        ).fetchone()

        if existing:
            raise HTTPException(status_code=400, detail="An account with this email already exists.")

        hashed_password = pwd_context.hash(payload.password)

        result = db.execute(
            text("INSERT INTO users (email, hashed_password) VALUES (:email, :hashed_password)"),
            {"email": payload.email, "hashed_password": hashed_password}
        )
        db.commit()

        new_user_id = result.lastrowid

        access_token = create_access_token(data={"sub": str(new_user_id)})
        return {"access_token": access_token, "token_type": "bearer", "user_id": new_user_id}
    finally:
        db.close()

@app.post("/users/login", response_model=TokenSchema, tags=["Auth"])
async def login_user(payload: UserAuthSchema):
    db = SessionLocal()
    try:
        query = text("SELECT id, hashed_password FROM users WHERE email = :email")
        row = db.execute(query, {"email": payload.email}).fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        user_id, hashed_password = row[0], row[1]

        if not pwd_context.verify(payload.password, hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        access_token = create_access_token(data={"sub": str(user_id)})
        return {"access_token": access_token, "token_type": "bearer", "user_id": user_id}
    finally:
        db.close()


@app.get("/items/popular", tags=["Module 4: Search Engine"])
async def get_popular_products(limit: int = 8):
    """
    Return a random sample of products that have both a real image and
    at least one recorded price, used to populate the homepage.
    """
    db = SessionLocal()
    try:
        query = text("""
            SELECT p.product_id, p.unified_name, p.image_url, MIN(pp.price) AS min_price
            FROM products p
            JOIN product_prices pp ON p.product_id = pp.product_id
            WHERE p.image_url IS NOT NULL AND p.image_url != ''
            GROUP BY p.product_id, p.unified_name, p.image_url
            ORDER BY RAND()
            LIMIT :limit
        """)
        rows = db.execute(query, {"limit": limit}).fetchall()
        return [
            {
                "product_id": row[0],
                "product_name": row[1],
                "image_url": row[2],
                "price": float(row[3]) if row[3] is not None else None,
            }
            for row in rows
        ]
    finally:
        db.close()

CATEGORY_KEYWORDS = {
    "food-and-groceries": [
        "sugar", "dairy", "rice", "cereal", "oil", "fat", "bread", "cake",
        "pastry", "condiment", "snack", "confectionery", "flour", "maize",
        "breakfast", "baby", "butter"
    ],
    "liquor-and-beverage": [
        "spirit", "beer", "wine", "alcoholic", "juice", "carbonate",
        "soft-drink", "beverage"
    ],
}

@app.get("/items/by-category", tags=["Module 4: Search Engine"])
async def get_items_by_category(category: str, limit: int = 20):
    """
    Return products whose stored category matches any of the keyword
    group associated with the requested top-level category.
    """
    keywords = CATEGORY_KEYWORDS.get(category.lower())
    if not keywords:
        raise HTTPException(status_code=400, detail=f"Unknown category '{category}'.")

    db = SessionLocal()
    try:
        like_clauses = " OR ".join([f"p.category LIKE :kw{i}" for i in range(len(keywords))])
        params = {f"kw{i}": f"%{kw}%" for i, kw in enumerate(keywords)}
        params["limit"] = limit

        query = text(f"""
            SELECT p.product_id, p.unified_name, p.image_url, MIN(pp.price) AS min_price
            FROM products p
            JOIN product_prices pp ON p.product_id = pp.product_id
            WHERE ({like_clauses})
            GROUP BY p.product_id, p.unified_name, p.image_url
            LIMIT :limit
        """)

        rows = db.execute(query, params).fetchall()
        return [
            {
                "product_id": row[0],
                "product_name": row[1],
                "image_url": row[2],
                "price": float(row[3]) if row[3] is not None else None,
            }
            for row in rows
        ]
    finally:
        db.close()

@app.get("/items/search", tags=["Module 4: Search Engine"])
async def search_singular_item(q: str):
    """
    Search for items using a flexible, case-insensitive partial match.
    """
    clean_query = q.strip()

    if len(clean_query) < 3:
        raise HTTPException(status_code=400, detail="Search query must be 3 or more characters.")

    db = SessionLocal()
    try:
        query = text("""
            SELECT p.product_id, p.unified_name, p.image_url, MIN(pp.price) AS min_price
            FROM products p
            LEFT JOIN product_prices pp ON p.product_id = pp.product_id
            WHERE p.unified_name LIKE :search_str
            GROUP BY p.product_id, p.unified_name, p.image_url
            LIMIT 20
        """)

        rows = db.execute(query, {"search_str": f"%{clean_query}%"}).fetchall()
        return [
            {
                "product_id": row[0],
                "product_name": row[1],
                "image_url": row[2],
                "price": float(row[3]) if row[3] is not None else None,
            }
            for row in rows
        ]
    finally:
        db.close()

@app.post("/items/batch", tags=["Module 4: Search Engine"])
async def batch_search_items(payload: BatchSearchRequest):
    """
    Retrieve multiple specified items currently stored inside a user's local storage cart.
    """
    db = SessionLocal()
    try:
        query = text("""
            SELECT product_id, unified_name, image_url 
            FROM products 
            WHERE product_id IN :id_list
        """)
        rows = db.execute(query, {"id_list": tuple(payload.product_ids)}).fetchall()
        return [
            {"product_id": row[0], "product_name": row[1], "image_url": row[2]}
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation fault: {str(e)}")
    finally:
        db.close()


@app.get("/items/{product_id}", tags=["Module 4: Search Engine"])
async def get_product_details(product_id: int):
    """
    Return full details for a single product, including its lowest
    current price at each supermarket that stocks it.
    """
    db = SessionLocal()
    try:
        product_row = db.execute(
            text("""
                SELECT product_id, unified_name, image_url, category, size_value, size_unit
                FROM products
                WHERE product_id = :pid
            """),
            {"pid": product_id}
        ).fetchone()

        if not product_row:
            raise HTTPException(status_code=404, detail="Product not found.")

        price_rows = db.execute(
            text("""
                SELECT s.name AS supermarket, MIN(pp.price) AS min_price
                FROM product_prices pp
                JOIN branches b ON pp.branch_id = b.branch_id
                JOIN supermarkets s ON b.supermarket_id = s.supermarket_id
                WHERE pp.product_id = :pid
                GROUP BY s.name
                ORDER BY min_price ASC
            """),
            {"pid": product_id}
        ).fetchall()

        prices = [{"supermarket": row[0], "price": float(row[1])} for row in price_rows]

        return {
            "product_id": product_row[0],
            "product_name": product_row[1],
            "image_url": product_row[2],
            "category": product_row[3],
            "size_value": float(product_row[4]) if product_row[4] is not None else None,
            "size_unit": product_row[5],
            "prices": prices,
            "cheapest_price": prices[0]["price"] if prices else None,
            "cheapest_store": prices[0]["supermarket"] if prices else None,
        }
    finally:
        db.close()

@app.post("/cart/optimize", tags=["Module 5: Brain Solver"])
async def optimize_shopping_cart(payload: OptimizeRequest):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Shopping cart is empty.")

    try:
        items_list = [item.model_dump() for item in payload.items]
        engine = CartOptimiser(cart_items=items_list)
        results = engine.compute(threshold_buffer_kes=payload.split_threshold_kes)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Engine runtime exception: {str(e)}")