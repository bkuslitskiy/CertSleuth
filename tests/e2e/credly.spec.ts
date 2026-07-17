import { test, expect } from "@playwright/test";
// Credly network calls are NOT exercised here (unofficial endpoint, flaky in CI);
// pytest covers lookup matching and the confirm handler. This spec covers the page
// and the confirm round-trip for an unmatched badge queued for research.
const EMAIL = process.env.E2E_EMAIL || "e2e@example.com";
const PASS = process.env.E2E_PASSWORD || "a-long-test-password";

async function login(page) {
  await page.goto("/accounts/login/");
  await page.getByLabel(/email/i).fill(EMAIL);
  await page.getByLabel(/password/i).fill(PASS);
  await page.getByRole("button", { name: /sign in/i }).click();
}

test("credly import page renders the lookup form", async ({ page }) => {
  await login(page);
  await page.goto("/track/import/credly/");
  await expect(page.getByLabel(/credly profile url/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /look up profile/i })).toBeVisible();
});

test("unmatched badge queued by a user shows up in the approver's queue", async ({ page }) => {
  await login(page);
  await page.goto("/track/import/credly/");
  const token = await page.locator("input[name=csrfmiddlewaretoken]").first().inputValue();
  const stamp = Date.now();
  const resp = await page.request.post("/track/import/credly/", {
    form: {
      csrfmiddlewaretoken: token,
      confirm: "1",
      profile_url: "https://www.credly.com/users/e2e/badges",
      queue_badge: JSON.stringify({
        badge: `E2E Unmatched Badge ${stamp}`,
        template_id: `e2e-${stamp}`,
        template_url: `https://www.credly.com/badges/e2e-${stamp}`,
      }),
    },
  });
  expect(resp.status()).toBe(200); // redirect followed to dashboard

  // The approver finds it queued (inert, D16) in admin.
  await page.getByRole("button", { name: /sign out/i }).click();
  await page.goto("/accounts/login/");
  await page.getByLabel(/email/i).fill(process.env.E2E_APPROVER_EMAIL || "rev@example.com");
  await page.getByLabel(/password/i).fill(PASS);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.goto("/admin/research/sourcesubmission/");
  await expect(page.getByText(`E2E Unmatched Badge ${stamp}`)).toBeVisible();
});
