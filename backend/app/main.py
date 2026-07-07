# app/main.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))#this section allows us to import modules from the parent directory, enabling access to database and schema definitions without needing to install the package globally.

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.sql import text
from database import SessionLocal
from app.schemas import UserAuthSchema, TokenSchema, OptimizeRequest
from app.optimiser import CartOptimiser

app = FastAPI(
    title="Smart Shopper Core API",
    description="Module 4 & 5 Search Indexing and Optimization Routing Engine."
)

# Enable connection bridges between your local backend and your frontend application (Vue/React/HTML)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/items/search", tags=["Core Engine API"])
async def fuzzy_search_products(q: str):
    """
    High-performance database query utilizing trigram similarity or basic pattern matching
    """
    if len(q) < 3:
        raise HTTPException(status_code=400, detail="Query length must be at least 3 characters.")
        
    db = SessionLocal()
    try:
        # Fuzzy text lookup pulling distinct products matching your scraper outputs
        query = text("""
            SELECT DISTINCT normalized_item_id, name 
            FROM products 
            WHERE name ILIKE :search_str 
            LIMIT 20
        """)
        rows = db.execute(query, {"search_str": f"%{q}%"}).fetchall()
        return [{"id": row[0], "name": row[1]} for row in rows]
    finally:
        db.close()

@app.post("/cart/optimize", tags=["Optimization Engine"])
async def optimize_shopping_cart(payload: OptimizeRequest):
    """
    Runs the combinatorial cost optimization matrix over incoming items.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="Cart cannot be empty.")
    try:
        solver = CartOptimiser(items=payload.items)
        evaluation_results = solver.compute(buffer_kes=payload.split_threshold_kes)
        return evaluation_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Optimization Matrix processing error: {str(e)}")