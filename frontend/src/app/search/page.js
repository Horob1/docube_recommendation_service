'use client';
import { useState, useEffect } from 'react';
import { apiFetch } from '../../lib/api';

export default function SearchPage() {
    const [userId, setUserId] = useState('');
    const [query, setQuery] = useState('');
    const [results, setResults] = useState(null);
    const [searchTime, setSearchTime] = useState(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const uid = localStorage.getItem('userId');
        if (!uid) { window.location.href = '/login'; return; }
        setUserId(uid);
    }, []);

    async function handleSearch(e) {
        e.preventDefault();
        if (!query.trim()) return;
        setLoading(true);

        // Log search
        apiFetch('/search-log', {
            method: 'POST',
            body: JSON.stringify({ query }),
        });

        const t0 = performance.now();
        const r = await apiFetch(`/api/documents/search?q=${encodeURIComponent(query)}&limit=20`);
        const elapsed = performance.now() - t0;

        if (r.ok) {
            setResults(r.data);
            setSearchTime(Math.round(elapsed));
        }
        setLoading(false);
    }

    return (
        <>
            <nav className="navbar">
                <div className="navbar-brand">📚 Docube</div>
                <div className="navbar-links">
                    <a href="/">Dashboard</a>
                    <a href="/search" className="active">Search</a>
                    <a href="/admin">Admin</a>
                    <span className="user-badge">{userId}</span>
                </div>
            </nav>

            <div className="container">
                <h2 className="page-title">🔍 Search Documents</h2>

                <form onSubmit={handleSearch}>
                    <div className="search-bar">
                        <input
                            className="input"
                            placeholder="Search documents using ANN vector search..."
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            data-testid="search-input"
                        />
                        <button className="btn btn-primary" type="submit" disabled={loading} data-testid="search-button">
                            {loading ? '⏳' : '🔍'} Search
                        </button>
                    </div>
                </form>

                {results && (
                    <>
                        <div className="search-time" data-testid="search-meta">
                            Found {results.total} results in {results.search_time_ms?.toFixed(0)}ms
                            (backend) · {searchTime}ms (total)
                        </div>

                        <div className="doc-grid" data-testid="search-results">
                            {results.results?.map(doc => (
                                <a key={doc.document_id} href={`/documents/${doc.document_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                                    <div className="card" data-testid={`search-result-${doc.document_id}`}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                            <div className="card-title">{doc.title}</div>
                                            <span className="score-badge">{doc.similarity.toFixed(3)}</span>
                                        </div>
                                        <div className="card-desc">{doc.description?.slice(0, 120)}...</div>
                                        <div className="tags">
                                            {doc.tags?.map(t => <span key={t} className="tag">{t}</span>)}
                                        </div>
                                        <div className="meta" style={{ marginTop: '6px' }}>
                                            ⭐ {doc.popularity_score?.toFixed(0)} · {doc.language}
                                        </div>
                                    </div>
                                </a>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </>
    );
}
