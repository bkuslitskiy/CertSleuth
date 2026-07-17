import { test, expect } from "@playwright/test";

// Feature: auth + invite gate (D1). Written with the feature per D21.
test("anonymous is sent to login; closed signup shows invite-only", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/accounts\/login/);
  await page.goto("/accounts/signup/");
  await expect(page.getByText("Invite-only")).toBeVisible();
});

test("login renders wordmark with three segments", async ({ page }) => {
  await page.goto("/accounts/login/");
  const mark = page.locator(".wordmark");
  await expect(mark.locator(".c")).toHaveText("Cert");
  await expect(mark.locator(".s")).toHaveText("Sle");
  await expect(mark.locator(".u")).toHaveText("uth");
});
