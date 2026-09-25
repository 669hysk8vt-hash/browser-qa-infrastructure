const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { test, expect } = require('@playwright/test');

const artifactDirectory = path.resolve(__dirname, '../../artifacts/self-test');
const selfTestUrl = pathToFileURL(
  path.resolve(__dirname, '../../test-site/self-test.html'),
).href;

const expectedBrowsers = {
  'chrome-stable': {
    productName: 'Google Chrome',
    channel: 'chrome',
    userAgentPattern: /Chrome\/\d/,
    forbiddenUserAgentPattern: /Edg\//,
  },
  'edge-stable': {
    productName: 'Microsoft Edge',
    channel: 'msedge',
    userAgentPattern: /Edg\/\d/,
  },
};

test('configured branded browser passes the infrastructure self-test', async ({
  browser,
  page,
}, testInfo) => {
  const expected = expectedBrowsers[testInfo.project.name];
  expect(expected, `Unexpected Playwright project: ${testInfo.project.name}`).toBeTruthy();

  await page.goto(selfTestUrl);
  expect(page.url()).toBe(selfTestUrl);
  await expect(page).toHaveTitle('Browser QA self-test');
  await expect(page.getByRole('heading', { name: 'Browser QA self-test' })).toBeVisible();
  await expect(page.locator('#javascript-status')).toHaveText('JavaScript executed.');
  await expect
    .poll(() => page.evaluate(() => window.browserQaSelfTest))
    .toEqual({ marker: 'browser-qa-javascript-executed', executed: true });

  const userAgent = await page.evaluate(() => navigator.userAgent);
  const browserVersion = browser.version();
  expect(userAgent).toMatch(expected.userAgentPattern);
  if (expected.forbiddenUserAgentPattern) {
    expect(userAgent).not.toMatch(expected.forbiddenUserAgentPattern);
  }
  expect(browserVersion).toMatch(/^\d+(?:\.\d+)+$/);

  await fs.mkdir(artifactDirectory, { recursive: true });
  const screenshotPath = path.join(artifactDirectory, `${testInfo.project.name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });

  const evidence = {
    project: testInfo.project.name,
    expectedProductName: expected.productName,
    configuredChannel: expected.channel,
    browserVersion,
    userAgent,
    pageUrl: page.url(),
    javascriptEvidence: await page.evaluate(() => window.browserQaSelfTest),
  };
  await fs.writeFile(
    path.join(artifactDirectory, `${testInfo.project.name}-identity.json`),
    `${JSON.stringify(evidence, null, 2)}\n`,
  );
});
