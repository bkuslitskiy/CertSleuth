import { test, expect } from "@playwright/test";
// Requires seeded test user (see CI job: manage.py loaddata e2e or create_e2e_user cmd).
const EMAIL = process.env.E2E_EMAIL || "e2e@example.com";
const PASS = process.env.E2E_PASSWORD || "a-long-test-password";

async function login(page) {
  await page.goto("/accounts/login/");
  await page.getByLabel(/email/i).fill(EMAIL);
  await page.getByLabel(/password/i).fill(PASS);
  await page.getByRole("button", { name: /sign in/i }).click();
}

test("dashboard shows empty states and theme toggles", async ({ page }) => {
  await login(page);
  await expect(page.getByText("Your certifications")).toBeVisible();
  const html = page.locator("html");
  await expect(html).toHaveAttribute("data-theme", "dark"); // dark default (brief)
  await page.getByRole("button", { name: "Theme" }).click();
  await expect(html).toHaveAttribute("data-theme", "light");
});

test("scan request from an unenrolled user bounces to enrollment (SEC-013 gate)", async ({ page }) => {
  await login(page);
  await expect(page.getByRole("link", { name: /enable inbox scanning/i })).toBeVisible();
  const token = await page.locator("input[name=csrfmiddlewaretoken]").first().inputValue();
  const resp = await page.request.post("/track/gmail/scan-request/", {
    form: { csrfmiddlewaretoken: token },
  });
  expect(resp.url()).toContain("/accounts/gmail-enrollment/");
});

test("ICS feed link is present and fetchable", async ({ page, request }) => {
  await login(page);
  const feedText = await page.locator(".data").first().innerText();
  const url = feedText.replace("Subscribe: ", "").trim();
  const resp = await request.get(url);
  expect(resp.status()).toBe(200);
  expect(await resp.text()).toContain("BEGIN:VCALENDAR");
});
