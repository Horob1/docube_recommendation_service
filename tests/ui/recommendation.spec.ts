import { test, expect } from '@playwright/test';
import { getRecommendations } from './helpers/api-helper';

test.describe('Recommendation Flow', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill('user-001');
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');
    });

    test('should display recommendation section on dashboard', async ({ page }) => {
        await expect(page.getByTestId('rec-title')).toBeVisible();
        await expect(page.getByTestId('rec-list')).toBeVisible({ timeout: 30000 });
    });

    test('should show personalized recommendations with scores', async ({ page }) => {
        await expect(page.getByTestId('rec-list')).toBeVisible({ timeout: 30000 });

        const items = page.getByTestId('rec-list').locator('[data-testid^="rec-item-"]');
        const count = await items.count();
        expect(count).toBeGreaterThan(0);

        // Each should have a score badge
        const firstScore = await items.first().locator('.score-badge').textContent();
        expect(parseFloat(firstScore || '0')).toBeGreaterThan(0);
    });

    test('should show A/B group info', async ({ page }) => {
        await expect(page.getByTestId('rec-meta')).toBeVisible({ timeout: 30000 });

        const metaText = await page.getByTestId('rec-meta').textContent();
        expect(metaText).toMatch(/Group [AB]/);
    });

    test('should not contain recently interacted documents (backend check)', async () => {
        // Record interaction with doc-0001
        const API = process.env.API_URL || 'http://localhost:8000';
        await fetch(`${API}/interactions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-User-Id': 'user-001' },
            body: JSON.stringify({ document_id: 'doc-0001', interaction_type: 'view' }),
        });

        // Get fresh recommendations
        const result = await getRecommendations('user-001');
        const docIds = result.data.recommendations.map((r: any) => r.document_id);

        // doc-0001 should be excluded (recently interacted)
        expect(docIds).not.toContain('doc-0001');
    });

    test('should show recommendations sorted by score (decreasing)', async ({ page }) => {
        await expect(page.getByTestId('rec-list')).toBeVisible({ timeout: 30000 });

        const scores = await page.getByTestId('rec-list').locator('.score-badge').allTextContents();
        const numScores = scores.map(s => parseFloat(s));

        // Verify decreasing order
        for (let i = 1; i < numScores.length; i++) {
            expect(numScores[i]).toBeLessThanOrEqual(numScores[i - 1]);
        }
    });

    test('should refresh recommendations via button', async ({ page }) => {
        await expect(page.getByTestId('rec-list')).toBeVisible({ timeout: 30000 });

        await page.getByTestId('refresh-recs').click();
        await page.waitForTimeout(2000);

        await expect(page.getByTestId('rec-list')).toBeVisible();
    });
});
