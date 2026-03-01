'use client';
import { useState, useEffect } from 'react';
import { apiFetch } from '../../lib/api';

export default function LoginPage() {
    const [users, setUsers] = useState([]);
    const [userId, setUserId] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        apiFetch('/api/auth/users').then(r => {
            if (r.ok) setUsers(r.data.users || []);
        });
    }, []);

    async function handleLogin(e) {
        e.preventDefault();
        if (!userId.trim()) { setError('Please enter a User ID'); return; }
        setLoading(true);
        setError('');

        const r = await apiFetch('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ user_id: userId }),
        });

        if (r.ok) {
            localStorage.setItem('userId', r.data.user_id);
            localStorage.setItem('userRole', r.data.role || '');
            localStorage.setItem('userAbGroup', r.data.ab_group || '');
            window.location.href = '/';
        } else {
            setError(r.data?.detail || 'Login failed');
        }
        setLoading(false);
    }

    return (
        <div className="login-container">
            <div className="login-card">
                <h1>🧪 Docube</h1>
                <p>Recommendation Service · Test Frontend</p>

                <form onSubmit={handleLogin}>
                    <select
                        className="select"
                        value={userId}
                        onChange={e => setUserId(e.target.value)}
                        data-testid="user-select"
                    >
                        <option value="">-- Select a test user --</option>
                        {users.map(u => (
                            <option key={u.user_id} value={u.user_id}>
                                {u.user_id} — {u.role} — Group {u.ab_group}
                                {u.has_embedding ? '' : ' (cold start)'}
                            </option>
                        ))}
                    </select>

                    <div style={{ textAlign: 'left', margin: '8px 0' }}>
                        <label className="label">Or enter User ID manually</label>
                    </div>
                    <input
                        className="input"
                        placeholder="e.g. user-001"
                        value={userId}
                        onChange={e => setUserId(e.target.value)}
                        data-testid="user-id-input"
                    />

                    {error && <p style={{ color: 'var(--red)', fontSize: '13px', margin: '8px 0' }}>{error}</p>}

                    <button
                        className="btn btn-primary"
                        type="submit"
                        disabled={loading}
                        data-testid="login-button"
                    >
                        {loading ? '⏳ Logging in...' : '🚀 Login'}
                    </button>
                </form>
            </div>
        </div>
    );
}
