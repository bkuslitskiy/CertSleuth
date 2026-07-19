import { test, expect } from "@playwright/test";
// Catalog browse + compatibility (user-facing). Data comes from whatever the local
// catalog holds; assertions target structure, not specific provider content.
const EMAIL = process.env.E2E_EMAIL || "e2e@example.com";
const PASS = process.env.E2E_PASSWORD || "a-long-test-password";

async function login(page) {
  await page.goto("/accounts/login/");
  await page.getByLabel(/email/i).fill(EMAIL);
  await page.getByLabel(/password/i).fill(PASS);
  await page.getByRole("button", { name: /sign in/i }).click();
}

test("browse is login-gated", async ({ page }) => {
  await page.goto("/catalog/");
  await expect(page).toHaveURL(/accounts\/login/);
});

test("nav Browse -> providers -> certs -> detail with compatibility section", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "Browse", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Browse certifications" })).toBeVisible();

  // CI runs on an empty catalog; local runs against real data. Assert the state we're in.
  const providers = page.locator(".card a");
  if ((await providers.count()) === 0) {
    await expect(page.getByText(/catalog is empty/i)).toBeVisible();
    return;
  }
  // Walk into the first provider, then its first certification.
  await providers.first().click();
  await expect(page.locator("table")).toBeVisible();
  await page.locator("table a").first().click();

  // Detail page always renders the compatibility heading; content depends on holdings.
  await expect(
    page.getByRole("heading", { name: /compatibility with your certifications/i })
  ).toBeVisible();
});

test("unknown provider 404s", async ({ page }) => {
  await login(page);
  const resp = await page.request.get("/catalog/definitely-not-a-provider/");
  expect(resp.status()).toBe(404);
});
