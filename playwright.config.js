const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  reporter: [
    ['line'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  use: {
    trace: 'on',
  },
  webServer: {
    command: 'node scripts/serve-test-site.js',
    url: 'http://127.0.0.1:4173/healthz',
    timeout: 10_000,
  },
  projects: [
    {
      name: 'chrome-stable',
      use: {
        browserName: 'chromium',
        channel: 'chrome',
      },
    },
    {
      name: 'edge-stable',
      use: {
        browserName: 'chromium',
        channel: 'msedge',
      },
    },
  ],
});
