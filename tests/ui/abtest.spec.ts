import { test, expect } from '@playwright/test';
import { getRecommendations, getUserAbGroup } from './helpers/api-helper';

test.describe('A/B Testing', () => {
    test('should assign users to different A/B groups (backend check)', async () => {
        const groupA = await getUserAbGroup('user-001');
        const groupB = await getUserAbGroup('user-002');

        expect(groupA.ab_group).toBeDefined();
        expect(groupB.ab_group).toBeDefined();
        // They should be in different groups (seeded alternating)
        expect(groupA.ab_group).not.toEqual(groupB.ab_group);
    });

    test('should show different A/B group labels on dashboard', async ({ page }) => {
        // Login as user-001 (Group A)
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill('user-001');
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');

        await expect(page.getByTestId('rec-meta')).toBeVisible({ timeout: 30000 });
        const metaA = await page.getByTestId('rec-meta').textContent();

        // Login as user-002 (Group B)
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill('user-002');
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');

        await expect(page.getByTestId('rec-meta')).toBeVisible({ timeout: 30000 });
        const metaB = await page.getByTestId('rec-meta').textContent();

        // Different groups
        expect(metaA).toContain('Group A');
        expect(metaB).toContain('Group B');
    });

    test('should produce different recommendation orders for different groups', async () => {
        const recsA = await getRecommendations('user-001', 10);
        const recsB = await getRecommendations('user-002', 10);

        expect(recsA.data.ab_group).toBe('A');
        expect(recsB.data.ab_group).toBe('B');

        // Different users with different groups should get different recommendations
        const idsA = recsA.data.recommendations.map((r: any) => r.document_id);
        const idsB = recsB.data.recommendations.map((r: any) => r.document_id);

        // At least some differences (different interests + different A/B weights)
        const overlap = idsA.filter((id: string) => idsB.includes(id));
        expect(overlap.length).toBeLessThan(idsA.length);
    });
});
