import { test, expect } from '@playwright/test';
import { getRecommendations, checkCacheTtl } from './helpers/api-helper';

test.describe('Cache Behavior', () => {
    const TEST_USER = 'user-010';

    test('should cache recommendations after first request', async () => {
        // Force fresh by making an interaction first
        const API = process.env.API_URL || 'http://localhost:8000';
        await fetch(`${API}/interactions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-User-Id': TEST_USER },
            body: JSON.stringify({ document_id: 'doc-0050', interaction_type: 'view' }),
        });

        // First request — should be fresh
        const t0 = performance.now();
        const first = await getRecommendations(TEST_USER);
        const firstTime = performance.now() - t0;
        expect(first.data.cached).toBe(false);

        // Second request — should be cached
        const t1 = performance.now();
        const second = await getRecommendations(TEST_USER);
        const secondTime = performance.now() - t1;
        expect(second.data.cached).toBe(true);
    });

    test('should show cached status on dashboard UI', async ({ page }) => {
        // Login
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill(TEST_USER);
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');

        // Wait for recommendations to load
        await expect(page.getByTestId('rec-meta')).toBeVisible({ timeout: 30000 });

        // Refresh — should show cached
        await page.getByTestId('refresh-recs').click();
        await page.waitForTimeout(2000);

        const meta = await page.getByTestId('rec-meta').textContent();
        expect(meta).toContain('Cached');
    });

    test('should have valid Redis TTL (backend check)', async () => {
        // Ensure cached first
        await getRecommendations(TEST_USER);

        const ttl = await checkCacheTtl(TEST_USER);
        expect(ttl.exists).toBe(true);
        expect(ttl.ttl_seconds).toBeGreaterThan(0);
        expect(ttl.ttl_seconds).toBeLessThanOrEqual(600);
    });
});
