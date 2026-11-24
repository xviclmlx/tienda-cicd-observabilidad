from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6)
    role: str = Field(default="user", pattern="^(user|admin)$")


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6)
    role: str | None = Field(default=None, pattern="^(user|admin)$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    role: str
    created_at: datetime


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""


class CategoryOut(CategoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)
    category_id: int


class ProductOut(ProductIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    quantity: int
    unit_price: float


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    total: float
    created_at: datetime
    items: list[OrderItemOut]
