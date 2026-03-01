'use client';
import { useState, useEffect } from 'react';
import { apiFetch } from '../../lib/api';

export default function AdminPage() {
    const [userId, setUserId] = useState('');
    const [health, setHealth] = useState(null);
    const [stats, setStats] = useState({});
    const [validation, setValidation] = useState({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const uid = localStorage.getItem('userId');
        if (!uid) { window.location.href = '/login'; return; }
        setUserId(uid);
        refresh();
    }, []);

    async function refresh() {
        setLoading(true);

        const [h, dc, uc, embDim, ivf, annT, cacheTtl] = await Promise.all([
            apiFetch('/health'),
            apiFetch('/api/validate/document-count'),
            apiFetch('/api/validate/user-count'),
            apiFetch('/api/validate/embedding-dim'),
            apiFetch('/api/validate/ivfflat-index'),
            apiFetch(`/api/validate/ann-query-time?user_id=${userId || 'user-001'}`),
            apiFetch(`/api/validate/cache-ttl?user_id=${userId || 'user-001'}`),
        ]);

        if (h.ok) setHealth(h.data);
        setStats({
            documents: dc.ok ? dc.data.total : '?',
            documentsWithEmb: dc.ok ? dc.data.with_embedding : '?',
            users: uc.ok ? uc.data.total : '?',
        });
        setValidation({
            embeddingDim: embDim.ok ? embDim.data : {},
            ivflatIndex: ivf.ok ? ivf.data : {},
            annQueryTime: annT.ok ? annT.data : {},
            cacheTtl: cacheTtl.ok ? cacheTtl.data : {},
        });
        setLoading(false);
    }

    const V = ({ ok }) => ok ? <span className="status-up">✓ PASS</span> : <span className="status-down">✗ FAIL</span>;

    return (
        <>
            <nav className="navbar">
                <div className="navbar-brand">📚 Docube</div>
                <div className="navbar-links">
                    <a href="/">Dashboard</a>
                    <a href="/search">Search</a>
                    <a href="/admin" className="active">Admin</a>
                    <span className="user-badge">{userId}</span>
                </div>
            </nav>

            <div className="container">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <h2 className="page-title" style={{ margin: 0 }}>📊 Admin · Test Monitor</h2>
                    <button className="btn btn-primary" onClick={refresh} disabled={loading} data-testid="refresh-admin">
                        🔄 Refresh
                    </button>
                </div>

                {/* Health */}
                {health && (
                    <div className="stat-grid" data-testid="health-stats">
                        <div className="stat-card">
                            <div className="stat-value" style={{ color: health.status === 'UP' ? 'var(--green)' : 'var(--yellow)' }}>
                                {health.status}
                            </div>
                            <div className="stat-label">Service</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-value" style={{ color: health.database === 'UP' ? 'var(--green)' : 'var(--red)' }}>
                                {health.database}
                            </div>
                            <div className="stat-label">PostgreSQL</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-value" style={{ color: health.redis?.includes('UP') ? 'var(--green)' : 'var(--red)' }}>
                                {health.redis}
                            </div>
                            <div className="stat-label">Redis</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-value">{stats.documents}</div>
                            <div className="stat-label">Documents</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-value">{stats.documentsWithEmb}</div>
                            <div className="stat-label">W/ Embedding</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-value">{stats.users}</div>
                            <div className="stat-label">Users</div>
                        </div>
                    </div>
                )}

                {/* Validation Checks */}
                <div className="section" data-testid="validation-section">
                    <h3 className="section-title">🔬 Backend Validation</h3>

                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                <th style={{ textAlign: 'left', padding: '8px', color: 'var(--text2)' }}>Check</th>
                                <th style={{ textAlign: 'left', padding: '8px', color: 'var(--text2)' }}>Result</th>
                                <th style={{ textAlign: 'left', padding: '8px', color: 'var(--text2)' }}>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style={{ borderBottom: '1px solid var(--border)' }} data-testid="check-embedding-dim">
                                <td style={{ padding: '8px' }}>Embedding Dimension = 384</td>
                                <td style={{ padding: '8px' }}>{validation.embeddingDim?.dimension || '?'}</td>
                                <td style={{ padding: '8px' }}><V ok={validation.embeddingDim?.match} /></td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid var(--border)' }} data-testid="check-ivfflat">
                                <td style={{ padding: '8px' }}>IVFFLAT Index Exists</td>
                                <td style={{ padding: '8px' }}>{validation.ivflatIndex?.indexes?.length || 0} index(es)</td>
                                <td style={{ padding: '8px' }}><V ok={validation.ivflatIndex?.exists} /></td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid var(--border)' }} data-testid="check-ann-time">
                                <td style={{ padding: '8px' }}>ANN Query Time &lt; 500ms</td>
                                <td style={{ padding: '8px' }}>{validation.annQueryTime?.ann_time_ms?.toFixed(1) || '?'}ms</td>
                                <td style={{ padding: '8px' }}><V ok={validation.annQueryTime?.under_threshold} /></td>
                            </tr>
                            <tr style={{ borderBottom: '1px solid var(--border)' }} data-testid="check-cache-ttl">
                                <td style={{ padding: '8px' }}>Redis Cache TTL</td>
                                <td style={{ padding: '8px' }}>{validation.cacheTtl?.ttl_seconds || '?'}s</td>
                                <td style={{ padding: '8px' }}><V ok={validation.cacheTtl?.exists} /></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </>
    );
}
