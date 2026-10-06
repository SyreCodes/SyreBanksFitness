import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e', timeout: 60_000, fullyParallel: false, workers: 1, retries: 0,
  reporter: 'list', expect: { timeout: 15_000 },
  use: { baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1000 }, screenshot: 'only-on-failure', trace: 'retain-on-failure', launchOptions: process.env.PLAYWRIGHT_CHROME ? {executablePath:process.env.PLAYWRIGHT_CHROME} : undefined },
});
