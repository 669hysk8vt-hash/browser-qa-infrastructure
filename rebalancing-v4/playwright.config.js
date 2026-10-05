const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [
    ['line'],
    ['html', { outputFolder: '../playwright-report-rebalancing-v4', open: 'never' }],
  ],
  use: {
    baseURL: 'http://127.0.0.1:8501',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: 'python -m streamlit run rebalancing_app_v4_complete.py --server.headless true --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false',
    url: 'http://127.0.0.1:8501/_stcore/health',
    timeout: 120_000,
    reuseExistingServer: false,
    stdout: 'pipe',
    stderr: 'pipe',
  },
  projects: [
    { name: 'chrome-stable', use: { browserName: 'chromium', channel: 'chrome' } },
    { name: 'edge-stable', use: { browserName: 'chromium', channel: 'msedge' } },
  ],
});
