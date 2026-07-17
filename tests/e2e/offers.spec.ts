import { test, expect } from "@playwright/test";
// Offer submission (D12): pends for review AND queues a verification crawl (SEC-007).
const EMAIL = process.env.E2E_EMAIL || "e2e@example.com";
const PASS = process.env.E2E_PASSWORD || "a-long-test-password";

async function login(page, email = EMAIL) {
  await page.goto("/accounts/login/");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(PASS);
  await page.getByRole("button", { name: /sign in/i }).click();
}

test("submitted offer pends and its page lands in the verification queue", async ({ page }) => {
  await login(page);
  const stamp = Date.now();
  await page.goto("/offers/submit/");
  await page.getByLabel(/title/i).fill(`E2E Offer ${stamp}`);
  await page.getByLabel(/url/i).fill(`https://example.com/e2e-offer-${stamp}`);
  await page.getByRole("button", { name: /save/i }).click();
  await expect(page.getByText(/queued for a verification crawl/i)).toBeVisible();
  // Pending offers must NOT appear on the public offers list yet.
  await expect(page.getByText(`E2E Offer ${stamp}`)).toHaveCount(0);

  // Approver sees the verification entry, inert, in the submissions queue.
  await page.getByRole("button", { name: /sign out/i }).click();
  await login(page, process.env.E2E_APPROVER_EMAIL || "rev@example.com");
  await page.goto("/admin/research/sourcesubmission/");
  await expect(page.getByText(`Verify free offer: E2E Offer ${stamp}`)).toBeVisible();
});
