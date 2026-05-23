import { test, expect, Page } from '@playwright/test';

// Test results tracking
const issues: Array<{category: string, title: string, description: string, severity: string}> = [];

test.describe('AgentOS Web UI E2E Tests', () => {
  let page: Page;
  const baseURL = 'http://localhost:3000';
  const apiURL = 'http://localhost:8000';

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
  });

  test.afterAll(async () => {
    await page?.close();
  });

  // Test 1: Home Page Load
  test('homepage should load successfully', async () => {
    const response = await page.goto(baseURL);
    expect(response?.status()).toBeLessThan(400);

    // Check page title
    const title = await page.title();
    console.log(`📄 Page Title: ${title}`);

    if (!title || title.toLowerCase().includes('localhost')) {
      issues.push({
        category: 'UI',
        title: 'Missing proper page title',
        description: 'Home page title is not set properly - shows localhost or empty',
        severity: 'low'
      });
    }
  });

  // Test 2: Navigation Elements
  test('navigation should be visible', async () => {
    await page.goto(baseURL);

    // Look for common navigation elements
    const nav = await page.locator('nav, header, [role="navigation"]').first();
    const isVisible = await nav.isVisible().catch(() => false);

    if (!isVisible) {
      issues.push({
        category: 'UI',
        title: 'Navigation not visible',
        description: 'Main navigation element is not visible on homepage',
        severity: 'high'
      });
    } else {
      console.log('✅ Navigation found');
    }
  });

  // Test 3: API Health Check
  test('API should respond healthily', async () => {
    try {
      const response = await page.request.get(`${apiURL}/health`);
      const status = response.status();

      if (status === 200) {
        console.log('✅ API health check passed');
      } else {
        issues.push({
          category: 'API',
          title: 'API health check failed',
          description: `API /health endpoint returned status ${status}`,
          severity: 'high'
        });
      }
    } catch (error) {
      issues.push({
        category: 'API',
        title: 'Cannot reach API',
        description: `Failed to reach API at ${apiURL}: ${error}`,
        severity: 'critical'
      });
    }
  });

  // Test 4: Responsive Design
  test('should be responsive on mobile', async () => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(baseURL);

    const bodyWidth = await page.locator('body').evaluate(el => el.offsetWidth);

    if (bodyWidth > 375) {
      issues.push({
        category: 'UI',
        title: 'Not responsive on mobile',
        description: `Body width ${bodyWidth}px exceeds viewport width 375px`,
        severity: 'medium'
      });
    } else {
      console.log('✅ Mobile responsive design OK');
    }

    // Reset to desktop
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  // Test 5: Agents List Page
  test('agents list should be accessible', async () => {
    await page.goto(baseURL);

    // Try to find agents link
    const agentsLink = await page.locator('a, [role="button"]').filter({hasText: /agents?/i}).first();

    if (await agentsLink.isVisible()) {
      await agentsLink.click();
      // Wait for navigation
      await page.waitForTimeout(1000);

      const url = page.url();
      if (!url.includes('agent')) {
        issues.push({
          category: 'Navigation',
          title: 'Agents page not properly routed',
          description: 'Clicking agents link did not navigate to agents page',
          severity: 'medium'
        });
      } else {
        console.log('✅ Agents page accessible');
      }
    } else {
      issues.push({
        category: 'Navigation',
        title: 'Agents link not found',
        description: 'Could not find agents navigation link on homepage',
        severity: 'high'
      });
    }
  });

  // Test 6: Console Errors
  test('should not have critical console errors', async () => {
    const errors: Array<{type: string, message: string}> = [];

    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push({
          type: msg.type(),
          message: msg.text()
        });
      }
    });

    await page.goto(baseURL);
    await page.waitForTimeout(2000);

    // Filter out known safe errors
    const criticalErrors = errors.filter(e =>
      !e.message.includes('sockjs') &&
      !e.message.includes('Failed to load resource')
    );

    if (criticalErrors.length > 0) {
      issues.push({
        category: 'Error Handling',
        title: `${criticalErrors.length} console errors detected`,
        description: `Found console errors: ${criticalErrors.map(e => e.message).join(', ')}`,
        severity: 'medium'
      });
    } else {
      console.log('✅ No critical console errors');
    }
  });

  // Test 7: Performance
  test('initial page load should be reasonably fast', async () => {
    const startTime = Date.now();
    await page.goto(baseURL);
    const loadTime = Date.now() - startTime;

    console.log(`⏱️ Page load time: ${loadTime}ms`);

    if (loadTime > 5000) {
      issues.push({
        category: 'Performance',
        title: 'Slow page load',
        description: `Page took ${loadTime}ms to load (>5s threshold)`,
        severity: 'medium'
      });
    }
  });

  // Test 8: Accessibility
  test('should have basic accessibility features', async () => {
    await page.goto(baseURL);

    const headings = await page.locator('h1, h2, h3').count();

    if (headings === 0) {
      issues.push({
        category: 'Accessibility',
        title: 'Missing heading structure',
        description: 'Page has no proper heading hierarchy (h1-h3)',
        severity: 'low'
      });
    }

    const images = await page.locator('img[alt]').count();
    const imagesWithoutAlt = (await page.locator('img').count()) - images;

    if (imagesWithoutAlt > 0) {
      issues.push({
        category: 'Accessibility',
        title: `${imagesWithoutAlt} images missing alt text`,
        description: `Found ${imagesWithoutAlt} images without alternative text`,
        severity: 'low'
      });
    }
  });

  // Test 9: Dark Mode (if exists)
  test('should support theme switching', async () => {
    await page.goto(baseURL);

    const themeButton = await page.locator('[aria-label*="theme"], [aria-label*="dark"], [aria-label*="light"]').first();

    if (await themeButton.isVisible()) {
      console.log('✅ Theme switcher found');
    } else {
      // Not critical, just informational
      console.log('ℹ️ No theme switcher found');
    }
  });

  // Test 10: Error Messages Display
  test('error handling should show user-friendly messages', async () => {
    await page.goto(baseURL);

    // Try to trigger an error by accessing non-existent page
    await page.goto(`${baseURL}/nonexistent`, { waitUntil: 'networkidle' }).catch(() => {});

    const errorText = await page.locator('body').textContent();

    if (errorText?.includes('Cannot') || errorText?.includes('404')) {
      console.log('✅ Error handling works');
    } else {
      issues.push({
        category: 'Error Handling',
        title: 'Poor 404 error message',
        description: 'Non-existent pages do not display friendly error messages',
        severity: 'low'
      });
    }
  });
});

// Export issues for external processing
export { issues };
