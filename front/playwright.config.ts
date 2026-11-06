import { defineConfig, devices } from "@playwright/test";

// De ponta a ponta contra a API de verdade (SQLite novo a cada rodada), servindo o front exportado.
// Antes: `npm run build`. Os testes mudam o banco, por isso rodam um de cada vez.
const PORTA = process.env.PORTA_E2E ?? "8765";
const BASE = `http://127.0.0.1:${PORTA}`;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: BASE,
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "node e2e/servidor.mjs",
    url: `${BASE}/health`,
    reuseExistingServer: false,
    timeout: 240_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
