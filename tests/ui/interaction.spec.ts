import { test, expect } from '@playwright/test';
import { checkInteractionCount, checkPopularity } from './helpers/api-helper';

test.describe('Interaction Flow', () => {
    const TEST_USER = 'user-005';
    const TEST_DOC = 'doc-0010';

    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill(TEST_USER);
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');
    });

    test('should open document detail page', async ({ page }) => {
        await page.goto(`/documents/${TEST_DOC}`);
        await expect(page.getByTestId('document-detail')).toBeVisible();
        await expect(page.getByTestId('doc-title')).toBeVisible();
        await expect(page.getByTestId('doc-content')).toBeVisible();
    });

    test('should display all interaction buttons', async ({ page }) => {
        await page.goto(`/documents/${TEST_DOC}`);

        await expect(page.getByTestId('btn-view')).toBeVisible();
        await expect(page.getByTestId('btn-download')).toBeVisible();
        await expect(page.getByTestId('btn-bookmark')).toBeVisible();
        await expect(page.getByTestId('btn-buy')).toBeVisible();
    });

    test('should record bookmark interaction and show feedback', async ({ page }) => {
        // Get initial count
        const before = await checkInteractionCount(TEST_USER);

        await page.goto(`/documents/${TEST_DOC}`);
        await page.waitForTimeout(1000); // wait for auto-view to complete

        // Click bookmark
        await page.getByTestId('btn-bookmark').click();

        // Should show feedback
        await expect(page.getByTestId('interaction-feedback')).toContainText('recorded');

        // Button should be active
        await expect(page.getByTestId('btn-bookmark')).toHaveClass(/active/);

        // Verify DB insert
        const after = await checkInteractionCount(TEST_USER);
        expect(after.count).toBeGreaterThan(before.count);
    });

    test('should record buy interaction and increase popularity', async ({ page }) => {
        const popBefore = await checkPopularity(TEST_DOC);

        await page.goto(`/documents/${TEST_DOC}`);
        await page.waitForTimeout(1000);

        await page.getByTestId('btn-buy').click();
        await expect(page.getByTestId('interaction-feedback')).toContainText('recorded');

        // Verify popularity increased
        await page.waitForTimeout(500);
        const popAfter = await checkPopularity(TEST_DOC);
        expect(popAfter.popularity_score).toBeGreaterThan(popBefore.popularity_score);
    });

    test('should update UI state for multiple interactions', async ({ page }) => {
        await page.goto(`/documents/${TEST_DOC}`);
        await page.waitForTimeout(1000);

        // Click view
        await page.getByTestId('btn-view').click();
        await page.waitForTimeout(500);

        // Click download
        await page.getByTestId('btn-download').click();
        await page.waitForTimeout(500);

        // Both should be active
        await expect(page.getByTestId('btn-view')).toHaveClass(/active/);
        await expect(page.getByTestId('btn-download')).toHaveClass(/active/);
    });
});
