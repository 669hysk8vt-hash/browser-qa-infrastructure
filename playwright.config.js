const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
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
