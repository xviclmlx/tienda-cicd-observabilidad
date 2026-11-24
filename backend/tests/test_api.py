"""Pruebas de cada endpoint del backend (RF-01)."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------- Auth ----------
def test_login_ok(client):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "Admin123!"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


def test_login_bad_password(client):
    r = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "nope"})
    assert r.status_code == 401


def test_me(client, admin_headers):
    r = client.get("/api/auth/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_requires_token(client):
    assert client.get("/api/products").status_code == 401


def test_invalid_token(client):
    r = client.get("/api/products", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


# ---------- Usuarios ----------
def test_users_crud(client, admin_headers):
    r = client.post("/api/users", headers=admin_headers, json={
        "name": "Ana", "email": "ana@test.com", "password": "secreto1"})
    assert r.status_code == 201
    uid = r.json()["id"]
    assert "password" not in r.json() and "password_hash" not in r.json()

    assert client.get(f"/api/users/{uid}", headers=admin_headers).json()["email"] == "ana@test.com"
    assert any(u["id"] == uid for u in client.get("/api/users", headers=admin_headers).json())

    r = client.put(f"/api/users/{uid}", headers=admin_headers, json={"name": "Ana María"})
    assert r.status_code == 200 and r.json()["name"] == "Ana María"

    assert client.delete(f"/api/users/{uid}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/users/{uid}", headers=admin_headers).status_code == 404


def test_users_duplicate_email(client, admin_headers):
    body = {"name": "Dup", "email": "dup@test.com", "password": "secreto1"}
    assert client.post("/api/users", headers=admin_headers, json=body).status_code == 201
    assert client.post("/api/users", headers=admin_headers, json=body).status_code == 409


def test_users_validation(client, admin_headers):
    r = client.post("/api/users", headers=admin_headers, json={
        "name": "X", "email": "no-es-correo", "password": "123"})
    assert r.status_code == 422


def test_users_forbidden_for_normal_user(client, user_headers):
    assert client.get("/api/users", headers=user_headers).status_code == 403


# ---------- Categorías ----------
def test_categories_crud(client, admin_headers, user_headers):
    r = client.post("/api/categories", headers=admin_headers,
                    json={"name": "Bebidas", "description": "Frías y calientes"})
    assert r.status_code == 201
    cid = r.json()["id"]

    assert client.get(f"/api/categories/{cid}", headers=user_headers).status_code == 200
    assert len(client.get("/api/categories", headers=user_headers).json()) >= 1

    r = client.put(f"/api/categories/{cid}", headers=admin_headers,
                   json={"name": "Bebidas frías", "description": ""})
    assert r.json()["name"] == "Bebidas frías"

    assert client.post("/api/categories", headers=user_headers,
                       json={"name": "Hack"}).status_code == 403
    assert client.delete(f"/api/categories/{cid}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/categories/{cid}", headers=admin_headers).status_code == 404


# ---------- Productos ----------
def test_products_crud(client, admin_headers, user_headers):
    cid = client.post("/api/categories", headers=admin_headers,
                      json={"name": "Snacks"}).json()["id"]
    r = client.post("/api/products", headers=admin_headers,
                    json={"name": "Papas", "price": 18.5, "stock": 10, "category_id": cid})
    assert r.status_code == 201
    pid = r.json()["id"]

    assert client.get(f"/api/products/{pid}", headers=user_headers).json()["price"] == 18.5
    filtered = client.get(f"/api/products?category_id={cid}", headers=user_headers).json()
    assert [p["id"] for p in filtered] == [pid]

    r = client.put(f"/api/products/{pid}", headers=admin_headers,
                   json={"name": "Papas XL", "price": 25, "stock": 5, "category_id": cid})
    assert r.json()["name"] == "Papas XL"

    # No se puede borrar una categoría con productos
    assert client.delete(f"/api/categories/{cid}", headers=admin_headers).status_code == 409

    assert client.delete(f"/api/products/{pid}", headers=admin_headers).status_code == 204
    assert client.get(f"/api/products/{pid}", headers=admin_headers).status_code == 404


def test_product_invalid(client, admin_headers):
    r = client.post("/api/products", headers=admin_headers,
                    json={"name": "X", "price": -1, "stock": 1, "category_id": 1})
    assert r.status_code == 422
    r = client.post("/api/products", headers=admin_headers,
                    json={"name": "X", "price": 1, "stock": 1, "category_id": 99999})
    assert r.status_code == 404


# ---------- Pedidos ----------
def test_orders(client, admin_headers, user_headers):
    cid = client.post("/api/categories", headers=admin_headers,
                      json={"name": "Lácteos"}).json()["id"]
    pid = client.post("/api/products", headers=admin_headers,
                      json={"name": "Leche", "price": 30, "stock": 3,
                            "category_id": cid}).json()["id"]

    r = client.post("/api/orders", headers=user_headers,
                    json={"items": [{"product_id": pid, "quantity": 2}]})
    assert r.status_code == 201
    order = r.json()
    assert order["total"] == 60
    assert client.get(f"/api/products/{pid}", headers=user_headers).json()["stock"] == 1

    assert client.get(f"/api/orders/{order['id']}", headers=user_headers).status_code == 200
    assert any(o["id"] == order["id"]
               for o in client.get("/api/orders", headers=user_headers).json())

    # Stock insuficiente
    r = client.post("/api/orders", headers=user_headers,
                    json={"items": [{"product_id": pid, "quantity": 5}]})
    assert r.status_code == 409

    # Pedido vacío
    assert client.post("/api/orders", headers=user_headers,
                       json={"items": []}).status_code == 422
