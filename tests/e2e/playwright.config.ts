import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: ".",
  use: { baseURL: process.env.E2E_BASE_URL || "http://localhost:8000" },
  webServer: process.env.CI ? {
    command: "python ../../manage.py runserver 8000",
    url: "http://localhost:8000/accounts/login/", reuseExistingServer: true,
  } : undefined,
});
