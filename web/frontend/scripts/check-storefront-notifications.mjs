import assert from "node:assert/strict";
import { chromium, expect } from "@playwright/test";

const origin = new URL(process.argv[2] || "http://127.0.0.1:5189");
assert(["127.0.0.1", "localhost", "[::1]"].includes(origin.hostname), "Browser validation requires a loopback frontend");
const browser = await chromium.launch({ headless: true });
const product = { id: "product-1", slug: "chair", name: "Chair", price: "20", currency: "USD", in_stock: true, images: [] };
const site = { brand: "Test Store", commerce_currency: "USD" };
const token = "a".repeat(64);
let passed = 0;

async function scenario(name, run, options = {}) {
  const context = await browser.newContext({ viewport: options.viewport || { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  const state = { productError: false, deliveryError: false, noAreas: false, discountError: false, orderError: false, changed: false, priceChanged: false };
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const json = (data, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    const unsafe = { detail: "SUPABASE_SERVICE_KEY=private-key; SQL internal_table failed" };
    if (path.includes("/public/sites/")) {
      if (path.includes("/catalog/products/")) return state.productError ? json(unsafe, 503) : json({ site, product, category: null, tags: [], attributes: [], options: [], variants: [] });
      if (path.endsWith("/store-profile")) return json({ site });
      if (path.endsWith("/delivery-areas")) return state.deliveryError ? json(unsafe, 503) : json({ areas: state.noAreas ? [] : [{ id: "area-1", name_en: "City", name_ar: "City" }] });
      if (path.endsWith("/cart/reconcile")) return json({ valid: !state.changed, items: [{ product_id: product.id, name: product.name, price: state.priceChanged ? "25" : product.price, currency: product.currency }] });
      if (path.endsWith("/orders")) return state.orderError ? json(unsafe, 503) : json({ confirmation_token: token });
      if (path.includes("/orders/confirmation/")) return json({ order: { id: "order-1", order_number: "TEST-1", created_at: "2026-09-17T12:00:00Z", total: "20", currency: "USD", status: "pending", payment_status: "unpaid" }, items: [] });
      if (path.endsWith("/loyalty/me")) return json({ detail: "Not signed in" }, 401);
      if (path.endsWith("/discounts")) return state.discountError ? json(unsafe, 503) : json({ conditions: [] });
      if (path.endsWith("/visits")) return json({ success: true });
      return json({ site, catalog: { categories: [], tags: [], products: [product], pagination: { page: 1, pages: 1, total: 1, limit: 12 } } });
    }
    if (path.includes("/auth/") || path.startsWith("/api/")) return json({ detail: "Not signed in" }, 401);
    if (url.origin !== origin.origin) return route.abort();
    return route.continue();
  });
  const toast = page.locator(".live-store-action-toast");
  async function visibleToast(text) {
    await expect(toast).toBeVisible();
    await expect(toast).toContainText(text);
    const visible = await toast.evaluate((el) => {
      const r = el.getBoundingClientRect();
      const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      return r.x >= 0 && r.y >= 0 && r.right <= innerWidth && r.bottom <= innerHeight && (el === top || el.contains(top));
    });
    assert(visible, `${name}: toast must be inside viewport and above other content`);
    assert(!((await page.locator("body").innerText()).includes("SUPABASE_SERVICE_KEY")), "Sensitive exception leaked");
  }
  const gotoProduct = () => page.goto(new URL("/site/demo/shop/product/chair", origin).href);
  async function checkout() {
    await gotoProduct();
    await page.getByRole("button", { name: "Add to cart", exact: true }).click();
    await page.getByRole("button", { name: "Open cart, 1 item" }).click();
    await page.getByRole("link", { name: /Proceed to checkout/ }).click();
    await page.locator('[name="customer_name"]').fill("Customer");
    await page.locator('[name="email"]').fill("customer@example.test");
    await page.locator('[name="phone"]').fill("123456789");
    await page.locator('[name="street"]').fill("Main street");
    await expect(page.locator('[name="service_area_id"]')).toHaveValue("area-1");
  }
  try {
    await run({ page, state, toast, visibleToast, gotoProduct, checkout });
    assert.deepEqual(errors, [], `${name}: browser exceptions`);
    passed += 1;
    process.stdout.write(`PASS ${name}\n`);
  } finally { await context.close(); }
}

try {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    await scenario(`cart actions ${viewport.width}px`, async ({ page, visibleToast, toast, gotoProduct }) => {
      await gotoProduct();
      await page.getByRole("button", { name: "Add to cart", exact: true }).click();
      await visibleToast("Added to cart");
      await page.getByRole("button", { name: "Open cart, 1 item" }).click();
      await page.getByRole("button", { name: "Increase Chair quantity" }).click();
      await visibleToast("Quantity updated");
      await page.getByRole("button", { name: "Decrease Chair quantity" }).click();
      await visibleToast("Quantity updated");
      await page.getByRole("button", { name: "Remove Chair" }).click();
      await visibleToast("Item removed");
      await expect(page.getByRole("button", { name: "Open cart, 0 items" })).toBeVisible();
      await toast.getByRole("button", { name: "Close" }).click();
      await expect(toast).toHaveCount(0);
    }, { viewport });
  }
  await scenario("Arabic add-to-cart notification", async ({ page, gotoProduct, visibleToast, toast }) => {
    await gotoProduct();
    await page.getByRole("button", { name: "العربية", exact: true }).click();
    await page.getByRole("button", { name: "أضف إلى السلة", exact: true }).click();
    await visibleToast("تمت الإضافة إلى السلة");
    await expect(toast).toHaveAttribute("dir", "rtl");
  });
  await scenario("checkout required fields", async ({ page, gotoProduct, visibleToast }) => {
    await gotoProduct();
    await page.getByRole("button", { name: "Add to cart", exact: true }).click();
    await page.getByRole("button", { name: "Open cart, 1 item" }).click();
    await page.getByRole("link", { name: /Proceed to checkout/ }).click();
    await page.getByRole("button", { name: "Place order", exact: true }).click();
    await visibleToast("Check your checkout details");
  });
  await scenario("toast auto dismissal", async ({ page, gotoProduct, visibleToast, toast }) => {
    await gotoProduct();
    await page.getByRole("button", { name: "Add to cart", exact: true }).click();
    await visibleToast("Added to cart");
    await expect(toast).toHaveCount(0, { timeout: 6000 });
  });
  await scenario("quantity limit", async ({ page, gotoProduct, visibleToast }) => {
    await gotoProduct();
    await page.evaluate((item) => localStorage.setItem("madar-store-cart:demo", JSON.stringify([{ ...item, quantity: 99 }])), product);
    await page.reload();
    await page.getByRole("button", { name: "Add to cart", exact: true }).click();
    await visibleToast("Quantity limit reached");
    await expect(page.getByRole("button", { name: "Open cart, 99 items" })).toBeVisible();
  });
  await scenario("changed cart", async ({ page, state, checkout, visibleToast }) => { await checkout(); state.changed = true; await page.getByRole("button", { name: "Place order", exact: true }).click(); await visibleToast("Your cart changed"); });
  await scenario("changed prices", async ({ page, state, checkout, visibleToast }) => { await checkout(); state.priceChanged = true; await page.getByRole("button", { name: "Place order", exact: true }).click(); await visibleToast("Your cart prices changed"); });
  await scenario("mobile checkout", async ({ page, checkout, visibleToast }) => { await checkout(); await page.getByRole("button", { name: "Place order", exact: true }).click(); await visibleToast("Order placed"); }, { viewport: { width: 390, height: 844 } });
  await scenario("product read failure", async ({ state, gotoProduct, visibleToast }) => { state.productError = true; await gotoProduct(); await visibleToast("Could not load the live store"); });
  await scenario("storage failure", async ({ page, gotoProduct, visibleToast }) => {
    await gotoProduct();
    await page.evaluate(() => { Storage.prototype.setItem = () => { throw Error("internal_storage secret"); }; });
    await page.getByRole("button", { name: "Add to cart", exact: true }).click();
    await visibleToast("Could not update your cart");
    await expect(page.getByRole("button", { name: "Open cart, 0 items" })).toBeVisible();
  });
  await scenario("checkout rejection", async ({ page, state, checkout, visibleToast }) => { await checkout(); state.orderError = true; await page.getByRole("button", { name: "Place order", exact: true }).click(); await visibleToast("Could not place your order"); });
  await scenario("checkout success survives navigation", async ({ page, checkout, visibleToast }) => { await checkout(); await page.getByRole("button", { name: "Place order", exact: true }).click(); await visibleToast("Order placed"); await expect(page).toHaveURL(new RegExp(`/confirmation/${token}$`)); });
  await scenario("discount failure", async ({ state, gotoProduct, visibleToast }) => { state.discountError = true; await gotoProduct(); await visibleToast("Could not load available discounts"); });
  await scenario("no delivery options", async ({ page, state, gotoProduct, visibleToast }) => { state.noAreas = true; await gotoProduct(); await page.getByRole("button", { name: "Add to cart", exact: true }).click(); await page.getByRole("button", { name: "Open cart, 1 item" }).click(); await page.getByRole("link", { name: /Proceed to checkout/ }).click(); await visibleToast("Delivery is currently unavailable"); });
  await scenario("delivery failure", async ({ page, state, gotoProduct, visibleToast }) => { state.deliveryError = true; await gotoProduct(); await page.getByRole("button", { name: "Add to cart", exact: true }).click(); await page.getByRole("button", { name: "Open cart, 1 item" }).click(); await page.getByRole("link", { name: /Proceed to checkout/ }).click(); await visibleToast("Could not load delivery options"); });
  process.stdout.write(`${passed} mocked browser scenarios passed; external network blocked.\n`);
} finally { await browser.close(); }
