'use client';
import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { apiFetch } from '../../../lib/api';

export default function DocumentDetailPage() {
    const params = useParams();
    const docId = params.id;
    const [doc, setDoc] = useState(null);
    const [userId, setUserId] = useState('');
    const [interactions, setInteractions] = useState({});
    const [feedback, setFeedback] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const uid = localStorage.getItem('userId');
        if (!uid) { window.location.href = '/login'; return; }
        setUserId(uid);
        loadDocument();
    }, [docId]);

    async function loadDocument() {
        setLoading(true);
        const r = await apiFetch(`/api/documents/${docId}`);
        if (r.ok) setDoc(r.data);
        setLoading(false);

        // Auto-record view
        recordInteraction('view');
    }

    async function recordInteraction(type) {
        const r = await apiFetch('/interactions', {
            method: 'POST',
            body: JSON.stringify({ document_id: docId, interaction_type: type }),
        });

        if (r.ok) {
            setInteractions(prev => ({ ...prev, [type]: true }));
            setFeedback(`✅ ${type} recorded!`);
            setTimeout(() => setFeedback(''), 2000);
        }
    }

    if (loading) return <div className="container"><div className="spinner" /></div>;
    if (!doc) return <div className="container"><p>Document not found</p></div>;

    return (
        <>
            <nav className="navbar">
                <div className="navbar-brand">📚 Docube</div>
                <div className="navbar-links">
                    <a href="/">Dashboard</a>
                    <a href="/search">Search</a>
                    <a href="/admin">Admin</a>
                    <span className="user-badge">{userId}</span>
                </div>
            </nav>

            <div className="container" style={{ maxWidth: '800px' }}>
                <div className="section" data-testid="document-detail">
                    <h1 style={{ fontSize: '24px', marginBottom: '8px' }} data-testid="doc-title">{doc.title}</h1>
                    <div className="meta" data-testid="doc-meta">
                        {doc.document_id} · {doc.language} · ⭐ {doc.popularity_score?.toFixed(0)}
                        · Author: {doc.author_id} ({doc.author_role})
                    </div>

                    <div className="tags" style={{ margin: '12px 0' }} data-testid="doc-tags">
                        {doc.tags?.map(t => <span key={t} className="tag">{t}</span>)}
                        {doc.categories?.map(c => (
                            <span key={c} className="tag" style={{ background: 'rgba(34,201,151,.12)', color: 'var(--green)' }}>{c}</span>
                        ))}
                    </div>

                    <p style={{ color: 'var(--text2)', fontSize: '14px', marginBottom: '16px' }} data-testid="doc-description">
                        {doc.description}
                    </p>

                    <div style={{ background: 'var(--bg)', padding: '16px', borderRadius: '10px', fontSize: '14px', lineHeight: '1.8' }} data-testid="doc-content">
                        {doc.content}
                    </div>

                    {/* Interaction Buttons */}
                    <div className="interaction-bar" data-testid="interaction-bar">
                        <button
                            className={`interaction-btn ${interactions.view ? 'active' : ''}`}
                            onClick={() => recordInteraction('view')}
                            data-testid="btn-view"
                        >
                            👁 View
                        </button>
                        <button
                            className={`interaction-btn ${interactions.download ? 'active' : ''}`}
                            onClick={() => recordInteraction('download')}
                            data-testid="btn-download"
                        >
                            📥 Download
                        </button>
                        <button
                            className={`interaction-btn ${interactions.bookmark ? 'active' : ''}`}
                            onClick={() => recordInteraction('bookmark')}
                            data-testid="btn-bookmark"
                        >
                            🔖 Bookmark
                        </button>
                        <button
                            className={`interaction-btn ${interactions.buy ? 'active' : ''}`}
                            onClick={() => recordInteraction('buy')}
                            data-testid="btn-buy"
                        >
                            💰 Buy
                        </button>
                    </div>

                    {feedback && (
                        <div style={{ color: 'var(--green)', fontSize: '13px', marginTop: '8px' }} data-testid="interaction-feedback">
                            {feedback}
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
