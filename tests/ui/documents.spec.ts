import { test, expect } from '@playwright/test';

test.describe('Document List', () => {
    test.beforeEach(async ({ page }) => {
        // Login first
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill('user-001');
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');
    });

    test('should load 20 documents on dashboard', async ({ page }) => {
        const grid = page.getByTestId('doc-grid');
        await expect(grid).toBeVisible();

        // Should have document cards
        const cards = grid.locator('[data-testid^="doc-card-"]');
        await expect(cards).toHaveCount(20);
    });

    test('should display pagination controls', async ({ page }) => {
        const pagination = page.getByTestId('pagination');
        await expect(pagination).toBeVisible();

        // Should have multiple page buttons
        const buttons = pagination.locator('[data-testid^="page-btn-"]');
        const count = await buttons.count();
        expect(count).toBeGreaterThan(1);
    });

    test('should navigate to page 2 and load different documents', async ({ page }) => {
        // Get first doc on page 1
        const firstDocPage1 = await page.getByTestId('doc-grid').locator('[data-testid^="doc-card-"]').first().getAttribute('data-testid');

        // Click page 2
        await page.getByTestId('page-btn-2').click();

        // Wait for new docs
        await page.waitForTimeout(1000);

        // First doc should be different
        const firstDocPage2 = await page.getByTestId('doc-grid').locator('[data-testid^="doc-card-"]').first().getAttribute('data-testid');
        expect(firstDocPage2).not.toBe(firstDocPage1);
    });

    test('should show document tags and metadata', async ({ page }) => {
        const firstCard = page.getByTestId('doc-grid').locator('.card').first();

        // Should have title
        await expect(firstCard.locator('.card-title')).toBeVisible();

        // Should have tags
        const tags = firstCard.locator('.tag');
        const tagCount = await tags.count();
        expect(tagCount).toBeGreaterThan(0);
    });
});
