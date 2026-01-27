import { test, expect } from '@playwright/test';

test('login and view dashboard without crash', async ({ page }) => {
  // Mock Keycloak login
  await page.route('**/protocol/openid-connect/token', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'mock-token-123' }),
    });
  });

  // Mock Documents API with the structure that was causing the crash
  await page.route('**/v1/documents*', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        documents: [], // Empty list inside an object
        total: 0,
        limit: 50,
        offset: 0
      }),
    });
  });

  // Go to login page
  await page.goto('/');

  // Fill credentials
  await page.getByPlaceholder('accountant').fill('accountant');
  await page.getByPlaceholder('••••••••').fill('accountant123');

  // Click Connect
  await page.getByRole('button', { name: 'Connect' }).click();

  // Wait for navigation and dashboard load
  // Should see "Inbox Chứng từ" if successful
  await expect(page.getByText('Inbox Chứng từ')).toBeVisible();

  // Ensure no error boundary text
  await expect(page.getByText('Something went wrong')).not.toBeVisible();
});
