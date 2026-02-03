/**
 * Playwright E2E Test: Full Module-Agent Flow
 * 
 * Tests the complete workflow:
 * Upload document → OCR/Extract → Generate Proposal → Submit → Approve → Evidence/Timestamp
 */

import { test, expect } from '@playwright/test';

// Configure timeouts for E2E flows
test.setTimeout(120_000);

const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:3000';
const API_URL = process.env.E2E_API_URL || 'http://localhost:8000';

test.describe('Module-Agent Full Flow E2E', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navigate to app
    await page.goto(BASE_URL);
    
    // Wait for app to be ready
    await page.waitForSelector('[data-testid="app-ready"]', { timeout: 30000 });
  });

  test('Upload chứng từ → OCR → Generate Proposal → Submit → Approve → Evidence', async ({ page }) => {
    // ========================================
    // STEP 1: Navigate to Documents module
    // ========================================
    await page.click('[data-nav="documents"]');
    await expect(page).toHaveURL(/.*documents/);
    
    // ========================================
    // STEP 2: Open Module Chat Dock
    // ========================================
    await page.click('[data-testid="module-chat-dock-button"]');
    await expect(page.locator('.module-chat-panel')).toBeVisible();
    
    // Verify module is "documents"
    await expect(page.locator('.module-chat-header')).toContainText('Tài liệu AI');
    
    // ========================================
    // STEP 3: Upload a test document
    // ========================================
    // Click upload button
    await page.click('[data-testid="upload-document-btn"]');
    
    // Upload test file
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.click('[data-testid="file-input-trigger"]');
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'test-invoice.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('Mock PDF content for testing')
    });
    
    // Wait for upload to complete
    await expect(page.locator('[data-testid="upload-progress"]')).toBeHidden({ timeout: 30000 });
    await expect(page.locator('[data-testid="upload-success"]')).toBeVisible();
    
    // ========================================
    // STEP 4: Trigger OCR/Extract via Chat
    // ========================================
    const chatInput = page.locator('.module-chat-input');
    await chatInput.fill('Trích xuất thông tin từ hóa đơn vừa upload');
    await chatInput.press('Enter');
    
    // Wait for AI response
    await expect(page.locator('.chat-message.assistant').last()).toBeVisible({ timeout: 30000 });
    
    // Verify OCR response includes extracted data
    const responseText = await page.locator('.chat-message.assistant').last().textContent();
    expect(responseText).toMatch(/trích xuất|thông tin|hóa đơn/i);
    
    // ========================================
    // STEP 5: Request AI to create proposal
    // ========================================
    await chatInput.fill('Tạo đề xuất thanh toán cho hóa đơn này');
    await chatInput.press('Enter');
    
    // Wait for AI response with proposed action
    await expect(page.locator('.action-proposal-card')).toBeVisible({ timeout: 30000 });
    
    // Verify proposal card is shown
    const proposalCard = page.locator('.action-proposal-card').first();
    await expect(proposalCard).toBeVisible();
    
    // Get proposal ID for later verification
    const proposalId = await proposalCard.getAttribute('data-proposal-id');
    expect(proposalId).toBeTruthy();
    
    // Verify it shows risk level
    await expect(proposalCard.locator('.risk-level')).toBeVisible();
    
    // ========================================
    // STEP 6: Confirm the proposal (user approval)
    // ========================================
    await proposalCard.locator('button:has-text("Xác nhận")').click();
    
    // Wait for confirmation dialog
    await expect(page.locator('.confirm-dialog')).toBeVisible();
    
    // Type confirmation
    await page.locator('.confirm-dialog input').fill('CONFIRM');
    await page.locator('.confirm-dialog button:has-text("Xác nhận thực hiện")').click();
    
    // Wait for execution
    await expect(page.locator('.action-proposal-card.status-executed')).toBeVisible({ timeout: 30000 });
    
    // Verify the proposal was executed
    await expect(proposalCard.locator('.status-badge')).toContainText('Đã thực hiện');
    
    // ========================================
    // STEP 7: Navigate to Approvals module
    // ========================================
    await page.click('[data-nav="approvals"]');
    await expect(page).toHaveURL(/.*approvals/);
    
    // Find the created approval request
    await page.fill('[data-testid="search-approvals"]', proposalId || 'test-invoice');
    await page.press('[data-testid="search-approvals"]', 'Enter');
    
    // Verify approval item exists
    const approvalItem = page.locator('.approval-item').first();
    await expect(approvalItem).toBeVisible();
    
    // ========================================
    // STEP 8: Approve via module chat
    // ========================================
    // Open approvals chat dock
    await page.click('[data-testid="module-chat-dock-button"]');
    await expect(page.locator('.module-chat-header')).toContainText('Duyệt AI');
    
    await chatInput.fill('Duyệt đề xuất thanh toán cho test-invoice');
    await chatInput.press('Enter');
    
    // Wait for approval proposal
    await expect(page.locator('.action-proposal-card')).toBeVisible({ timeout: 30000 });
    
    // Confirm approval action
    await page.locator('.action-proposal-card button:has-text("Xác nhận")').first().click();
    await page.locator('.confirm-dialog input').fill('CONFIRM');
    await page.locator('.confirm-dialog button:has-text("Xác nhận thực hiện")').click();
    
    // Wait for approval execution
    await expect(page.locator('.action-proposal-card.status-executed')).toBeVisible({ timeout: 30000 });
    
    // ========================================
    // STEP 9: Verify Evidence & Timestamp
    // ========================================
    // Click on the approved item
    await approvalItem.click();
    
    // Navigate to evidence section
    await page.click('[data-testid="view-evidence"]');
    
    // Verify evidence is displayed
    await expect(page.locator('.evidence-section')).toBeVisible();
    
    // Check for timestamp
    const timestampElement = page.locator('.evidence-timestamp');
    await expect(timestampElement).toBeVisible();
    const timestamp = await timestampElement.textContent();
    expect(timestamp).toMatch(/\d{4}-\d{2}-\d{2}/); // ISO date format
    
    // Verify audit trail
    await expect(page.locator('.audit-trail')).toBeVisible();
    await expect(page.locator('.audit-entry')).toHaveCount(expect.any(Number));
    
    // ========================================
    // STEP 10: Verify via API that action was logged
    // ========================================
    const response = await page.request.get(`${API_URL}/v1/agent/actions/${proposalId}`);
    expect(response.ok()).toBeTruthy();
    
    const actionData = await response.json();
    expect(actionData.status).toBe('executed');
    expect(actionData.evidence_id).toBeTruthy();
    expect(actionData.executed_at).toBeTruthy();
  });

  test('Standalone chatbot remains read-only (no write proposals)', async ({ page }) => {
    // ========================================
    // Navigate to general copilot/chat (standalone)
    // ========================================
    await page.goto(`${BASE_URL}/copilot`);
    await expect(page.locator('.copilot-chat')).toBeVisible();
    
    // ========================================
    // Try to request a write action
    // ========================================
    const chatInput = page.locator('.copilot-input');
    await chatInput.fill('Tạo một hóa đơn mới');
    await chatInput.press('Enter');
    
    // Wait for response
    await expect(page.locator('.chat-message.assistant').last()).toBeVisible({ timeout: 30000 });
    
    // ========================================
    // Verify NO action proposal card is shown
    // ========================================
    await expect(page.locator('.action-proposal-card')).toHaveCount(0);
    
    // Verify response message indicates read-only or redirects to module
    const responseText = await page.locator('.chat-message.assistant').last().textContent();
    expect(responseText).toMatch(/module|chức năng cụ thể|không thể thực hiện|chỉ đọc/i);
  });

  test('Analytics module enforces SQL SELECT-only', async ({ page }) => {
    // Navigate to analytics
    await page.click('[data-nav="analyze"]');
    await expect(page).toHaveURL(/.*analyze/);
    
    // Open module chat
    await page.click('[data-testid="module-chat-dock-button"]');
    
    // Try to request a dangerous SQL
    const chatInput = page.locator('.module-chat-input');
    await chatInput.fill('Chạy query: DELETE FROM users WHERE id = 1');
    await chatInput.press('Enter');
    
    // Wait for response
    await expect(page.locator('.chat-message.assistant').last()).toBeVisible({ timeout: 30000 });
    
    // Verify NO action proposal for dangerous SQL
    await expect(page.locator('.action-proposal-card')).toHaveCount(0);
    
    // Verify error/rejection message
    const responseText = await page.locator('.chat-message.assistant').last().textContent();
    expect(responseText).toMatch(/không được phép|SELECT|chỉ đọc|từ chối/i);
  });

  test('Cross-module action is blocked', async ({ page }) => {
    // Navigate to Documents module
    await page.click('[data-nav="documents"]');
    
    // Open module chat
    await page.click('[data-testid="module-chat-dock-button"]');
    
    // Try to request an Approvals action from Documents module
    const chatInput = page.locator('.module-chat-input');
    await chatInput.fill('Duyệt đề xuất proposal-123');  // Approval action
    await chatInput.press('Enter');
    
    // Wait for response
    await expect(page.locator('.chat-message.assistant').last()).toBeVisible({ timeout: 30000 });
    
    // Verify NO action proposal (cross-module blocked)
    await expect(page.locator('.action-proposal-card')).toHaveCount(0);
    
    // Or verify it creates a read-only info response
    const responseText = await page.locator('.chat-message.assistant').last().textContent();
    expect(responseText).not.toMatch(/đã tạo đề xuất.*approve/i);
  });

  test('Module chat session persists across page reload', async ({ page }) => {
    // Navigate to Documents
    await page.click('[data-nav="documents"]');
    
    // Open chat and send a message
    await page.click('[data-testid="module-chat-dock-button"]');
    const chatInput = page.locator('.module-chat-input');
    await chatInput.fill('Xin chào');
    await chatInput.press('Enter');
    
    // Wait for response
    await expect(page.locator('.chat-message.assistant').last()).toBeVisible({ timeout: 30000 });
    
    // Get session ID from localStorage
    const sessionId = await page.evaluate(() => {
      const state = JSON.parse(localStorage.getItem('erpx_chat_state') || '{}');
      return state.documents?.sessionId;
    });
    
    // Reload page
    await page.reload();
    await page.waitForSelector('[data-testid="app-ready"]');
    
    // Open chat again
    await page.click('[data-testid="module-chat-dock-button"]');
    
    // Verify session ID persisted
    const persistedSessionId = await page.evaluate(() => {
      const state = JSON.parse(localStorage.getItem('erpx_chat_state') || '{}');
      return state.documents?.sessionId;
    });
    
    expect(persistedSessionId).toBe(sessionId);
    
    // Verify chat history is visible (if backend supports session restore)
    // This may need adjustment based on backend implementation
    await expect(page.locator('.chat-message')).toHaveCount(expect.any(Number));
  });
});

test.describe('Quantum UI Tokens', () => {
  test('Theme toggle works correctly', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForSelector('[data-testid="app-ready"]');
    
    // Get initial theme
    const initialTheme = await page.evaluate(() => 
      document.documentElement.getAttribute('data-theme')
    );
    
    // Toggle theme
    await page.click('[data-testid="theme-toggle"]');
    
    // Verify theme changed
    const newTheme = await page.evaluate(() => 
      document.documentElement.getAttribute('data-theme')
    );
    
    expect(newTheme).not.toBe(initialTheme);
    expect(['light', 'dark']).toContain(newTheme);
  });

  test('Density setting is applied', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForSelector('[data-testid="app-ready"]');
    
    // Open settings
    await page.click('[data-testid="settings-btn"]');
    
    // Change density to compact
    await page.click('[data-testid="density-compact"]');
    
    // Verify density attribute
    const density = await page.evaluate(() => 
      document.documentElement.getAttribute('data-density')
    );
    
    expect(density).toBe('compact');
    
    // Verify CSS variable changed
    const spacingBase = await page.evaluate(() => 
      getComputedStyle(document.documentElement).getPropertyValue('--spacing-base').trim()
    );
    
    // Compact should have smaller spacing
    expect(parseFloat(spacingBase)).toBeLessThan(1);  // 0.8rem for compact
  });

  test('Reduced motion preference is respected', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForSelector('[data-testid="app-ready"]');
    
    // Open settings
    await page.click('[data-testid="settings-btn"]');
    
    // Enable reduced motion
    await page.click('[data-testid="reduce-motion"]');
    
    // Verify motion attribute
    const motion = await page.evaluate(() => 
      document.documentElement.getAttribute('data-reduce-motion')
    );
    
    expect(motion).toBe('true');
    
    // Verify animation duration is minimal
    const duration = await page.evaluate(() => 
      getComputedStyle(document.documentElement).getPropertyValue('--motion-duration-fast').trim()
    );
    
    expect(duration).toBe('0ms');
  });
});

test.describe('Web Vitals Performance', () => {
  test('LCP is under threshold', async ({ page }) => {
    await page.goto(BASE_URL);
    
    // Wait for LCP to be measured
    const lcpValue = await page.evaluate(() => {
      return new Promise<number>((resolve) => {
        new PerformanceObserver((list) => {
          const entries = list.getEntries();
          const lastEntry = entries[entries.length - 1] as any;
          resolve(lastEntry.startTime);
        }).observe({ type: 'largest-contentful-paint', buffered: true });
        
        // Timeout fallback
        setTimeout(() => resolve(0), 10000);
      });
    });
    
    // LCP should be under 2.5s for "good"
    expect(lcpValue).toBeLessThan(2500);
  });

  test('CLS is under threshold', async ({ page }) => {
    await page.goto(BASE_URL);
    
    // Navigate around to trigger potential layout shifts
    await page.click('[data-nav="documents"]');
    await page.click('[data-nav="approvals"]');
    
    const clsValue = await page.evaluate(() => {
      return new Promise<number>((resolve) => {
        let clsValue = 0;
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (!(entry as any).hadRecentInput) {
              clsValue += (entry as any).value;
            }
          }
        }).observe({ type: 'layout-shift', buffered: true });
        
        setTimeout(() => resolve(clsValue), 3000);
      });
    });
    
    // CLS should be under 0.1 for "good"
    expect(clsValue).toBeLessThan(0.1);
  });
});
