/**
 * API helper for Playwright tests.
 * Calls the backend directly for DB/Redis/Kafka validation.
 */

const API_URL = process.env.API_URL || 'http://localhost:8000';

export async function apiGet(path: string) {
    const res = await fetch(`${API_URL}${path}`);
    return res.json();
}

export async function apiPost(path: string, body: any, userId?: string) {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (userId) headers['X-User-Id'] = userId;

    const res = await fetch(`${API_URL}${path}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
    });
    return { status: res.status, data: await res.json(), headers: res.headers };
}

// ── Validation Helpers ──────────────────────────────────────────────

export async function checkEmbeddingDim() {
    return apiGet('/api/validate/embedding-dim');
}

export async function checkIvflatIndex() {
    return apiGet('/api/validate/ivfflat-index');
}

export async function checkInteractionCount(userId: string) {
    return apiGet(`/api/validate/interaction-count?user_id=${userId}`);
}

export async function checkCacheTtl(userId: string) {
    return apiGet(`/api/validate/cache-ttl?user_id=${userId}`);
}

export async function checkAnnQueryTime(userId: string) {
    return apiGet(`/api/validate/ann-query-time?user_id=${userId}`);
}

export async function checkPopularity(docId: string) {
    return apiGet(`/api/validate/popularity?document_id=${docId}`);
}

export async function pushKafkaEvent(topic: string, eventType: string, extras: Record<string, string> = {}) {
    const params = new URLSearchParams({ topic, event_type: eventType, ...extras });
    const res = await fetch(`${API_URL}/api/validate/push-kafka-event?${params}`, { method: 'POST' });
    return res.json();
}

export async function getRecommendations(userId: string, limit = 10) {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'X-User-Id': userId,
    };
    const res = await fetch(`${API_URL}/recommendations?limit=${limit}`, { headers });
    return {
        status: res.status,
        data: await res.json(),
        cacheHit: res.headers.get('X-Cache-Hit'),
        annTimeMs: res.headers.get('X-ANN-Time-Ms'),
    };
}

export async function getUserAbGroup(userId: string) {
    return apiGet(`/api/validate/user-ab-group?user_id=${userId}`);
}
