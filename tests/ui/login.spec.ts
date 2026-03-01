import { test, expect } from '@playwright/test';

test.describe('Login Flow', () => {
    test('should display login page with user list', async ({ page }) => {
        await page.goto('/login');
        await expect(page.getByTestId('user-select')).toBeVisible();
        await expect(page.getByTestId('login-button')).toBeVisible();
    });

    test('should login with selected user and redirect to dashboard', async ({ page }) => {
        await page.goto('/login');

        // Select a user from dropdown
        await page.getByTestId('user-select').selectOption({ index: 1 });
        await page.getByTestId('login-button').click();

        // Should redirect to dashboard
        await page.waitForURL('/');
        await expect(page.getByTestId('doc-list-title')).toBeVisible();
        await expect(page.getByTestId('user-badge')).toContainText('user-');
    });

    test('should login with manual user ID input', async ({ page }) => {
        await page.goto('/login');

        await page.getByTestId('user-id-input').fill('user-001');
        await page.getByTestId('login-button').click();

        await page.waitForURL('/');
        await expect(page.getByTestId('user-badge')).toContainText('user-001');
    });

    test('should persist login across page navigation', async ({ page }) => {
        await page.goto('/login');
        await page.getByTestId('user-id-input').fill('user-001');
        await page.getByTestId('login-button').click();
        await page.waitForURL('/');

        // Navigate to search
        await page.goto('/search');
        await expect(page).toHaveURL('/search');
        // Should not redirect to login
    });
});
