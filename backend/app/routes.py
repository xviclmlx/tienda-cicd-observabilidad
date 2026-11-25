from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from . import schemas
from .db import get_db
from .models import Category, Order, OrderItem, Product, User
from .security import admin_user, create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api")


def _get_or_404(db: Session, model, obj_id: int, label: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} no encontrado")
    return obj


def _commit(db: Session, conflict_msg: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, conflict_msg)


# ---------- Auth ----------
@router.post("/auth/login", response_model=schemas.TokenOut, tags=["auth"])
def login(data: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas")
    return {"access_token": create_token(user)}


@router.get("/auth/me", response_model=schemas.UserOut, tags=["auth"])
def me(user: User = Depends(current_user)):
    return user


# ---------- Usuarios (solo admin) ----------
@router.get("/users", response_model=list[schemas.UserOut], tags=["users"])
def list_users(db: Session = Depends(get_db), _=Depends(admin_user)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.get("/users/{user_id}", response_model=schemas.UserOut, tags=["users"])
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    return _get_or_404(db, User, user_id, "Usuario")


@router.post("/users", response_model=schemas.UserOut, status_code=201, tags=["users"])
def create_user(data: schemas.UserIn, db: Session = Depends(get_db), _=Depends(admin_user)):
    user = User(name=data.name, email=data.email, role=data.role,
                password_hash=hash_password(data.password))
    db.add(user)
    _commit(db, "El correo ya está registrado")
    return user


@router.put("/users/{user_id}", response_model=schemas.UserOut, tags=["users"])
def update_user(user_id: int, data: schemas.UserUpdate, db: Session = Depends(get_db),
                _=Depends(admin_user)):
    user = _get_or_404(db, User, user_id, "Usuario")
    changes = data.model_dump(exclude_unset=True)
    if "password" in changes:
        user.password_hash = hash_password(changes.pop("password"))
    for k, v in changes.items():
        setattr(user, k, v)
    _commit(db, "El correo ya está registrado")
    return user


@router.delete("/users/{user_id}", status_code=204, tags=["users"])
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    user = _get_or_404(db, User, user_id, "Usuario")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes eliminarte a ti mismo")
    db.delete(user)
    db.commit()
    return Response(status_code=204)


# ---------- Categorías ----------
@router.get("/categories", response_model=list[schemas.CategoryOut], tags=["categories"])
def list_categories(db: Session = Depends(get_db), _=Depends(current_user)):
    return db.scalars(select(Category).order_by(Category.id)).all()


@router.get("/categories/{cat_id}", response_model=schemas.CategoryOut, tags=["categories"])
def get_category(cat_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    return _get_or_404(db, Category, cat_id, "Categoría")


@router.post("/categories", response_model=schemas.CategoryOut, status_code=201, tags=["categories"])
def create_category(data: schemas.CategoryIn, db: Session = Depends(get_db), _=Depends(admin_user)):
    cat = Category(**data.model_dump())
    db.add(cat)
    _commit(db, "La categoría ya existe")
    return cat


@router.put("/categories/{cat_id}", response_model=schemas.CategoryOut, tags=["categories"])
def update_category(cat_id: int, data: schemas.CategoryIn, db: Session = Depends(get_db),
                    _=Depends(admin_user)):
    cat = _get_or_404(db, Category, cat_id, "Categoría")
    for k, v in data.model_dump().items():
        setattr(cat, k, v)
    _commit(db, "La categoría ya existe")
    return cat


@router.delete("/categories/{cat_id}", status_code=204, tags=["categories"])
def delete_category(cat_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    cat = _get_or_404(db, Category, cat_id, "Categoría")
    if cat.products:
        raise HTTPException(status.HTTP_409_CONFLICT, "La categoría tiene productos")
    db.delete(cat)
    db.commit()
    return Response(status_code=204)


# ---------- Productos ----------
@router.get("/products", response_model=list[schemas.ProductOut], tags=["products"])
def list_products(category_id: int | None = None, db: Session = Depends(get_db),
                  _=Depends(current_user)):
    q = select(Product).order_by(Product.id)
    if category_id is not None:
        q = q.where(Product.category_id == category_id)
    return db.scalars(q).all()


@router.get("/products/{prod_id}", response_model=schemas.ProductOut, tags=["products"])
def get_product(prod_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    return _get_or_404(db, Product, prod_id, "Producto")


@router.post("/products", response_model=schemas.ProductOut, status_code=201, tags=["products"])
def create_product(data: schemas.ProductIn, db: Session = Depends(get_db), _=Depends(admin_user)):
    _get_or_404(db, Category, data.category_id, "Categoría")
    prod = Product(**data.model_dump())
    db.add(prod)
    db.commit()
    return prod


@router.put("/products/{prod_id}", response_model=schemas.ProductOut, tags=["products"])
def update_product(prod_id: int, data: schemas.ProductIn, db: Session = Depends(get_db),
                   _=Depends(admin_user)):
    prod = _get_or_404(db, Product, prod_id, "Producto")
    _get_or_404(db, Category, data.category_id, "Categoría")
    for k, v in data.model_dump().items():
        setattr(prod, k, v)
    db.commit()
    return prod


@router.delete("/products/{prod_id}", status_code=204, tags=["products"])
def delete_product(prod_id: int, db: Session = Depends(get_db), _=Depends(admin_user)):
    prod = _get_or_404(db, Product, prod_id, "Producto")
    db.delete(prod)
    db.commit()
    return Response(status_code=204)


# ---------- Pedidos (GET, POST) ----------
@router.get("/orders", response_model=list[schemas.OrderOut], tags=["orders"])
def list_orders(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Order).options(selectinload(Order.items)).order_by(Order.id.desc())
    if user.role != "admin":
        q = q.where(Order.user_id == user.id)
    return db.scalars(q).all()


@router.get("/orders/{order_id}", response_model=schemas.OrderOut, tags=["orders"])
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    order = _get_or_404(db, Order, order_id, "Pedido")
    if user.role != "admin" and order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido no encontrado")
    return order


@router.post("/orders", response_model=schemas.OrderOut, status_code=201, tags=["orders"])
def create_order(data: schemas.OrderIn, db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    order = Order(user_id=user.id, total=0)
    total = 0.0
    for item in data.items:
        prod = _get_or_404(db, Product, item.product_id, f"Producto {item.product_id}")
        if prod.stock < item.quantity:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, f"Stock insuficiente para {prod.name}")
        prod.stock -= item.quantity
        price = float(prod.price)
        total += price * item.quantity
        order.items.append(OrderItem(product_id=prod.id, quantity=item.quantity, unit_price=price))
    order.total = round(total * 2, 2)
    db.add(order)
    db.commit()
    return order
