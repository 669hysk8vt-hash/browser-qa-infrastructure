const fs = require('node:fs/promises');
const path = require('node:path');
const { test, expect } = require('@playwright/test');
const { PDFDocument } = require('pdf-lib');

const artifactDirectory = path.resolve(__dirname, '../../artifacts/self-test');
const selfTestUrl = 'http://127.0.0.1:4173/self-test.html';
const printSelfTestUrl = 'http://127.0.0.1:4173/print-self-test.html';
const a4SizeInPoints = { width: 595.28, height: 841.89 };
const a4ToleranceInPoints = 2;
const indexedDbSelfTest = {
  databaseName: 'browser-qa-self-test',
  objectStoreName: 'records',
  key: 'persistence-record',
  record: {
    marker: 'browser-qa-indexeddb-persistence',
    value: 90210,
  },
};

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

async function deleteSelfTestDatabase(page) {
  return page.evaluate(async ({ databaseName }) => {
    await new Promise((resolve, reject) => {
      const request = window.indexedDB.deleteDatabase(databaseName);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error(`Deletion of ${databaseName} was blocked.`));
    });
    return true;
  }, indexedDbSelfTest);
}

async function writeAndImmediatelyReadSelfTestRecord(page) {
  return page.evaluate(async ({ databaseName, objectStoreName, key, record }) => {
    const database = await new Promise((resolve, reject) => {
      const request = window.indexedDB.open(databaseName, 1);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(objectStoreName)) {
          request.result.createObjectStore(objectStoreName);
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error(`Opening ${databaseName} was blocked.`));
    });

    try {
      await new Promise((resolve, reject) => {
        const transaction = database.transaction(objectStoreName, 'readwrite');
        const request = transaction.objectStore(objectStoreName).put(record, key);
        request.onerror = () => reject(request.error);
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error || new Error('IndexedDB write aborted.'));
      });

      const immediateRead = await new Promise((resolve, reject) => {
        const transaction = database.transaction(objectStoreName, 'readonly');
        const request = transaction.objectStore(objectStoreName).get(key);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      return { writeSucceeded: true, immediateRead };
    } finally {
      database.close();
    }
  }, indexedDbSelfTest);
}

async function readSelfTestRecord(page) {
  return page.evaluate(async ({ databaseName, objectStoreName, key }) => {
    const database = await new Promise((resolve, reject) => {
      const request = window.indexedDB.open(databaseName);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      request.onblocked = () => reject(new Error(`Reopening ${databaseName} was blocked.`));
    });

    try {
      return await new Promise((resolve, reject) => {
        const transaction = database.transaction(objectStoreName, 'readonly');
        const request = transaction.objectStore(objectStoreName).get(key);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
    } finally {
      database.close();
    }
  }, indexedDbSelfTest);
}

test('configured branded browser passes the infrastructure self-test', async ({
  browser,
  page,
}, testInfo) => {
  const expected = expectedBrowsers[testInfo.project.name];
  expect(expected, `Unexpected Playwright project: ${testInfo.project.name}`).toBeTruthy();

  const navigationResponse = await page.goto(selfTestUrl);
  expect(navigationResponse).not.toBeNull();
  expect(navigationResponse.status()).toBe(200);
  expect(page.url()).toBe(selfTestUrl);
  expect(new URL(page.url()).origin).toBe('http://127.0.0.1:4173');
  expect(page.url()).not.toMatch(/^file:/);
  await expect(page).toHaveTitle('Browser QA self-test');
  await expect(page.getByRole('heading', { name: 'Browser QA self-test' })).toBeVisible();
  await expect(page.locator('#javascript-status')).toHaveText('JavaScript executed.');
  await expect
    .poll(() => page.evaluate(() => window.browserQaSelfTest))
    .toEqual({ marker: 'browser-qa-javascript-executed', executed: true });

  let indexedDbEvidence;
  expect(await page.evaluate(() => typeof window.indexedDB !== 'undefined')).toBe(true);
  try {
    expect(await deleteSelfTestDatabase(page)).toBe(true);

    const initialResult = await writeAndImmediatelyReadSelfTestRecord(page);
    expect(initialResult.writeSucceeded).toBe(true);
    expect(initialResult.immediateRead).toEqual(indexedDbSelfTest.record);

    const reloadResponse = await page.reload();
    expect(reloadResponse, 'The self-test page reload did not return a response.').not.toBeNull();
    expect(reloadResponse.status()).toBe(200);
    await expect(page).toHaveTitle('Browser QA self-test');

    const persistedRecord = await readSelfTestRecord(page);
    expect(persistedRecord).toEqual(indexedDbSelfTest.record);
    indexedDbEvidence = {
      project: testInfo.project.name,
      databaseName: indexedDbSelfTest.databaseName,
      objectStoreName: indexedDbSelfTest.objectStoreName,
      key: indexedDbSelfTest.key,
      written: indexedDbSelfTest.record,
      readAfterReload: persistedRecord,
      persistenceVerified: true,
      pageOrigin: new URL(page.url()).origin,
    };
  } finally {
    if (!page.isClosed()) {
      await deleteSelfTestDatabase(page);
    }
  }

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
  await fs.writeFile(
    path.join(artifactDirectory, `${testInfo.project.name}-indexeddb.json`),
    `${JSON.stringify(indexedDbEvidence, null, 2)}\n`,
  );
});

test('configured branded browser generates a valid one-page A4 PDF', async ({
  browser,
  page,
}, testInfo) => {
  expect(expectedBrowsers[testInfo.project.name], `Unexpected Playwright project: ${testInfo.project.name}`).toBeTruthy();

  const navigationResponse = await page.goto(printSelfTestUrl);
  expect(navigationResponse, 'The print self-test navigation did not return a response.').not.toBeNull();
  expect(navigationResponse.status()).toBe(200);
  expect(page.url()).toBe(printSelfTestUrl);
  expect(new URL(page.url()).origin).toBe('http://127.0.0.1:4173');
  await expect(page).toHaveTitle('Browser QA print self-test');
  await expect(page.getByRole('heading', { name: 'Browser QA print self-test' })).toBeVisible();

  await page.emulateMedia({ media: 'print' });
  const printMarker = page.locator('#print-only-marker');
  await expect(printMarker).toBeVisible();
  await expect(printMarker).toHaveCSS('display', 'block');
  await expect(printMarker).toHaveCSS('color', 'rgb(36, 87, 166)');

  await fs.mkdir(artifactDirectory, { recursive: true });
  const pdfPath = path.join(artifactDirectory, `${testInfo.project.name}-print.pdf`);
  const pdfBuffer = await page.pdf({
    path: pdfPath,
    format: 'A4',
    landscape: false,
    printBackground: true,
    preferCSSPageSize: true,
    scale: 1,
  });
  expect(pdfBuffer.length).toBeGreaterThan(1_000);

  const pdfDocument = await PDFDocument.load(pdfBuffer);
  const pageCount = pdfDocument.getPageCount();
  expect(pageCount).toBe(1);
  const { width, height } = pdfDocument.getPage(0).getSize();
  expect(height).toBeGreaterThan(width);
  expect(Math.abs(width - a4SizeInPoints.width)).toBeLessThanOrEqual(a4ToleranceInPoints);
  expect(Math.abs(height - a4SizeInPoints.height)).toBeLessThanOrEqual(a4ToleranceInPoints);

  const evidence = {
    project: testInfo.project.name,
    browserVersion: browser.version(),
    sourceUrl: page.url(),
    pageCount,
    expectedPageCount: 1,
    pdfPageWidth: width,
    pdfPageHeight: height,
    orientation: 'portrait',
    printMediaVerified: true,
    pdfFileSize: pdfBuffer.length,
    pdfPath: `artifacts/self-test/${testInfo.project.name}-print.pdf`,
    pdfGenerationVerified: true,
  };
  await fs.writeFile(
    path.join(artifactDirectory, `${testInfo.project.name}-print.json`),
    `${JSON.stringify(evidence, null, 2)}\n`,
  );
});
