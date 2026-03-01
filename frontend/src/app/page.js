'use client';
import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';

export default function Dashboard() {
    const [userId, setUserId] = useState('');
    const [docs, setDocs] = useState([]);
    const [recs, setRecs] = useState(null);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [loading, setLoading] = useState(true);
    const [recLoading, setRecLoading] = useState(true);
    const [recMeta, setRecMeta] = useState({});

    useEffect(() => {
        const uid = localStorage.getItem('userId');
        if (!uid) { window.location.href = '/login'; return; }
        setUserId(uid);
        loadDocuments(1);
        loadRecommendations();
    }, []);

    async function loadDocuments(p) {
        setLoading(true);
        const r = await apiFetch(`/api/documents?page=${p}&limit=20`);
        if (r.ok) {
            setDocs(r.data.documents || []);
            setTotalPages(r.data.pages || 1);
            setPage(p);
        }
        setLoading(false);
    }

    async function loadRecommendations() {
        setRecLoading(true);
        const t0 = performance.now();
        const r = await apiFetch('/recommendations?limit=10');
        const elapsed = performance.now() - t0;
        if (r.ok) {
            setRecs(r.data);
            setRecMeta({
                latency: Math.round(elapsed),
                cached: r.data.cached,
                cacheHit: r.cacheHit,
            });
        }
        setRecLoading(false);
    }

    function logout() {
        localStorage.clear();
        window.location.href = '/login';
    }

    return (
        <>
            <nav className="navbar">
                <div className="navbar-brand">📚 Docube</div>
                <div className="navbar-links">
                    <a href="/" className="active">Dashboard</a>
                    <a href="/search">Search</a>
                    <a href="/admin">Admin</a>
                    <span className="user-badge" data-testid="user-badge">{userId}</span>
                    <button className="btn btn-sm btn-outline" onClick={logout}>Logout</button>
                </div>
            </nav>

            <div className="container">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: '24px' }}>
                    {/* Left: Documents */}
                    <div>
                        <h2 className="page-title" data-testid="doc-list-title">📄 Documents</h2>
                        {loading ? (
                            <div className="spinner" />
                        ) : (
                            <>
                                <div className="doc-grid" data-testid="doc-grid">
                                    {docs.map(doc => (
                                        <a key={doc.document_id} href={`/documents/${doc.document_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                                            <div className="card" data-testid={`doc-card-${doc.document_id}`}>
                                                <div className="card-title">{doc.title}</div>
                                                <div className="card-desc">{doc.description?.slice(0, 100)}...</div>
                                                <div className="tags">
                                                    {(doc.tags || []).map(t => <span key={t} className="tag">{t}</span>)}
                                                </div>
                                                <div className="meta" style={{ marginTop: '8px' }}>
                                                    ⭐ {doc.popularity_score?.toFixed(0)} · {doc.language}
                                                </div>
                                            </div>
                                        </a>
                                    ))}
                                </div>

                                <div className="pagination" data-testid="pagination">
                                    {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => (
                                        <button
                                            key={i + 1}
                                            className={`page-btn ${page === i + 1 ? 'active' : ''}`}
                                            onClick={() => loadDocuments(i + 1)}
                                            data-testid={`page-btn-${i + 1}`}
                                        >
                                            {i + 1}
                                        </button>
                                    ))}
                                </div>
                            </>
                        )}
                    </div>

                    {/* Right: Recommendations */}
                    <div>
                        <h2 className="page-title" data-testid="rec-title">🎯 For You</h2>
                        <div className="section" style={{ position: 'sticky', top: '72px' }}>
                            {recLoading ? (
                                <div className="spinner" />
                            ) : recs ? (
                                <>
                                    <div className="meta" style={{ marginBottom: '12px' }} data-testid="rec-meta">
                                        Group {recs.ab_group} · {recMeta.cached ? '⚡ Cached' : '🔄 Fresh'}
                                        · {recMeta.latency}ms
                                    </div>
                                    <div className="rec-list" data-testid="rec-list">
                                        {recs.recommendations?.map((rec, i) => (
                                            <a key={rec.document_id} href={`/documents/${rec.document_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                                                <div className="rec-item" data-testid={`rec-item-${i}`}>
                                                    <div>
                                                        <div className="card-title">{rec.title}</div>
                                                        <div className="tags" style={{ marginTop: '4px' }}>
                                                            {rec.tags?.slice(0, 3).map(t => <span key={t} className="tag">{t}</span>)}
                                                        </div>
                                                        <div className="rec-reason">{rec.reason}</div>
                                                    </div>
                                                    <span className="score-badge">{rec.score.toFixed(3)}</span>
                                                </div>
                                            </a>
                                        ))}
                                    </div>
                                    <button
                                        className="btn btn-outline btn-sm"
                                        style={{ width: '100%', justifyContent: 'center', marginTop: '12px' }}
                                        onClick={loadRecommendations}
                                        data-testid="refresh-recs"
                                    >
                                        🔄 Refresh
                                    </button>
                                </>
                            ) : (
                                <div className="meta">No recommendations yet</div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}
