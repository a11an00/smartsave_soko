import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.sql import text
from database import SessionLocal
from app.optimiser import CartOptimiser
from app.schemas import OptimizeRequest, BatchSearchRequest

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

@app.get("/", tags=["Root"])
async def root_welcome():
    return {
        "status": "online",
        "message": "Welcome to SmartSave Soko API Engine. Head over to /docs for interactive testing!"
    }

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
        # Removed BINARY so 'sugar' matches 'Kabras Sugar 2KG'
        query = text("""
            SELECT DISTINCT product_id, unified_name 
            FROM products 
            WHERE unified_name LIKE :search_str 
            LIMIT 20
        """)
        
        rows = db.execute(query, {"search_str": f"%{clean_query}%"}).fetchall()
        return [{"product_id": row[0], "product_name": row[1]} for row in rows]
    finally:
        db.close()


@app.post("/items/batch", tags=["Module 4: Search Engine"])
async def batch_search_items(payload: BatchSearchRequest):
    """
    Retrieve multiple specified items currently stored inside a user's local storage cart.
    """
    db = SessionLocal()
    try:
        # FIXED: Changed selected string field name to 'unified_name'
        query = text("""
            SELECT product_id, unified_name 
            FROM products 
            WHERE product_id IN :id_list
        """)
        rows = db.execute(query, {"id_list": tuple(payload.product_ids)}).fetchall()
        return [{"product_id": row[0], "product_name": row[1]} for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation fault: {str(e)}")
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