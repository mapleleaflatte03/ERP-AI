import { test, expect, type Page } from '@playwright/test';

const stubApi = async (page: Page) => {
  await page.route('**/v1/**', async (route) => {
    const url = route.request().url();
    const fulfill = (body: Record<string, unknown>) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

    if (url.includes('/v1/copilot/chat')) {
      return fulfill({ response: 'Read-only response' });
    }
    if (url.includes('/v1/analytics/kpis')) {
      return fulfill({ metrics: {} });
    }
    if (url.includes('/v1/analytics/datasets')) {
      return fulfill({ datasets: [] });
    }
    if (url.includes('/v1/analytics/schema')) {
      return fulfill({ tables: [] });
    }
    if (url.includes('/v1/analytics/query')) {
      return fulfill({ results: { columns: [], rows: [] } });
    }
    if (url.includes('/v1/analytics/forecast')) {
      return fulfill({ results: [] });
    }
    if (url.includes('/v1/analytics/chat')) {
      return fulfill({ message: 'OK', session_id: 'smoke' });
    }
    if (url.includes('/v1/documents')) {
      return fulfill({ documents: [], total: 0 });
    }
    if (url.includes('/v1/approvals')) {
      return fulfill({ approvals: [], count: 0, pending: 0 });
    }
    if (url.includes('/v1/proposals')) {
      return fulfill({ proposals: [], count: 0 });
    }
    if (url.includes('/v1/analyze/reports')) {
      return fulfill({ reports: [] });
    }
    if (url.includes('/v1/analyze/datasets')) {
      return fulfill({ datasets: [] });
    }
    if (url.includes('/v1/analyze/query')) {
      return fulfill({ success: true, results: [], row_count: 0 });
    }
    return fulfill({});
  });
};

const openDockAndChat = async (page: Page) => {
  const dock = page.locator('.module-chat-dock').first();
  const fab = page.locator('.module-chat-fab').first();
  if (await fab.isVisible()) {
    await fab.click();
  }
  await expect(dock).toBeVisible();
  const input = dock.locator('.module-chat-input input');
  await input.fill('Xin chao');
  await input.press('Enter');
  await expect(dock).toContainText('Read-only response');
};

test.describe('E2E Smoke Tests - Module Chat', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('erpx_token', 'test-token');
    });
    await stubApi(page);
  });

  test('@smoke module pages open with chat dock and no console errors', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    page.on('pageerror', (err) => {
      consoleErrors.push(err.message);
    });

    await page.goto('/');
    await openDockAndChat(page);

    await page.goto('/proposals');
    await openDockAndChat(page);

    await page.goto('/approvals');
    await openDockAndChat(page);

    await page.goto('/analyze');
    await openDockAndChat(page);

    expect(consoleErrors, `Console errors: ${consoleErrors.join('\n')}`).toHaveLength(0);
  });
});
