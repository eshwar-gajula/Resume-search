'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { isLoggedIn, isRecruiter, getAuthHeaders } from '@/lib/auth';
import AccessDenied from '@/components/AccessDenied';
import TestIntegrityPanel from '@/components/TestIntegrityPanel';
import styles from './page.module.css';

import API from '@/lib/config';

export default function ReviewApplicantsPage() {
    const router = useRouter();
    const [hasAccess, setHasAccess] = useState(null);
    const [applications, setApplications] = useState([]);
    const [flaggedCount, setFlaggedCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('');
    const [selectedApp, setSelectedApp] = useState(null);
    const [integrityChecking, setIntegrityChecking] = useState(null);
    const [searchText, setSearchText] = useState('');
    const [searchSkills, setSearchSkills] = useState('');
    const [searchMinExperience, setSearchMinExperience] = useState('');
    const [searchMaxExperience, setSearchMaxExperience] = useState('');
    const [searchMinMatch, setSearchMinMatch] = useState('');
    const [searchLocation, setSearchLocation] = useState('');
    const [searchStatus, setSearchStatus] = useState('');
    const [searching, setSearching] = useState(false);
    const [selectedIds, setSelectedIds] = useState([]);
    const [bulkBusy, setBulkBusy] = useState(false);

    useEffect(() => {
        if (!isLoggedIn()) {
            router.push('/login');
            return;
        }
        const recruiterAccess = isRecruiter();
        setHasAccess(recruiterAccess);
        if (recruiterAccess) {
            fetchApplications();
        } else {
            setLoading(false);
        }
    }, [router]);

    const fetchApplications = async () => {
        try {
            // Use /applications/ with no filters to get all applications
            const res = await fetch(`${API}/applications/`, {
                headers: getAuthHeaders()
            });
            const data = await res.json();
            // Filter out flagged applications (they go to separate page)
            const allApps = Array.isArray(data) ? data : [];
            const nonFlagged = allApps.filter(app => app.status !== 'flagged');
            const flagged = allApps.filter(app => app.status === 'flagged');
            setApplications(nonFlagged);
            setFlaggedCount(flagged.length);
        } catch (err) {
            console.error('Error fetching applications:', err);
            setApplications([]);
        } finally {
            setLoading(false);
        }
    };

    const searchCandidates = async (event) => {
        event?.preventDefault();
        const query = searchText.trim();
        const hasFilters = searchSkills.trim() || searchMinExperience !== '' || searchMaxExperience !== '' || searchMinMatch !== '' || searchLocation.trim() || searchStatus;
        if (!query && !hasFilters) {
            await fetchApplications();
            setSelectedIds([]);
            return;
        }
        setSearching(true);
        try {
            const response = await fetch(`${API}/applications/search`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    ...(query ? { query } : {}),
                    ...(searchSkills.trim() ? { skills: searchSkills.split(',').map(skill => skill.trim()).filter(Boolean) } : {}),
                    ...(searchMinExperience !== '' ? { min_experience: Number(searchMinExperience) } : {}),
                    ...(searchMaxExperience !== '' ? { max_experience: Number(searchMaxExperience) } : {}),
                    ...(searchMinMatch !== '' ? { min_match_score: Number(searchMinMatch) } : {}),
                    ...(searchLocation.trim() ? { location: searchLocation.trim() } : {}),
                    ...(searchStatus ? { status: searchStatus } : {}),
                }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Candidate search failed.');
            setApplications(Array.isArray(data) ? data : []);
            setSelectedIds([]);
        } catch (error) {
            alert(error.message || 'Candidate search failed.');
        } finally {
            setSearching(false);
        }
    };

    const toggleSelected = (applicationId) => {
        setSelectedIds(current => {
            if (current.includes(applicationId)) return current.filter(id => id !== applicationId);
            if (current.length >= 100) {
                alert('Select up to 100 applications for a bulk action.');
                return current;
            }
            return [...current, applicationId];
        });
    };

    const bulkShortlist = async () => {
        if (!selectedIds.length) return;
        setBulkBusy(true);
        try {
            const response = await fetch(`${API}/applications/bulk-action`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ application_ids: selectedIds, action: 'shortlist' }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Bulk shortlist failed.');
            setSelectedIds([]);
            await fetchApplications();
        } catch (error) {
            alert(error.message || 'Bulk shortlist failed.');
        } finally {
            setBulkBusy(false);
        }
    };

    const exportCandidates = async () => {
        const ids = selectedIds.length ? `&${selectedIds.map(id => `application_ids=${id}`).join('&')}` : '';
        try {
            const response = await fetch(`${API}/applications/export?reveal_pii=false${ids}`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` },
            });
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.detail || 'Export failed.');
            }
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'resumeai-candidates.csv';
            link.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            alert(error.message || 'Export failed.');
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

    const downloadResume = async (applicationId) => {
        try {
            const response = await fetch(`${API}/applications/${applicationId}/resume?reveal_pii=true`, {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` },
            });
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.detail || 'Resume download failed.');
            }
            const url = URL.createObjectURL(await response.blob());
            const link = document.createElement('a');
            link.href = url;
            link.download = `resume-${applicationId}`;
            link.click();
            URL.revokeObjectURL(url);
        } catch (error) {
            alert(error.message || 'Resume download failed.');
        }
    };

    const updateStatus = async (appId, status) => {
        try {
            const res = await fetch(`${API}/applications/${appId}/status?new_status=${status}`, {
                method: 'PUT',
                headers: getAuthHeaders()
            });

            if (res.ok) {
                setApplications(apps =>
                    apps.map(app =>
                        app.application_id === appId ? { ...app, status } : app
                    )
                );
                if (selectedApp?.application_id === appId) {
                    setSelectedApp({ ...selectedApp, status });
                }
            } else {
                const data = await res.json().catch(() => ({}));
                alert(data.detail || 'Failed to update status');
            }
        } catch (err) {
            alert('Network error');
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
            await fetchApplications();
        } catch (err) {
            alert(err.message || 'Could not check these answers');
        } finally {
            setIntegrityChecking(null);
        }
    };

    // Loading state
    if (hasAccess === null || loading) {
        return (
            <div style={{ textAlign: 'center', padding: '60px' }}>
                <div className="loading-spinner"></div>
                <p style={{ color: '#888' }}>Loading...</p>
            </div>
        );
    }

    // Access denied - polite message
    if (!hasAccess) {
        return (
            <AccessDenied
                title="Recruiter Access Only"
                message="This page is reserved for recruiters to review job applications. If you're looking for job opportunities, check out our available positions!"
                linkText="Browse Jobs"
                linkHref="/jobs"
            />
        );
    }

    const filteredApps = filter
        ? applications.filter(app => app.status === filter)
        : applications;

    const getStatusClass = (status) => {
        switch (status) {
            case 'shortlisted': return styles.statusShortlisted;
            case 'accepted': return styles.statusAccepted;
            case 'rejected': return styles.statusRejected;
            default: return styles.statusPending;
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return 'Recently';
        return new Date(dateStr).toLocaleDateString();
    };

    const statusCounts = {
        all: applications.length,
        pending: applications.filter(a => a.status === 'pending').length,
        shortlisted: applications.filter(a => a.status === 'shortlisted').length,
        accepted: applications.filter(a => a.status === 'accepted').length,
        rejected: applications.filter(a => a.status === 'rejected').length
    };

    return (
        <div className="container">
            <div className={styles.header}>
                <h2>📋 Review Applicants</h2>
                <p>Manage job applications and update candidate status</p>
                {flaggedCount > 0 && (
                    <Link href="/recruiter/flagged-applications" className={styles.flaggedLink}>
                        🚨 {flaggedCount} application{flaggedCount > 1 ? 's' : ''} flagged for review
                    </Link>
                )}
            </div>

            <div className={styles.filters}>
                <button
                    className={`${styles.filterBtn} ${filter === '' ? styles.active : ''}`}
                    onClick={() => setFilter('')}
                >
                    All ({statusCounts.all})
                </button>
                <button
                    className={`${styles.filterBtn} ${filter === 'pending' ? styles.active : ''}`}
                    onClick={() => setFilter('pending')}
                >
                    Pending ({statusCounts.pending})
                </button>
                <button
                    className={`${styles.filterBtn} ${filter === 'shortlisted' ? styles.active : ''}`}
                    onClick={() => setFilter('shortlisted')}
                >
                    Shortlisted ({statusCounts.shortlisted})
                </button>
                <button
                    className={`${styles.filterBtn} ${filter === 'accepted' ? styles.active : ''}`}
                    onClick={() => setFilter('accepted')}
                >
                    Accepted ({statusCounts.accepted})
                </button>
                <button
                    className={`${styles.filterBtn} ${filter === 'rejected' ? styles.active : ''}`}
                    onClick={() => setFilter('rejected')}
                >
                    Rejected ({statusCounts.rejected})
                </button>
            </div>

            <form className={styles.searchBar} onSubmit={searchCandidates}>
                <input
                    value={searchText}
                    onChange={event => setSearchText(event.target.value)}
                    placeholder="Search skills or paste a job description"
                    aria-label="Search applicants"
                />
                <input value={searchSkills} onChange={event => setSearchSkills(event.target.value)} placeholder="Required skills" aria-label="Required skills, comma separated" />
                <input type="number" min="0" max="80" value={searchMinExperience} onChange={event => setSearchMinExperience(event.target.value)} placeholder="Min years" aria-label="Minimum experience" />
                <input type="number" min="0" max="80" value={searchMaxExperience} onChange={event => setSearchMaxExperience(event.target.value)} placeholder="Max years" aria-label="Maximum experience" />
                <input type="number" min="0" max="100" value={searchMinMatch} onChange={event => setSearchMinMatch(event.target.value)} placeholder="Min match %" aria-label="Minimum match score" />
                <input value={searchLocation} onChange={event => setSearchLocation(event.target.value)} placeholder="Location" aria-label="Location filter" />
                <select value={searchStatus} onChange={event => setSearchStatus(event.target.value)} aria-label="Application status">
                    <option value="">Any status</option>
                    <option value="pending">Pending</option>
                    <option value="shortlisted">Shortlisted</option>
                    <option value="accepted">Accepted</option>
                    <option value="rejected">Rejected</option>
                </select>
                <button type="submit" disabled={searching}>{searching ? 'Searching…' : 'Search'}</button>
                <button type="button" onClick={async () => {
                    setSearchText(''); setSearchSkills(''); setSearchMinExperience(''); setSearchMaxExperience('');
                    setSearchMinMatch(''); setSearchLocation(''); setSearchStatus(''); setSelectedIds([]);
                    await fetchApplications();
                }}>Clear</button>
            </form>
            <div className={styles.bulkActions}>
                <span>{selectedIds.length} selected · applicant identities are hidden by default</span>
                <button type="button" onClick={bulkShortlist} disabled={!selectedIds.length || bulkBusy}>
                    {bulkBusy ? 'Inviting…' : 'Shortlist and invite selected'}
                </button>
                <button type="button" onClick={exportCandidates}>Export CSV</button>
            </div>

            {filteredApps.length === 0 ? (
                <div className={styles.empty}>
                    <h3>No applications found</h3>
                    <p>Applications will appear here when candidates apply to your jobs.</p>
                </div>
            ) : (
                <div className={styles.appList}>
                    {filteredApps.map(app => (
                        <div key={app.application_id} className={styles.appCard}>
                            <div className={styles.appMain}>
                                <label className={styles.selectCandidate}>
                                    <input
                                        type="checkbox"
                                        checked={selectedIds.includes(app.application_id)}
                                        onChange={() => toggleSelected(app.application_id)}
                                        aria-label={`Select ${app.user?.display_name || 'candidate'}`}
                                    />
                                    Select
                                </label>
                                <h3>{app.user?.display_name || 'Candidate'}</h3>
                                <p className={styles.jobTitle}>{app.job?.role || 'Job Position'}</p>
                                <div className={styles.appMeta}>
                                    <span>Experience: {app.user?.years_of_experience ?? 0} years</span>
                                    <span>📅 Applied: {formatDate(app.applied_at)}</span>
                                    {app.resume_required && <span>Resume needed</span>}
                                </div>
                                {app.match_score && (
                                    <div className={styles.matchScore}>
                                        AI Match Score: <strong>{Math.round(app.match_score)}%</strong>
                                    </div>
                                )}
                            </div>
                            <div className={styles.appActions}>
                                <span className={`${styles.status} ${getStatusClass(app.status)}`}>
                                    {app.status}
                                </span>
                                <div className={styles.actionBtns}>
                                    {app.status !== 'shortlisted' && app.status !== 'accepted' && (
                                        <button
                                            className={styles.btnShortlist}
                                            onClick={() => updateStatus(app.application_id, 'shortlisted')}
                                            disabled={app.resume_required}
                                        >
                                            {app.resume_required ? 'Waiting for resume' : '✓ Shortlist'}
                                        </button>
                                    )}
                                    {app.status === 'shortlisted' && (
                                        <button
                                            className={styles.btnAccept}
                                            onClick={() => updateStatus(app.application_id, 'accepted')}
                                        >
                                            ✓ Accept
                                        </button>
                                    )}
                                    {app.status !== 'rejected' && app.status !== 'accepted' && (
                                        <button
                                            className={styles.btnReject}
                                            onClick={() => updateStatus(app.application_id, 'rejected')}
                                        >
                                            ✗ Reject
                                        </button>
                                    )}
                                    <button
                                        className={styles.btnView}
                                        onClick={() => setSelectedApp(app)}
                                    >
                                        View Details
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {selectedApp && (
                <div className="modal-overlay" onClick={() => setSelectedApp(null)}>
                    <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
                        <button className="modal-close" onClick={() => setSelectedApp(null)}>×</button>

                        <h2>{selectedApp.user?.display_name || 'Candidate'}</h2>
                        {selectedApp.revealed_pii && (
                            <p style={{ color: '#888', marginBottom: '12px' }}>
                                {selectedApp.user?.email}{selectedApp.user?.mobile ? ` · ${selectedApp.user.mobile}` : ''}
                            </p>
                        )}
                        <div className={styles.identityActions}>
                            <button type="button" onClick={() => toggleIdentity(selectedApp.application_id, !selectedApp.revealed_pii)}>
                                {selectedApp.revealed_pii ? 'Hide identity' : 'Reveal identity'}
                            </button>
                            {selectedApp.revealed_pii && selectedApp.user?.has_resume && selectedApp.status !== 'flagged' && (
                                <button type="button" onClick={() => downloadResume(selectedApp.application_id)}>Download resume</button>
                            )}
                        </div>

                        {/* Social Links */}
                        {selectedApp.revealed_pii && selectedApp.user?.resume_parsed?.social_links && (
                            <div className={styles.socialLinks}>
                                {selectedApp.user.resume_parsed.social_links.github && (
                                    <a href={selectedApp.user.resume_parsed.social_links.github} target="_blank" rel="noopener noreferrer" className={styles.socialLink}>
                                        🐙 GitHub
                                    </a>
                                )}
                                {selectedApp.user.resume_parsed.social_links.linkedin && (
                                    <a href={selectedApp.user.resume_parsed.social_links.linkedin} target="_blank" rel="noopener noreferrer" className={styles.socialLink}>
                                        💼 LinkedIn
                                    </a>
                                )}
                                {selectedApp.user.resume_parsed.social_links.leetcode && (
                                    <a href={selectedApp.user.resume_parsed.social_links.leetcode} target="_blank" rel="noopener noreferrer" className={styles.socialLink}>
                                        🧩 LeetCode
                                    </a>
                                )}
                                {selectedApp.user.resume_parsed.social_links.codechef && (
                                    <a href={selectedApp.user.resume_parsed.social_links.codechef} target="_blank" rel="noopener noreferrer" className={styles.socialLink}>
                                        👨‍🍳 CodeChef
                                    </a>
                                )}
                                {selectedApp.user.resume_parsed.social_links.hackerrank && (
                                    <a href={selectedApp.user.resume_parsed.social_links.hackerrank} target="_blank" rel="noopener noreferrer" className={styles.socialLink}>
                                        💚 HackerRank
                                    </a>
                                )}
                                {selectedApp.user.resume_parsed.social_links.portfolio && (
                                    <a href={selectedApp.user.resume_parsed.social_links.portfolio} target="_blank" rel="noopener noreferrer" className={styles.socialLink}>
                                        🌐 Portfolio
                                    </a>
                                )}
                            </div>
                        )}

                        <div className={styles.modalSection}>
                            <h4>Applied For</h4>
                            <p><strong>{selectedApp.job?.role}</strong></p>
                            <p style={{ color: '#888' }}>
                                📍 {selectedApp.job?.job_location || 'Remote'}
                            </p>
                        </div>

                        <TestIntegrityPanel
                            report={selectedApp.match_details?.skill_test_integrity}
                            answers={selectedApp.test_answers?.length ? selectedApp.test_answers : (selectedApp.screening_answers || [])}
                            matchOriginality={selectedApp.match_details?.benchmarks?.screening_questions?.originality_assessment}
                            plagiarismScore={selectedApp.plagiarism_score}
                            passedPlagiarism={selectedApp.passed_plagiarism}
                            onRunCheck={() => runIntegrityCheck(selectedApp.application_id)}
                            checking={integrityChecking === selectedApp.application_id}
                        />

                        {selectedApp.match_score && (
                            <div className={styles.modalSection}>
                                <h4>AI Match Analysis</h4>
                                <div className={styles.scoreBar}>
                                    <div
                                        className={styles.scoreProgress}
                                        style={{ width: `${selectedApp.match_score}%` }}
                                    ></div>
                                </div>
                                <p style={{ fontSize: '20px', fontWeight: 'bold', color: '#22c55e' }}>
                                    {Math.round(selectedApp.match_score)}% Overall Match
                                </p>

                                {/* Benchmark Breakdown - if available in user's resume_parsed or a separate field */}
                                {selectedApp.match_details?.benchmarks && (
                                    <div className={styles.benchmarks}>
                                        <h5>Benchmark Breakdown</h5>
                                        <div className={styles.benchmarkGrid}>
                                            {Object.entries(selectedApp.match_details.benchmarks).map(([key, data]) => (
                                                <div key={key} className={styles.benchmarkItem}>
                                                    <div className={styles.benchmarkHeader}>
                                                        <span className={styles.benchmarkName}>
                                                            {key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                                                        </span>
                                                        <span className={styles.benchmarkScore}>{data.score}</span>
                                                    </div>
                                                    <p className={styles.benchmarkReason}>{data.reasoning}</p>

                                                </div>
                                            ))}
                                        </div>
                                        {selectedApp.match_details.overall_assessment && (
                                            <div className={styles.overallAssessment}>
                                                <h5>Overall Assessment</h5>
                                                <p>{selectedApp.match_details.overall_assessment}</p>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Skills from resume */}
                        {selectedApp.user?.resume_parsed?.skills && selectedApp.user.resume_parsed.skills.length > 0 && (
                            <div className={styles.modalSection}>
                                <h4>Candidate Skills</h4>
                                <div className={styles.skillTags}>
                                    {selectedApp.user.resume_parsed.skills.map((skill, idx) => (
                                        <span key={idx} className="skill-tag">{skill}</span>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className={styles.modalSection}>
                            <h4>Current Status</h4>
                            <span className={`${styles.status} ${getStatusClass(selectedApp.status)}`}>
                                {selectedApp.status}
                            </span>
                        </div>

                        <div className={styles.modalActions}>
                            {selectedApp.status !== 'shortlisted' && selectedApp.status !== 'accepted' && (
                                <button
                                    className={styles.btnShortlist}
                                    onClick={() => updateStatus(selectedApp.application_id, 'shortlisted')}
                                >
                                    ✓ Shortlist
                                </button>
                            )}
                            {selectedApp.status === 'shortlisted' && (
                                <button
                                    className={styles.btnAccept}
                                    onClick={() => updateStatus(selectedApp.application_id, 'accepted')}
                                >
                                    ✓ Accept
                                </button>
                            )}
                            {selectedApp.status !== 'rejected' && selectedApp.status !== 'accepted' && (
                                <button
                                    className={styles.btnReject}
                                    onClick={() => updateStatus(selectedApp.application_id, 'rejected')}
                                >
                                    ✗ Reject
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
