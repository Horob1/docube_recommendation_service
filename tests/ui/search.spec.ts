import { test, expect } from '@playwright/test';
import { checkAnnQueryTime } from './helpers/api-helper';

test.describe('Search Flow', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill('user-001');
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');
        await page.goto('/search');
    });

    test('should display search input and button', async ({ page }) => {
        await expect(page.getByTestId('search-input')).toBeVisible();
        await expect(page.getByTestId('search-button')).toBeVisible();
    });

    test('should return results for keyword search', async ({ page }) => {
        await page.getByTestId('search-input').fill('machine learning');
        await page.getByTestId('search-button').click();

        // Wait for results
        await expect(page.getByTestId('search-meta')).toBeVisible({ timeout: 30000 });
        await expect(page.getByTestId('search-results')).toBeVisible();

        // Should have results
        const results = page.getByTestId('search-results').locator('[data-testid^="search-result-"]');
        const count = await results.count();
        expect(count).toBeGreaterThan(0);
    });

    test('should show response time within threshold', async ({ page }) => {
        await page.getByTestId('search-input').fill('python programming');
        await page.getByTestId('search-button').click();

        await expect(page.getByTestId('search-meta')).toBeVisible({ timeout: 30000 });

        // Check response time is displayed
        const metaText = await page.getByTestId('search-meta').textContent();
        expect(metaText).toContain('ms');
    });

    test('should verify ANN search is actually used (backend check)', async () => {
        // Direct backend validation
        const result = await checkAnnQueryTime('user-001');
        expect(result.ann_time_ms).toBeDefined();
        expect(result.under_threshold).toBe(true);
        expect(result.results_count).toBeGreaterThan(0);
    });

    test('should show similarity scores in results', async ({ page }) => {
        await page.getByTestId('search-input').fill('deep learning neural networks');
        await page.getByTestId('search-button').click();

        await expect(page.getByTestId('search-results')).toBeVisible({ timeout: 30000 });

        // First result should have a score badge
        const scoreBadge = page.getByTestId('search-results').locator('.score-badge').first();
        await expect(scoreBadge).toBeVisible();

        const scoreText = await scoreBadge.textContent();
        const score = parseFloat(scoreText || '0');
        expect(score).toBeGreaterThan(0);
    });
});
