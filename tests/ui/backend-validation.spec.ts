import { test, expect } from '@playwright/test';
import { checkEmbeddingDim, checkIvflatIndex } from './helpers/api-helper';

test.describe('Backend Validation', () => {
    test('should have embedding dimension = 384', async () => {
        const result = await checkEmbeddingDim();
        expect(result.dimension).toBe(384);
        expect(result.match).toBe(true);
    });

    test('should have IVFFLAT index on documents.embedding', async () => {
        const result = await checkIvflatIndex();
        expect(result.exists).toBe(true);
        expect(result.indexes.length).toBeGreaterThan(0);

        // Check index definition contains IVFFLAT
        const def = result.indexes[0].definition;
        expect(def.toLowerCase()).toContain('ivfflat');
    });

    test('should verify all checks pass on Admin page', async ({ page }) => {
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill('user-001');
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');

        await page.goto('/admin');

        // Wait for data to load
        await expect(page.getByTestId('health-stats')).toBeVisible({ timeout: 30000 });
        await expect(page.getByTestId('validation-section')).toBeVisible();

        // Check embedding dimension
        const embCheck = page.getByTestId('check-embedding-dim');
        await expect(embCheck).toContainText('PASS');

        // Check IVFFLAT index
        const ivfCheck = page.getByTestId('check-ivfflat');
        await expect(ivfCheck).toContainText('PASS');

        // Check ANN query time
        const annCheck = page.getByTestId('check-ann-time');
        await expect(annCheck).toContainText('PASS');
    });
});
