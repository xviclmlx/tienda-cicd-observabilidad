const $ = (s) => document.querySelector(s);
const state = { token: localStorage.getItem("token"), me: null, categories: [], products: [] };

async function api(path, opts = {}) {
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401 && path !== "/auth/login") { logout(); throw new Error("Sesión expirada"); }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    throw new Error(Array.isArray(d) ? d.map((e) => e.msg).join(", ") : d || `Error ${res.status}`);
  }
  return data;
}

function toast(msg, ok = true) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = ok ? "ok" : "err";
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => `$${Number(n).toFixed(2)}`;

// ---------- Sesión ----------
$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#login-error").textContent = "";
  try {
    const { access_token } = await api("/auth/login", {
      method: "POST",
      body: { email: $("#login-email").value, password: $("#login-password").value },
    });
    state.token = access_token;
    localStorage.setItem("token", access_token);
    await start();
  } catch (err) {
    $("#login-error").textContent = err.message;
  }
});

function logout() {
  state.token = null;
  localStorage.removeItem("token");
  $("#app-view").hidden = true;
  $("#login-view").hidden = false;
}
$("#logout").addEventListener("click", logout);

async function start() {
  state.me = await api("/auth/me");
  document.body.classList.toggle("is-admin", state.me.role === "admin");
  $("#whoami").textContent = `${state.me.name} (${state.me.role})`;
  $("#login-view").hidden = true;
  $("#app-view").hidden = false;
  showTab("products");
}

// ---------- Pestañas ----------
document.querySelectorAll("#tabs button").forEach((b) =>
  b.addEventListener("click", () => showTab(b.dataset.tab)));

async function showTab(name) {
  document.querySelectorAll("#tabs button").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => (t.hidden = t.id !== `tab-${name}`));
  toast("");
  try {
    await loaders[name]();
  } catch (err) { toast(err.message, false); }
}

const loaders = {
  async products() {
    state.categories = await api("/categories");
    state.products = await api("/products");
    $("#product-category").innerHTML = state.categories
      .map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
    const catName = (id) => state.categories.find((c) => c.id === id)?.name ?? id;
    $("#products-table tbody").innerHTML = state.products.map((p) => `
      <tr data-id="${p.id}">
        <td>${p.id}</td><td>${esc(p.name)}</td><td>${money(p.price)}</td>
        <td>${p.stock}</td><td>${esc(catName(p.category_id))}</td>
        <td class="actions admin-only">
          <button class="small ghost" data-edit="product" data-id="${p.id}">Editar</button>
          <button class="small danger" data-del="products" data-id="${p.id}">Eliminar</button>
        </td>
      </tr>`).join("");
  },
  async categories() {
    state.categories = await api("/categories");
    $("#categories-table tbody").innerHTML = state.categories.map((c) => `
      <tr data-id="${c.id}">
        <td>${c.id}</td><td>${esc(c.name)}</td><td>${esc(c.description)}</td>
        <td class="actions admin-only">
          <button class="small ghost" data-edit="category" data-id="${c.id}">Editar</button>
          <button class="small danger" data-del="categories" data-id="${c.id}">Eliminar</button>
        </td>
      </tr>`).join("");
  },
  async orders() {
    state.products = await api("/products");
    $("#order-product").innerHTML = state.products
      .map((p) => `<option value="${p.id}">${esc(p.name)} — ${money(p.price)} (stock ${p.stock})</option>`)
      .join("");
    const orders = await api("/orders");
    $("#orders-table tbody").innerHTML = orders.map((o) => `
      <tr data-id="${o.id}">
        <td>${o.id}</td><td>${o.user_id}</td>
        <td>${o.items.map((i) => `${i.quantity} × #${i.product_id}`).join(", ")}</td>
        <td>${money(o.total)}</td><td>${new Date(o.created_at).toLocaleString()}</td>
      </tr>`).join("");
  },
  async users() {
    const users = await api("/users");
    state.users = users;
    $("#users-table tbody").innerHTML = users.map((u) => `
      <tr data-id="${u.id}">
        <td>${u.id}</td><td>${esc(u.name)}</td><td>${esc(u.email)}</td><td>${u.role}</td>
        <td class="actions">
          <button class="small ghost" data-edit="user" data-id="${u.id}">Editar</button>
          <button class="small danger" data-del="users" data-id="${u.id}">Eliminar</button>
        </td>
      </tr>`).join("");
  },
};

// ---------- Formularios ----------
function bindForm(kind, tab, path, build) {
  $(`#${kind}-form`).addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = $(`#${kind}-id`)?.value;
    try {
      await api(id ? `${path}/${id}` : path, { method: id ? "PUT" : "POST", body: build(!!id) });
      toast(id ? "Actualizado correctamente" : "Creado correctamente");
      e.target.reset();
      if ($(`#${kind}-id`)) $(`#${kind}-id`).value = "";
      await loaders[tab]();
    } catch (err) { toast(err.message, false); }
  });
}

bindForm("product", "products", "/products", () => ({
  name: $("#product-name").value,
  price: parseFloat($("#product-price").value),
  stock: parseInt($("#product-stock").value, 10),
  category_id: parseInt($("#product-category").value, 10),
}));
bindForm("category", "categories", "/categories", () => ({
  name: $("#category-name").value,
  description: $("#category-description").value,
}));
bindForm("user", "users", "/users", (editing) => {
  const body = { name: $("#user-name").value, email: $("#user-email").value, role: $("#user-role").value };
  const pw = $("#user-password").value;
  if (pw || !editing) body.password = pw;
  return body;
});
$("#order-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const o = await api("/orders", {
      method: "POST",
      body: { items: [{ product_id: parseInt($("#order-product").value, 10),
                        quantity: parseInt($("#order-quantity").value, 10) }] },
    });
    toast(`Pedido #${o.id} creado por ${money(o.total)}`);
    await loaders.orders();
  } catch (err) { toast(err.message, false); }
});

document.querySelectorAll("[data-reset]").forEach((b) => b.addEventListener("click", () => {
  const kind = b.dataset.reset;
  $(`#${kind}-form`).reset();
  $(`#${kind}-id`).value = "";
}));

// ---------- Editar / eliminar (delegado) ----------
document.addEventListener("click", async (e) => {
  const edit = e.target.closest("[data-edit]");
  const del = e.target.closest("[data-del]");
  if (edit) {
    const id = Number(edit.dataset.id);
    const kind = edit.dataset.edit;
    if (kind === "product") {
      const p = state.products.find((x) => x.id === id);
      Object.assign(fields("product"), { id: p.id, name: p.name, price: p.price, stock: p.stock, category: p.category_id });
    } else if (kind === "category") {
      const c = state.categories.find((x) => x.id === id);
      Object.assign(fields("category"), { id: c.id, name: c.name, description: c.description });
    } else if (kind === "user") {
      const u = state.users.find((x) => x.id === id);
      Object.assign(fields("user"), { id: u.id, name: u.name, email: u.email, role: u.role, password: "" });
    }
  }
  if (del) {
    if (!confirm("¿Eliminar este registro?")) return;
    try {
      await api(`/${del.dataset.del}/${del.dataset.id}`, { method: "DELETE" });
      toast("Eliminado correctamente");
      await loaders[del.dataset.del]();
    } catch (err) { toast(err.message, false); }
  }
});

// Proxy que escribe en los inputs #<kind>-<campo>
function fields(kind) {
  return new Proxy({}, { set(_, key, value) { const el = $(`#${kind}-${key}`); if (el) el.value = value; return true; } });
}

if (state.token) start().catch(logout);
