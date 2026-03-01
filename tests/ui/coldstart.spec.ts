import { test, expect } from '@playwright/test';
import { getRecommendations } from './helpers/api-helper';

test.describe('Cold Start User', () => {
    test('should handle cold start user (no embedding) on dashboard', async ({ page }) => {
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill('user-cold-001');
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');

        // Should load without errors
        await expect(page.getByTestId('doc-list-title')).toBeVisible();

        // Recommendation section should be visible
        await expect(page.getByTestId('rec-title')).toBeVisible();

        // Should show recommendations (trending fallback)
        await expect(page.getByTestId('rec-list')).toBeVisible({ timeout: 30000 });

        const items = page.getByTestId('rec-list').locator('[data-testid^="rec-item-"]');
        const count = await items.count();
        expect(count).toBeGreaterThan(0);
    });

    test('should show trending documents for cold start (backend check)', async () => {
        const result = await getRecommendations('user-cold-001');

        expect(result.data.recommendations.length).toBeGreaterThan(0);

        // Should have "Trending" in reason for cold start
        const reasons = result.data.recommendations.map((r: any) => r.reason);
        const hasTrending = reasons.some((r: string) => r.includes('Trending'));
        expect(hasTrending).toBe(true);
    });

    test('should handle brand new user (auto-created)', async ({ page }) => {
        const newUser = `user-new-${Date.now()}`;

        await page.goto('/login');
        await page.getByTestId('user-id-input').fill(newUser);
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');

        // Should NOT error out
        await expect(page.getByTestId('doc-list-title')).toBeVisible();
        await expect(page.getByTestId('rec-title')).toBeVisible();
    });
});
