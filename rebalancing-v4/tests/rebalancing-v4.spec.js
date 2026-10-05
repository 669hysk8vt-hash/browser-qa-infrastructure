const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

async function waitForApp(page) {
  await page.goto('/');
  await expect(page.getByText(/RETURN STACKING/i).first()).toBeVisible({ timeout: 60_000 });
  await expect(page.locator('[data-testid="stException"]')).toHaveCount(0);
}

async function setNumberInput(page, label, value) {
  const input = page.getByLabel(label, { exact: true });
  await expect(input).toBeVisible();
  await input.fill(String(value));
  await input.press('Enter');
}

test.describe('Return Stacking Engine v4 browser QA', () => {
  test('loads the complete Streamlit cockpit without runtime exceptions', async ({ page }, testInfo) => {
    await waitForApp(page);
    await expect(page.getByText(/v4\.0\.0/).first()).toBeVisible();
    for (const tab of ['Cockpit Operativo', 'Rischio & Stress', 'Traiettoria PAC', 'Overlay & Benchmark']) {
      await expect(page.getByRole('tab', { name: new RegExp(tab) })).toBeVisible();
    }
    await expect(page.getByRole('button', { name: /Aggiorna Quotazioni Yahoo/i })).toBeVisible();
    await expect(page.getByLabel('Target Oro %', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Target Trend %', { exact: true })).toBeVisible();

    const out = path.join(process.cwd(), '..', 'artifacts', 'rebalancing-v4');
    fs.mkdirSync(out, { recursive: true });
    await page.screenshot({ path: path.join(out, testInfo.project.name + '-cockpit.png'), fullPage: true });
  });

  test('applies 8% gold and 8% trend targets and preserves the app', async ({ page }) => {
    await waitForApp(page);
    await setNumberInput(page, 'Target Oro %', 8);
    await setNumberInput(page, 'Target Trend %', 8);
    await page.getByRole('button', { name: /Applica target/i }).click();
    await expect(page.getByText(/Target espliciti/i).first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/16\.0%/).first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Target Oro/i).first()).toBeVisible();
    await expect(page.getByText(/Target Trend/i).first()).toBeVisible();
    await expect(page.locator('[data-testid="stException"]')).toHaveCount(0);
  });

  test('produces a usable indicative order path with explicit stale-price override', async ({ page }) => {
    await waitForApp(page);
    await expect(page.getByText(/Cash finale/i).first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Distinta indicativa bloccata:/i)).toBeVisible({ timeout: 30_000 });
    const override = page.getByRole('checkbox', { name: /Override manuale: mostra comunque la distinta/i });
    await expect(override).toBeVisible({ timeout: 30_000 });
    await override.check();
    await expect(page.getByText(/Distinta Operativa Indicativa/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="stException"]')).toHaveCount(0);
  });

  test('Yahoo refresh executes through the real network path without crashing Streamlit', async ({ page }) => {
    await waitForApp(page);
    await page.getByRole('button', { name: /Aggiorna Quotazioni Yahoo/i }).click();
    await expect(page.getByText(/RETURN STACKING/i).first()).toBeVisible({ timeout: 150_000 });
    await expect(page.locator('[data-testid="stException"]')).toHaveCount(0);
    const body = await page.locator('body').innerText();
    expect(body).toMatch(/Yahoo|Aggiornamento parziale/);
  });

  test('risk engine downloads proxy history and renders quantitative outputs', async ({ page }) => {
    await waitForApp(page);
    await page.getByRole('tab', { name: /Rischio & Stress/i }).click();
    await expect(page.getByText(/VaR \/ Expected Shortfall/i)).toBeVisible({ timeout: 150_000 });
    await expect(page.getByText(/Risk data:/i)).toBeVisible({ timeout: 150_000 });
    await expect(page.getByText(/Historical VaR 95%/i)).toBeVisible();
    await expect(page.getByText(/Historical ES 95%/i)).toBeVisible();
    await expect(page.getByText(/Matrice stress modificabile/i)).toBeVisible();
    await expect(page.locator('[data-testid="stException"]')).toHaveCount(0);
  });

  test('PAC and overlay tabs render from the unified assumptions model', async ({ page }) => {
    await waitForApp(page);
    await page.getByRole('tab', { name: /Traiettoria PAC/i }).click();
    await expect(page.getByText(/Diluizione Legacy e PAC/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Core <50% NAV/i)).toBeVisible();
    await expect(page.getByText(/Stacking > Legacy/i)).toBeVisible();

    await page.getByRole('tab', { name: /Overlay & Benchmark/i }).click();
    await expect(page.getByText(/Overlay Contribution Sensitivity/i)).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText(/Benchmark coerenti con il modello/i)).toBeVisible();
    await expect(page.locator('[data-testid="stException"]')).toHaveCount(0);
  });

  test('configuration export produces a versioned JSON download', async ({ page }) => {
    await waitForApp(page);
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /Esporta configurazione/i }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/return_stacking_config_v2\.json/);
  });
});
