import { test, expect } from '@playwright/test';
import { getRecommendations } from './helpers/api-helper';

test.describe('Re-ranking', () => {
    const TEST_USER = 'user-003';

    test('should boost category after multiple interactions', async ({ page }) => {
        const API = process.env.API_URL || 'http://localhost:8000';

        // Record many interactions with ML-category documents
        const mlDocs = ['doc-0001', 'doc-0002', 'doc-0003', 'doc-0004', 'doc-0005'];
        for (const docId of mlDocs) {
            await fetch(`${API}/interactions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-User-Id': TEST_USER },
                body: JSON.stringify({ document_id: docId, interaction_type: 'bookmark' }),
            });
        }

        // Wait for processing
        await page.waitForTimeout(2000);

        // Login and check recommendations
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill(TEST_USER);
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');

        await expect(page.getByTestId('rec-list')).toBeVisible({ timeout: 30000 });

        // Recommendations should exist
        const items = page.getByTestId('rec-list').locator('[data-testid^="rec-item-"]');
        const count = await items.count();
        expect(count).toBeGreaterThan(0);
    });

    test('should change recommendation order after interactions (backend check)', async () => {
        const API = process.env.API_URL || 'http://localhost:8000';

        // Get recommendations before
        const before = await getRecommendations(TEST_USER);
        const idsBefore = before.data.recommendations.map((r: any) => r.document_id);

        // Record more interactions with specific category
        for (let i = 6; i <= 10; i++) {
            const docId = `doc-${String(i).padStart(4, '0')}`;
            await fetch(`${API}/interactions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-User-Id': TEST_USER },
                body: JSON.stringify({ document_id: docId, interaction_type: 'buy' }),
            });
        }

        await new Promise(r => setTimeout(r, 2000));

        // Get recommendations after
        const after = await getRecommendations(TEST_USER);
        const idsAfter = after.data.recommendations.map((r: any) => r.document_id);

        // Order should be different after interactions changed user embedding
        expect(idsAfter).not.toEqual(idsBefore);
    });
});
