"""A tiny, deterministic stand-in for the demo store, served through Playwright
request interception (``context.route``), so no request ever leaves the machine.

It reproduces only what the page objects rely on: the ``data-test`` hooks and
class names of the real app, its login rules and messages, a cart kept in
``localStorage`` (as the real app does), the four sort options, the checkout
form's validation messages, the checkout totals with 8% tax (including the app's unrounded float item
total), and the documented
defects of the practice accounts:

* ``problem_user``: sorting does nothing, catalogue adds of odd product ids and
  removals of even ids silently do nothing, and typing a last name at checkout
  overwrites the first name;
* ``performance_glitch_user``: the catalogue blocks for ``glitch_ms`` before
  rendering;
* ``error_user``: catalogue adds of odd product ids silently do nothing.

It is a test double, not a copy of the app: layout, images and styling are
omitted.

Knobs for negative tests of the order-total check:

* ``overview_markup_cents`` inflates the checkout "Item total" so it no longer
  matches the products in the cart (a pricing bug);
* ``tax_basis_points`` changes the tax rate the overview applies (800 = 8%).
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import BrowserContext, Route

BASE_URL = "https://fake-store.test"

USERS = (
    "standard_user",
    "locked_out_user",
    "problem_user",
    "performance_glitch_user",
    "error_user",
    "visual_user",
)
PASSWORD = "secret_sauce"  # the demo store's published practice password


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    price: Decimal


CATALOG: tuple[Product, ...] = (
    Product(0, "Sauce Labs Bike Light", Decimal("9.99")),
    Product(1, "Sauce Labs Bolt T-Shirt", Decimal("15.99")),
    Product(2, "Sauce Labs Onesie", Decimal("7.99")),
    Product(3, "Test.allTheThings() T-Shirt (Red)", Decimal("15.99")),
    Product(4, "Sauce Labs Backpack", Decimal("29.99")),
    Product(5, "Sauce Labs Fleece Jacket", Decimal("49.99")),
)

_COMMON_JS = """
const CATALOG = __CATALOG__;
const USERS = __USERS__;
const MARKUP_CENTS = __MARKUP__;
const TAX_BP = __TAX_BP__;
const GLITCH_MS = __GLITCH_MS__;
function user() { return localStorage.getItem('session-username'); }
function cart() { return JSON.parse(localStorage.getItem('cart-contents') || '[]'); }
function setCart(c) { localStorage.setItem('cart-contents', JSON.stringify(c)); renderBadge(); }
// Adds and removals from the catalogue and detail pages: the faulty accounts
// silently ignore some of them, like the real app.
function addItem(id) {
  if ((user() === 'problem_user' || user() === 'error_user') && id % 2 === 1) return;
  const c = cart(); if (!c.includes(id)) c.push(id); setCart(c);
}
function removeItem(id) {
  if (user() === 'problem_user' && id % 2 === 0) return;
  setCart(cart().filter(x => x !== id));
}
// Removal from the cart page always works.
function removeFromCart(id) { setCart(cart().filter(x => x !== id)); }
function slug(name) { return name.replace(/\\s+/g, '-').toLowerCase(); }
function renderBadge() {
  const link = document.querySelector('[data-test="shopping-cart-link"]');
  if (!link) return;
  const n = cart().length;
  link.innerHTML = n ? '<span class="shopping_cart_badge" data-test="shopping-cart-badge">' + n + '</span>' : '';
}
function toggleMenu() {
  const nav = document.getElementById('menu');
  nav.style.display = nav.style.display === 'none' ? 'block' : 'none';
}
function logout() { localStorage.removeItem('session-username'); location.href = '/'; }
function resetApp() { localStorage.removeItem('cart-contents'); renderBadge(); }
function cartRows(withRemove) {
  return cart().map(id => {
    const p = CATALOG[id];
    return '<div class="cart_item" data-test="inventory-item">'
      + '<div class="cart_quantity" data-test="item-quantity">1</div>'
      + '<div class="inventory_item_name" data-test="inventory-item-name">' + p.name + '</div>'
      + '<div class="inventory_item_price" data-test="inventory-item-price">$' + p.price + '</div>'
      + (withRemove ? '<button class="btn cart_button" data-test="remove-' + slug(p.name)
          + '" onclick="removeFromCart(' + id + '); render()">Remove</button>' : '')
      + '</div>';
  }).join('');
}
"""

_HEADER = """
<div class="primary_header" data-test="primary-header">
  <button id="react-burger-menu-btn" type="button" onclick="toggleMenu()">Open Menu</button>
  <nav id="menu" class="bm-menu" style="display:none">
    <a id="inventory_sidebar_link" data-test="inventory-sidebar-link" href="/inventory.html">All Items</a>
    <a id="logout_sidebar_link" data-test="logout-sidebar-link" href="#" onclick="logout(); return false">Logout</a>
    <a id="reset_sidebar_link" data-test="reset-sidebar-link" href="#" onclick="resetApp(); toggleMenu(); return false">Reset App State</a>
  </nav>
  <div class="app_logo">Swag Labs</div>
  <a class="shopping_cart_link" data-test="shopping-cart-link" href="/cart.html"></a>
</div>
"""


@dataclass
class FakeStore:
    overview_markup_cents: int = 0
    tax_basis_points: int = 800
    glitch_ms: int = 2500
    requests: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def install(self, context: BrowserContext) -> None:
        """Serve the store at ``BASE_URL`` and abort every other request.

        Playwright runs the most recently registered matching route first, so
        the store route wins for its own origin and the catch-all aborts the rest.
        """
        context.route("**/*", lambda route: route.abort())
        context.route(f"{BASE_URL}/**", self._handle)

    def _handle(self, route: Route) -> None:
        url = urlparse(route.request.url)
        self.requests.append(url.path)
        status, body = self.render(url.path or "/", parse_qs(url.query))
        route.fulfill(status=status, content_type="text/html; charset=utf-8", body=body)

    # ------------------------------------------------------------------ #
    # Pages
    # ------------------------------------------------------------------ #
    def render(self, path: str, query: dict[str, list[str]]) -> tuple[int, str]:
        pages = {
            "/": self._login,
            "/inventory.html": self._inventory,
            "/cart.html": self._cart,
            "/checkout-step-one.html": self._checkout_info,
            "/checkout-step-two.html": self._checkout_overview,
            "/checkout-complete.html": self._complete,
        }
        if path == "/inventory-item.html":
            return 200, self._item(query.get("id", [""])[0])
        if path in pages:
            return 200, pages[path]()
        return 404, self._doc("Not found", "<h1>404</h1>")

    def _doc(self, title: str, body: str, script: str = "") -> str:
        common = (
            _COMMON_JS.replace(
                "__CATALOG__",
                json.dumps({p.id: {"name": p.name, "price": f"{p.price:.2f}"} for p in CATALOG}),
            )
            .replace("__USERS__", json.dumps(USERS))
            .replace("__MARKUP__", str(self.overview_markup_cents))
            .replace("__TAX_BP__", str(self.tax_basis_points))
            .replace("__GLITCH_MS__", str(self.glitch_ms))
        )
        return (
            f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head>"
            f"<body>{body}<script>{common}\n{script}\nrenderBadge();</script></body></html>"
        )

    def _login(self) -> str:
        body = """
        <div class="login_logo">Swag Labs</div>
        <form id="login" onsubmit="return doLogin(event)">
          <input data-test="username" id="user-name" placeholder="Username">
          <input data-test="password" id="password" type="password" placeholder="Password">
          <div class="error-message-container" id="err"></div>
          <input type="submit" data-test="login-button" id="login-button" value="Login">
        </form>"""
        script = f"""
        function doLogin(e) {{
          e.preventDefault();
          const u = document.getElementById('user-name').value;
          const p = document.getElementById('password').value;
          let msg = '';
          if (!u) msg = 'Username is required';
          else if (!p) msg = 'Password is required';
          else if (p !== {json.dumps(PASSWORD)} || !USERS.includes(u))
            msg = 'Username and password do not match any user in this service';
          else if (u === 'locked_out_user') msg = 'Sorry, this user has been locked out.';
          if (msg) {{
            document.getElementById('err').innerHTML =
              '<h3 data-test="error">Epic sadface: ' + msg + '</h3>';
            return false;
          }}
          localStorage.setItem('session-username', u);
          location.href = '/inventory.html';
          return false;
        }}"""
        return self._doc("Swag Labs", body, script)

    def _inventory(self) -> str:
        body = f"""{_HEADER}
        <span class="title" data-test="title">Products</span>
        <span class="select_container">
          <span class="active_option" data-test="active-option">Name (A to Z)</span>
          <select class="product_sort_container" data-test="product-sort-container"
                  onchange="sortBy(this.value)">
            <option value="az">Name (A to Z)</option>
            <option value="za">Name (Z to A)</option>
            <option value="lohi">Price (low to high)</option>
            <option value="hilo">Price (high to low)</option>
          </select>
        </span>
        <div class="inventory_list" data-test="inventory-list" id="list"></div>"""
        script = """
        const LABELS = {az: 'Name (A to Z)', za: 'Name (Z to A)',
                        lohi: 'Price (low to high)', hilo: 'Price (high to low)'};
        const CMP = {
          az: (a, b) => a.name.localeCompare(b.name),
          za: (a, b) => b.name.localeCompare(a.name),
          lohi: (a, b) => Number(a.price) - Number(b.price),
          hilo: (a, b) => Number(b.price) - Number(a.price),
        };
        let order = 'az';
        function card(p) {
          const inCart = cart().includes(p.id);
          const label = inCart ? 'Remove' : 'Add to cart';
          return '<div class="inventory_item" data-test="inventory-item">'
            + '<a href="#" id="item_' + p.id + '_title_link" data-test="item-' + p.id + '-title-link"'
            + ' onclick="location.href=\\'/inventory-item.html?id=' + p.id + '\\'; return false">'
            + '<div class="inventory_item_name" data-test="inventory-item-name">' + p.name + '</div></a>'
            + '<div class="inventory_item_price" data-test="inventory-item-price">$' + p.price + '</div>'
            + '<button class="btn ' + (inCart ? 'btn_secondary' : 'btn_primary') + ' btn_inventory"'
            + ' data-test="' + slug(label + '-' + p.name) + '"'
            + ' onclick="' + (inCart ? 'removeItem' : 'addItem') + '(' + p.id + '); render()">'
            + label + '</button></div>';
        }
        function render() {
          const products = Object.entries(CATALOG).map(([id, p]) => ({id: Number(id), ...p}));
          document.getElementById('list').innerHTML = products.sort(CMP[order]).map(card).join('');
        }
        function sortBy(key) {
          if (user() === 'problem_user') {  // sorting does nothing; the select snaps back
            document.querySelector('[data-test="product-sort-container"]').value = order;
            return;
          }
          if (user() === 'error_user') { alert('Sorting is broken!'); return; }
          order = key;
          document.querySelector('[data-test="active-option"]').textContent = LABELS[key];
          render();
        }
        if (user() === 'performance_glitch_user') {
          const until = Date.now() + GLITCH_MS;
          while (Date.now() < until) {}  // the real app blocks like this too
        }
        render();"""
        return self._doc("Swag Labs", body, script)

    def _item(self, raw_id: str) -> str:
        product = next((p for p in CATALOG if str(p.id) == raw_id), None)
        if product is None:
            return self._doc("Swag Labs", f"{_HEADER}<div>ITEM NOT FOUND</div>")
        body = f"""{_HEADER}
        <div class="inventory_details_name" data-test="inventory-item-name">{html.escape(product.name)}</div>
        <div class="inventory_details_price" data-test="inventory-item-price">${product.price}</div>
        <span id="btn"></span>
        <button data-test="back-to-products" id="back-to-products"
                onclick="location.href='/inventory.html'">Back to products</button>"""
        script = f"""
        const ID = {product.id};
        function renderBtn() {{
          document.getElementById('btn').innerHTML = cart().includes(ID)
            ? '<button data-test="remove" id="remove" onclick="removeItem(ID); renderBtn()">Remove</button>'
            : '<button data-test="add-to-cart" id="add-to-cart" onclick="addItem(ID); renderBtn()">Add to cart</button>';
        }}
        renderBtn();"""
        return self._doc("Swag Labs", body, script)

    def _cart(self) -> str:
        body = f"""{_HEADER}
        <span class="title" data-test="title">Your Cart</span>
        <div class="cart_list" data-test="cart-list" id="list"></div>
        <button data-test="continue-shopping" id="continue-shopping"
                onclick="location.href='/inventory.html'">Continue Shopping</button>
        <button data-test="checkout" id="checkout"
                onclick="location.href='/checkout-step-one.html'">Checkout</button>"""
        script = "function render() { document.getElementById('list').innerHTML = cartRows(true); }\nrender();"
        return self._doc("Swag Labs", body, script)

    def _checkout_info(self) -> str:
        body = f"""{_HEADER}
        <form onsubmit="return next(event)">
          <input data-test="firstName" id="first-name" placeholder="First Name">
          <input data-test="lastName" id="last-name" placeholder="Last Name"
                 oninput="lastNameTyped(this)">
          <input data-test="postalCode" id="postal-code" placeholder="Zip/Postal Code">
          <div class="error-message-container" id="err"></div>
          <input type="submit" data-test="continue" id="continue" value="Continue">
        </form>"""
        script = """
        function lastNameTyped(input) {
          if (user() !== 'problem_user') return;
          document.getElementById('first-name').value = input.value;  // the documented defect
          input.value = '';
        }
        function next(e) {
          e.preventDefault();
          const missing = [['first-name', 'First Name'], ['last-name', 'Last Name'],
                           ['postal-code', 'Postal Code']]
            .find(([id]) => !document.getElementById(id).value);
          if (missing) {
            document.getElementById('err').innerHTML =
              '<h3 data-test="error">Error: ' + missing[1] + ' is required</h3>';
            return false;
          }
          location.href = '/checkout-step-two.html';
          return false;
        }"""
        return self._doc("Swag Labs", body, script)

    def _checkout_overview(self) -> str:
        body = f"""{_HEADER}
        <div class="cart_list" id="list"></div>
        <div class="summary_subtotal_label" data-test="subtotal-label" id="sub"></div>
        <div class="summary_tax_label" data-test="tax-label" id="tax"></div>
        <div class="summary_total_label" data-test="total-label" id="tot"></div>
        <button data-test="finish" id="finish" onclick="finish()">Finish</button>"""
        script = """
        document.getElementById('list').innerHTML = cartRows(false);
        // Like the real app: a float sum printed as is (e.g. 59.980000000000004),
        // tax and total formatted with toFixed(2).
        const sum = cart().reduce((s, id) => s + Number(CATALOG[id].price), 0) + MARKUP_CENTS / 100;
        const tax = (sum * TAX_BP / 10000).toFixed(2);
        document.getElementById('sub').textContent = 'Item total: $' + sum;
        document.getElementById('tax').textContent = 'Tax: $' + tax;
        document.getElementById('tot').textContent = 'Total: $' + (sum + parseFloat(tax)).toFixed(2);
        function finish() { localStorage.removeItem('cart-contents'); location.href = '/checkout-complete.html'; }"""
        return self._doc("Swag Labs", body, script)

    def _complete(self) -> str:
        body = f"""{_HEADER}
        <h2 class="complete-header" data-test="complete-header">Thank you for your order!</h2>"""
        return self._doc("Swag Labs", body)
