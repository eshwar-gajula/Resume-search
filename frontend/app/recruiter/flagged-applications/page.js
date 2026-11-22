'use client';

import { useState, useEffect } from 'react';
import { isLoggedIn, isRecruiter, getAuthHeaders } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import AccessDenied from '@/components/AccessDenied';
import TestIntegrityPanel from '@/components/TestIntegrityPanel';
import styles from './page.module.css';

import API from '@/lib/config';

export default function FlaggedApplicationsPage() {
    const router = useRouter();
    const [hasAccess, setHasAccess] = useState(null);
    const [applications, setApplications] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedApp, setSelectedApp] = useState(null);
    const [actionLoading, setActionLoading] = useState(null);
    const [integrityChecking, setIntegrityChecking] = useState(null);

    useEffect(() => {
        if (!isLoggedIn()) {
            router.push('/login');
            return;
        }
        setHasAccess(isRecruiter());
    }, [router]);

    useEffect(() => {
        if (hasAccess) {
            fetchFlaggedApplications();
        }
    }, [hasAccess]);

    const fetchFlaggedApplications = async () => {
        try {
            const res = await fetch(`${API}/applications/flagged`, {
                headers: getAuthHeaders()
            });
            const data = await res.json();
            setApplications(Array.isArray(data) ? data : []);
        } catch (err) {
            console.error('Error fetching flagged applications:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleApprove = async (appId) => {
        setActionLoading(appId);
        try {
            const res = await fetch(`${API}/applications/${appId}/approve-flag`, {
                method: 'POST',
                headers: getAuthHeaders()
            });
            if (res.ok) {
                setApplications(prev => prev.filter(a => a.application_id !== appId));
                setSelectedApp(null);
            }
        } catch (err) {
            console.error('Error approving application:', err);
        } finally {
            setActionLoading(null);
        }
    };

    const handleReject = async (appId) => {
        setActionLoading(appId);
        try {
            const res = await fetch(`${API}/applications/${appId}/reject-flag`, {
                method: 'POST',
                headers: getAuthHeaders()
            });
            if (res.ok) {
                setApplications(prev => prev.filter(a => a.application_id !== appId));
                setSelectedApp(null);
            }
        } catch (err) {
            console.error('Error rejecting application:', err);
        } finally {
            setActionLoading(null);
        }
    };

    const runIntegrityCheck = async (appId) => {
        setIntegrityChecking(appId);
        try {
            const res = await fetch(`${API}/applications/${appId}/integrity-check`, {
                method: 'POST',
                headers: getAuthHeaders()
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Could not check these answers');
            setSelectedApp(current => current?.application_id === appId ? { ...current, ...data } : current);
            setApplications(current => current.map(app =>
                app.application_id === appId ? { ...app, ...data } : app
            ));
        } catch (err) {
            alert(err.message || 'Could not check these answers');
        } finally {
            setIntegrityChecking(null);
        }
    };

    const toggleIdentity = async (applicationId, reveal) => {
        try {
            const response = await fetch(`${API}/applications/${applicationId}?reveal_pii=${reveal}`, {
                headers: getAuthHeaders(),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Could not load applicant details.');
            setSelectedApp(data);
        } catch (error) {
            alert(error.message || 'Could not load applicant details.');
        }
    };

    const getOriginalityInfo = (app) => {
        const originality = app.match_details?.benchmarks?.screening_questions?.originality_assessment;
        return originality || {};
    };

    if (hasAccess === null || loading) {
        return (
            <div style={{ textAlign: 'center', padding: '60px' }}>
                <div className="loading-spinner"></div>
                <p style={{ color: '#888' }}>Loading...</p>
            </div>
        );
    }

    if (!hasAccess) {
        return (
            <AccessDenied
                title="Recruiter Access Only"
                message="This page is for recruiters to review flagged applications."
                linkText="Go Home"
                linkHref="/"
            />
        );
    }

    return (
        <div className="container">
            <div className={styles.header}>
                <h2>🚨 Flagged Applications</h2>
                <p>These applications need a human review because an answer check was concerning or inconclusive. Automated indicators are estimates, not proof; review the answers and context before deciding.</p>
            </div>

            {applications.length === 0 ? (
                <div className={styles.emptyState}>
                    <span className={styles.emptyIcon}>✅</span>
                    <h3>No Flagged Applications</h3>
                    <p>No applications currently have an originality score below 40.</p>
                </div>
            ) : (
                <div className={styles.grid}>
                    {applications.map(app => {
                        const originality = getOriginalityInfo(app);
                        const integrity = app.match_details?.skill_test_integrity;
                        const ai = integrity?.ai_detection;
                        const web = integrity?.web_similarity;
                        return (
                            <div key={app.application_id} className={styles.card}>
                                <div className={styles.cardHeader}>
                                    <div className={styles.candidateInfo}>
                                        <h4>{app.user?.display_name || 'Candidate'}</h4>
                                    </div>
                                    <div className={styles.warningBadge}>
                                        {integrity?.routing?.reasons?.length
                                            ? 'Manual review required'
                                            : (originality.originality_score !== undefined && originality.originality_score !== null
                                                ? `Originality estimate: ${originality.originality_score}/100`
                                                : 'Manual review required')}
                                    </div>
                                </div>

                                <div className={styles.jobInfo}>
                                    <span>Applied for: </span>
                                    <strong>{app.job?.role}</strong>
                                </div>

                                {ai?.status === 'checked' ? (
                                    <div className={styles.suspicionLevel}>
                                        <span>AI detector: </span>
                                        <span className={`${styles.level} ${styles['level' + (ai.verdict === 'ai_generated' ? 'High' : ai.verdict === 'human_written' ? 'Low' : 'Inconclusive')]}`}>
                                            {ai.verdict === 'ai_generated' ? 'likely AI-generated' : ai.verdict === 'human_written' ? 'likely human-written' : 'undetectable'}
                                        </span>
                                    </div>
                                ) : originality.suspicion_level ? (
                                    <div className={styles.suspicionLevel}>
                                        <span>Originality review: </span>
                                        <span className={`${styles.level} ${styles['level' + originality.suspicion_level.charAt(0).toUpperCase() + originality.suspicion_level.slice(1)]}`}>
                                            {originality.suspicion_level}
                                        </span>
                                    </div>
                                ) : null}

                                {web?.status === 'checked' && (
                                    <div className={styles.jobInfo}>
                                        <span>Web-source similarity: </span>
                                        <strong>{Number(web.score).toFixed(1)}%{web.passed === false ? ' (above review threshold)' : ''}</strong>
                                    </div>
                                )}

                                {originality.suspicion_flags?.length > 0 && (
                                    <div className={styles.flags}>
                                        {originality.suspicion_flags.map((flag, idx) => (
                                            <span key={idx} className={styles.flag}>
                                                ⚠️ {flag.replace(/_/g, ' ')}
                                            </span>
                                        ))}
                                    </div>
                                )}

                                <button
                                    className={styles.viewBtn}
                                    onClick={() => setSelectedApp(app)}
                                >
                                    Review Details
                                </button>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Review Modal */}
            {selectedApp && (
                <div className={styles.modalOverlay} onClick={() => setSelectedApp(null)}>
                    <div className={styles.modal} onClick={e => e.stopPropagation()}>
                        <button className={styles.closeBtn} onClick={() => setSelectedApp(null)}>×</button>

                        <h3>Review Flagged Application</h3>

                        <div className={styles.section}>
                            <h4>Candidate</h4>
                            <p><strong>{selectedApp.user?.display_name || 'Candidate'}</strong></p>
                            {selectedApp.revealed_pii && (
                                <p>{selectedApp.user?.email}{selectedApp.user?.mobile ? ` · ${selectedApp.user.mobile}` : ''}</p>
                            )}
                            <button
                                type="button"
                                className={styles.viewBtn}
                                onClick={() => toggleIdentity(selectedApp.application_id, !selectedApp.revealed_pii)}
                            >
                                {selectedApp.revealed_pii ? 'Hide identity' : 'Reveal identity'}
                            </button>
                        </div>

                        <div className={styles.section}>
                            <h4>Applied For</h4>
                            <p><strong>{selectedApp.job?.role}</strong></p>
                        </div>

                        <TestIntegrityPanel
                            report={selectedApp.match_details?.skill_test_integrity}
                            answers={selectedApp.test_answers?.length ? selectedApp.test_answers : (selectedApp.screening_answers || [])}
                            matchOriginality={Object.keys(getOriginalityInfo(selectedApp)).length > 0 ? getOriginalityInfo(selectedApp) : null}
                            plagiarismScore={selectedApp.plagiarism_score}
                            passedPlagiarism={selectedApp.passed_plagiarism}
                            onRunCheck={() => runIntegrityCheck(selectedApp.application_id)}
                            checking={integrityChecking === selectedApp.application_id}
                        />

                        <div className={styles.actions}>
                            <button
                                className={styles.approveBtn}
                                onClick={() => handleApprove(selectedApp.application_id)}
                                disabled={actionLoading === selectedApp.application_id}
                            >
                                {actionLoading === selectedApp.application_id ? 'Processing...' : '✅ Approve for Review'}
                            </button>
                            <button
                                className={styles.rejectBtn}
                                onClick={() => handleReject(selectedApp.application_id)}
                                disabled={actionLoading === selectedApp.application_id}
                            >
                                {actionLoading === selectedApp.application_id ? 'Processing...' : '❌ Reject application'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
