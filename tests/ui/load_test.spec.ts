import { test, expect } from '@playwright/test';

/**
 * Load test — simulates concurrent browser users.
 *
 * Each user: Login → Search → Click doc → Interact → Load recommendations
 *
 * IMPORTANT: Run this separately from the main test suite:
 *   npx playwright test load_test.spec.ts
 */

const CONCURRENT_USERS = 50;
const API_URL = process.env.API_URL || 'http://localhost:8000';

test.describe('Load Test', () => {
    test('should handle 50 concurrent users', async () => {
        const results: Array<{
            userId: string;
            loginMs: number;
            searchMs: number;
            interactionMs: number;
            recommendationMs: number;
            success: boolean;
        }> = [];

        const userFn = async (i: number) => {
            const userId = `user-${String((i % 30) + 1).padStart(3, '0')}`;
            const t: Record<string, number> = {};
            let success = true;

            try {
                // Login
                let t0 = performance.now();
                const loginRes = await fetch(`${API_URL}/api/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId }),
                });
                t.login = performance.now() - t0;
                if (!loginRes.ok) success = false;

                // Search
                t0 = performance.now();
                const searchRes = await fetch(`${API_URL}/api/documents/search?q=machine+learning&limit=5`);
                t.search = performance.now() - t0;
                if (!searchRes.ok) success = false;

                // Interaction
                t0 = performance.now();
                const interRes = await fetch(`${API_URL}/interactions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-User-Id': userId },
                    body: JSON.stringify({
                        document_id: `doc-${String(Math.floor(Math.random() * 200) + 1).padStart(4, '0')}`,
                        interaction_type: 'view',
                    }),
                });
                t.interaction = performance.now() - t0;
                if (!interRes.ok) success = false;

                // Recommendations
                t0 = performance.now();
                const recRes = await fetch(`${API_URL}/recommendations?limit=5`, {
                    headers: { 'X-User-Id': userId },
                });
                t.recommendation = performance.now() - t0;
                if (!recRes.ok) success = false;

            } catch (e) {
                success = false;
            }

            return {
                userId,
                loginMs: t.login || 0,
                searchMs: t.search || 0,
                interactionMs: t.interaction || 0,
                recommendationMs: t.recommendation || 0,
                success,
            };
        };

        // Run all concurrent
        const promises = Array.from({ length: CONCURRENT_USERS }, (_, i) => userFn(i));
        const allResults = await Promise.all(promises);

        // Analyze results
        const successCount = allResults.filter(r => r.success).length;
        const avgLogin = allResults.reduce((s, r) => s + r.loginMs, 0) / allResults.length;
        const avgSearch = allResults.reduce((s, r) => s + r.searchMs, 0) / allResults.length;
        const avgInteraction = allResults.reduce((s, r) => s + r.interactionMs, 0) / allResults.length;
        const avgRecommendation = allResults.reduce((s, r) => s + r.recommendationMs, 0) / allResults.length;

        console.log(`\n📊 LOAD TEST RESULTS`);
        console.log(`══════════════════════════════════════`);
        console.log(`Concurrent Users: ${CONCURRENT_USERS}`);
        console.log(`Success: ${successCount}/${CONCURRENT_USERS}`);
        console.log(`Avg Login:          ${avgLogin.toFixed(0)}ms`);
        console.log(`Avg Search (ANN):   ${avgSearch.toFixed(0)}ms`);
        console.log(`Avg Interaction:    ${avgInteraction.toFixed(0)}ms`);
        console.log(`Avg Recommendation: ${avgRecommendation.toFixed(0)}ms`);
        console.log(`══════════════════════════════════════\n`);

        // Assertions
        expect(successCount).toBeGreaterThan(CONCURRENT_USERS * 0.9); // 90%+ success
        expect(avgSearch).toBeLessThan(10000); // under 10s average
        expect(avgRecommendation).toBeLessThan(10000);
    });
});
