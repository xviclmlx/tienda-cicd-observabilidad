// Pruebas de API (backend) a través del contenedor real, con Playwright request.
const { test, expect } = require("@playwright/test");

const ADMIN = { email: process.env.ADMIN_EMAIL || "admin@tienda.com",
                password: process.env.ADMIN_PASSWORD || "Admin123!" };
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

let auth;
test.beforeAll(async ({ request }) => {
  const r = await request.post("/api/auth/login", { data: ADMIN });
  expect(r.status()).toBe(200);
  auth = { Authorization: `Bearer ${(await r.json()).access_token}` };
});

test("GET /health responde ok", async ({ request }) => {
  const r = await request.get("/health");
  expect(r.ok()).toBeTruthy();
  expect((await r.json()).status).toBe("ok");
});

test("login con credenciales malas devuelve 401", async ({ request }) => {
  const r = await request.post("/api/auth/login", { data: { email: ADMIN.email, password: "x" } });
  expect(r.status()).toBe(401);
});

test("endpoints protegidos sin token devuelven 401", async ({ request }) => {
  for (const p of ["/api/users", "/api/categories", "/api/products", "/api/orders"]) {
    expect((await request.get(p)).status(), p).toBe(401);
  }
});

test("CRUD completo vía API: categoría, producto, usuario y pedido", async ({ request }) => {
  const s = uid();
  let r = await request.post("/api/categories", { headers: auth, data: { name: `Cat ${s}` } });
  expect(r.status()).toBe(201);
  const cat = await r.json();

  r = await request.post("/api/products", { headers: auth,
    data: { name: `Prod ${s}`, price: 10, stock: 5, category_id: cat.id } });
  expect(r.status()).toBe(201);
  const prod = await r.json();

  r = await request.put(`/api/products/${prod.id}`, { headers: auth,
    data: { name: `Prod ${s} v2`, price: 12.5, stock: 5, category_id: cat.id } });
  expect((await r.json()).price).toBe(12.5);

  r = await request.post("/api/users", { headers: auth,
    data: { name: `User ${s}`, email: `u${s}@tienda.com`, password: "secreto1" } });
  expect(r.status()).toBe(201);
  const user = await r.json();

  r = await request.post("/api/orders", { headers: auth,
    data: { items: [{ product_id: prod.id, quantity: 2 }] } });
  expect(r.status()).toBe(201);
  expect((await r.json()).total).toBe(25);

  r = await request.get("/api/orders", { headers: auth });
  expect(r.ok()).toBeTruthy();

  expect((await request.delete(`/api/users/${user.id}`, { headers: auth })).status()).toBe(204);
});
