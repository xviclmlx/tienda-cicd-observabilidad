// Pruebas de extremo a extremo de la interfaz (frontend + backend).
const { test, expect } = require("@playwright/test");

const ADMIN = { email: process.env.ADMIN_EMAIL || "admin@tienda.com",
                password: process.env.ADMIN_PASSWORD || "Admin123!" };
const uid = () => Date.now().toString(36);

async function login(page, email = ADMIN.email, password = ADMIN.password) {
  await page.goto("/");
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.click("#login-submit");
}

test.beforeEach(async ({ page }) => {
  page.on("dialog", (d) => d.accept()); // confirmar eliminaciones
});

test("login incorrecto muestra error", async ({ page }) => {
  await login(page, ADMIN.email, "mala");
  await expect(page.locator("#login-error")).toHaveText("Credenciales incorrectas");
  await expect(page.locator("#app-view")).toBeHidden();
});

test("login correcto muestra el panel y cerrar sesión regresa al login", async ({ page }) => {
  await login(page);
  await expect(page.locator("#whoami")).toContainText("admin");
  await page.click("#logout");
  await expect(page.locator("#login-view")).toBeVisible();
});

test("CRUD de categorías desde la interfaz", async ({ page }) => {
  const name = `Categoria ${uid()}`;
  await login(page);
  await page.click("button[data-tab=categories]");
  await page.fill("#category-name", name);
  await page.fill("#category-description", "creada por Playwright");
  await page.click("#category-save");
  await expect(page.locator("#toast")).toHaveText("Creado correctamente");
  const row = page.locator("#categories-table tr", { hasText: name });
  await expect(row).toBeVisible();

  await row.getByRole("button", { name: "Editar" }).click();
  await page.fill("#category-name", `${name} editada`);
  await page.click("#category-save");
  await expect(page.locator("#categories-table tr", { hasText: `${name} editada` })).toBeVisible();

  await page.locator("#categories-table tr", { hasText: `${name} editada` })
    .getByRole("button", { name: "Eliminar" }).click();
  await expect(page.locator("#toast")).toHaveText("Eliminado correctamente");
  await expect(page.locator("#categories-table tr", { hasText: name })).toHaveCount(0);
});

test("CRUD de productos y creación de pedido desde la interfaz", async ({ page }) => {
  const s = uid();
  await login(page);
  await page.click("button[data-tab=categories]");
  await page.fill("#category-name", `CatProd ${s}`);
  await page.click("#category-save");
  await expect(page.locator("#toast")).toHaveText("Creado correctamente");

  await page.click("button[data-tab=products]");
  await page.fill("#product-name", `Producto ${s}`);
  await page.fill("#product-price", "15.50");
  await page.fill("#product-stock", "4");
  await page.selectOption("#product-category", { label: `CatProd ${s}` });
  await page.click("#product-save");
  const row = page.locator("#products-table tr", { hasText: `Producto ${s}` });
  await expect(row).toContainText("$15.50");

  await page.click("button[data-tab=orders]");
  await page.selectOption("#order-product", { label: `Producto ${s} — $15.50 (stock 4)` });
  await page.fill("#order-quantity", "2");
  await page.click("#order-save");
  await expect(page.locator("#toast")).toContainText("creado por $31.00");

  await page.click("button[data-tab=products]");
  await expect(row.locator("td").nth(3)).toHaveText("2");
  await row.getByRole("button", { name: "Eliminar" }).click();
  await expect(page.locator("#products-table tr", { hasText: `Producto ${s}` })).toHaveCount(0);
});

test("CRUD de usuarios y permisos de un usuario normal", async ({ page }) => {
  const s = uid();
  const email = `pw${s}@tienda.com`;
  await login(page);
  await page.click("button[data-tab=users]");
  await page.fill("#user-name", `Usuario ${s}`);
  await page.fill("#user-email", email);
  await page.fill("#user-password", "secreto1");
  await page.click("#user-save");
  await expect(page.locator("#users-table tr", { hasText: email })).toBeVisible();

  await page.click("#logout");
  await login(page, email, "secreto1");
  await expect(page.locator("#whoami")).toContainText("(user)");
  await expect(page.locator("button[data-tab=users]")).toBeHidden();
  await expect(page.locator("#product-form")).toBeHidden();

  await page.click("#logout");
  await login(page);
  await page.click("button[data-tab=users]");
  await page.locator("#users-table tr", { hasText: email }).getByRole("button", { name: "Eliminar" }).click();
  await expect(page.locator("#users-table tr", { hasText: email })).toHaveCount(0);
});
