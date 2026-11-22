'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { checkJobSeeker, getUser, getAuthHeaders } from '@/lib/auth';
import styles from './page.module.css';

import API from '@/lib/config';

export default function MyApplicationsPage() {
    const router = useRouter();
    const [applications, setApplications] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('');
    const [resumeFiles, setResumeFiles] = useState({});
    const [uploadingResume, setUploadingResume] = useState(null);
    const [resumeError, setResumeError] = useState('');

    useEffect(() => {
        if (!checkJobSeeker(router)) return;
        fetchApplications();
    }, [router]);

    const fetchApplications = async () => {
        const user = getUser();
        try {
            const res = await fetch(`${API}/applications/?user_id=${user.user_id}`, {
                headers: getAuthHeaders()
            });
            const data = await res.json();
            setApplications(data);
        } catch (err) {
            console.error('Error fetching applications:', err);
        } finally {
            setLoading(false);
        }
    };

    const uploadResume = async (applicationId) => {
        const file = resumeFiles[applicationId];
        if (!file) return;
        setUploadingResume(applicationId);
        setResumeError('');
        try {
            const body = new FormData();
            body.append('file', file);
            const response = await fetch(`${API}/applications/${applicationId}/resume`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` },
                body,
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Resume upload failed.');
            setResumeFiles(current => ({ ...current, [applicationId]: null }));
            await fetchApplications();
        } catch (error) {
            setResumeError(error.message || 'Resume upload failed.');
        } finally {
            setUploadingResume(null);
        }
    };

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

    if (loading) {
        return (
            <div className={styles.loading}>
                <div className="loading-spinner"></div>
                <p>Loading your applications...</p>
            </div>
        );
    }

    return (
        <div className="container">
            <div className={styles.header}>
                <h2>📋 My Applications</h2>
                <p>Track the status of your job applications</p>
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

            {filteredApps.length === 0 ? (
                <div className={styles.empty}>
                    <h3>No applications found</h3>
                    <p>Start applying to jobs to see them here!</p>
                    <Link href="/jobs" className="btn btn-primary">Browse Jobs</Link>
                </div>
            ) : (
                <div className={styles.appList}>
                    {filteredApps.map(app => (
                        <div key={app.application_id} className={styles.appCard}>
                            <div className={styles.appMain}>
                                <h3>{app.job?.role || 'Job Position'}</h3>
                                <div className={styles.appMeta}>
                                    <span>📍 {app.job?.job_location || 'Remote'}</span>
                                    <span>📅 Applied: {formatDate(app.applied_at)}</span>
                                </div>
                                {app.match_score !== null && app.match_score !== undefined && (
                                    <div className={styles.matchScore}>
                                        Match Score: <strong>{Math.round(app.match_score)}%</strong>
                                    </div>
                                )}
                            </div>
                            <div className={styles.appActions}>
                                <span className={`${styles.status} ${getStatusClass(app.status)}`}>
                                    {app.status}
                                </span>
                                {app.resume_required && (
                                    <div className={styles.resumeStep}>
                                        <p>Upload a resume to finish this application.</p>
                                        <input
                                            type="file"
                                            accept=".pdf,.docx"
                                            aria-label={`Resume for ${app.job?.role || 'application'}`}
                                            onChange={(event) => setResumeFiles(current => ({
                                                ...current,
                                                [app.application_id]: event.target.files?.[0] || null,
                                            }))}
                                        />
                                        <button
                                            type="button"
                                            className={styles.testBtn}
                                            onClick={() => uploadResume(app.application_id)}
                                            disabled={!resumeFiles[app.application_id] || uploadingResume === app.application_id}
                                        >
                                            {uploadingResume === app.application_id ? 'Uploading…' : 'Upload and finish'}
                                        </button>
                                        {resumeError && uploadingResume === null && <small role="alert">{resumeError}</small>}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
