import { test, expect } from "@playwright/test";
// Generic importer (spec 5.3-5.5). Covers the file-upload path end-to-end (Open Badges)
// without external network — upload a baked-free .json assertion, preview, confirm.
// URL-based sources (Microsoft Learn, Accredible) are covered by pytest with mocked fetch.
const EMAIL = process.env.E2E_EMAIL || "e2e@example.com";
const PASS = process.env.E2E_PASSWORD || "a-long-test-password";

async function login(page, email = EMAIL) {
  await page.goto("/accounts/login/");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(PASS);
  await page.getByRole("button", { name: /sign in/i }).click();
}

test("open badge upload previews and queues an unmatched credential", async ({ page }) => {
  await login(page);
  await page.goto("/track/import/openbadges/");
  await expect(page.getByRole("heading", { name: /import from open badges/i })).toBeVisible();

  const stamp = Date.now();
  const badge = JSON.stringify({
    type: "Assertion", issuedOn: "2023-01-15",
    badge: { name: `E2E Open Badge ${stamp}` },
  });
  await page.getByLabel(/open badge file/i).setInputFiles({
    name: "badge.json", mimeType: "application/json", buffer: Buffer.from(badge),
  });
  await page.getByRole("button", { name: /upload/i }).click();

  await expect(page.getByText(`E2E Open Badge ${stamp}`)).toBeVisible();
  await expect(page.getByText(/queue for research/i)).toBeVisible();
  await page.getByRole("button", { name: /import selected/i }).click();
  await expect(page.getByText(/queued 1 unmatched credential/i)).toBeVisible();

  // Approver finds it in the (inert) research queue.
  await page.getByRole("button", { name: /sign out/i }).click();
  await login(page, process.env.E2E_APPROVER_EMAIL || "rev@example.com");
  await page.goto("/admin/research/sourcesubmission/");
  await expect(page.getByText(
    `Open Badges credential with no catalog match: E2E Open Badge ${stamp}`)).toBeVisible();
});
