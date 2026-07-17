import { test, expect } from "@playwright/test";
// Ingest -> staging -> review loop (the MVP priority path). Approver credentials via env.
const EMAIL = process.env.E2E_APPROVER_EMAIL || "rev@example.com";
const PASS = process.env.E2E_PASSWORD || "a-long-test-password";

test("approver sees review queue link and staging admin loads", async ({ page }) => {
  await page.goto("/accounts/login/");
  await page.getByLabel(/email/i).fill(EMAIL);
  await page.getByLabel(/password/i).fill(PASS);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.getByRole("link", { name: "Review queue" }).click();
  await expect(page).toHaveURL(/stagedchange/);
});
