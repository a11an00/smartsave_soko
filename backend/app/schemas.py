# app/schemas.py
from pydantic import BaseModel, EmailStr, Field
from typing import List

class UserAuthSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, description="Passwords must be at least 6 characters.")

class TokenSchema(BaseModel):
    access_token: str
    token_type: str

class CartItemRequest(BaseModel):
    normalized_item_id: int
    quantity: int = Field(default=1, ge=1)

class OptimizeRequest(BaseModel):
    items: List[CartItemRequest]
    split_threshold_kes: float = Field(default=150.0, ge=0.0, description="Minimum cost savings margin required to prompt a multi-store split split.")