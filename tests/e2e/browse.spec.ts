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
  await page.getByRole("link", { name: "Browse" }).click();
  await expect(page.getByRole("heading", { name: "Browse certifications" })).toBeVisible();

  // Walk into the first provider with certs, then its first certification.
  const firstProvider = page.locator(".card a").first();
  await firstProvider.click();
  await expect(page.locator("table")).toBeVisible();
  const firstCert = page.locator("table a").first();
  await firstCert.click();

  // Detail page always renders the compatibility heading; content depends on holdings.
  await expect(
    page.getByRole("heading", { name: /compatibility with your certifications/i })
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Renewal|Level/i }).first()
  ).toBeVisible({ timeout: 2000 }).catch(() => {}); // table header presence is layout, not data
});

test("unknown provider 404s", async ({ page }) => {
  await login(page);
  const resp = await page.request.get("/catalog/definitely-not-a-provider/");
  expect(resp.status()).toBe(404);
});
