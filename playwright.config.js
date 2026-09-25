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
