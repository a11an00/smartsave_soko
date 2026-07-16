# app/schemas.py
from pydantic import BaseModel, EmailStr, Field
from typing import List

class UserAuthSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, description="Passwords must be at least 6 characters.")

class TokenSchema(BaseModel):
    access_token: str
    token_type: str
    user_id: int

class CartItemRequest(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1, description="Quantity must be 1 or greater.")

class OptimizeRequest(BaseModel):
    items: List[CartItemRequest]
    split_threshold_kes: float = Field(
        default=150.0, 
        ge=0.0, 
        description="Minimum cost savings margin required to prompt a multi-store split order."
    )

class BatchSearchRequest(BaseModel):
    product_ids: List[int] = Field(..., min_items=1, description="List of product IDs to retrieve details for.")