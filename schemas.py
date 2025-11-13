"""
Database Schemas for TRI App

Define MongoDB collection schemas using Pydantic models.
Each Pydantic model corresponds to a collection (lowercased class name).
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: Optional[str] = Field(None, description="Address")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in INR")
    category: str = Field(..., description="Product/Service category")
    in_stock: bool = Field(True, description="Whether product is in stock")
    image_url: Optional[str] = Field(None, description="Image URL")

class CartItem(BaseModel):
    product_id: str = Field(...)
    title: str = Field(...)
    quantity: int = Field(..., ge=1)
    price: float = Field(..., ge=0)

class Order(BaseModel):
    user_email: str = Field(..., description="Email of the ordering user")
    items: List[CartItem] = Field(...)
    amount: float = Field(..., ge=0, description="Total order amount")
    status: str = Field("created", description="created|paid|failed|cancelled|fulfilled")
    order_id: Optional[str] = Field(None, description="Gateway order id")
    payment_id: Optional[str] = Field(None, description="Gateway payment id")
    invoice_number: Optional[str] = Field(None, description="Sequential invoice number")

class BlogPost(BaseModel):
    title: str
    slug: str
    excerpt: Optional[str] = None
    content: str
    published: bool = True
    published_at: Optional[datetime] = None

class InvoiceSequence(BaseModel):
    last_number: int = 0
