'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { checkAuth, getUser, isRecruiter, getAuthHeaders } from '@/lib/auth';
import styles from './page.module.css';

import API from '@/lib/config';

export default function JobsPage() {
    const router = useRouter();
    const [jobs, setJobs] = useState([]);
    const [filteredJobs, setFilteredJobs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [locationFilter, setLocationFilter] = useState('');
    const [experienceFilter, setExperienceFilter] = useState('');
    const [sortBy, setSortBy] = useState('newest');
    const [locations, setLocations] = useState([]);
    const [selectedJob, setSelectedJob] = useState(null);
    const [recruiterUser, setRecruiterUser] = useState(false);

    // Pagination state
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(9);

    // Application modal state
    const [applyingJob, setApplyingJob] = useState(null);
    const [questions, setQuestions] = useState([]);
    const [answers, setAnswers] = useState({});
    const [loadingQuestions, setLoadingQuestions] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [resumeFile, setResumeFile] = useState(null);
    const [applicationId, setApplicationId] = useState(null);
    const [applicationStep, setApplicationStep] = useState('screening');

    useEffect(() => {
        if (!checkAuth(router)) return;
        setRecruiterUser(isRecruiter());
        fetchJobs();
    }, [router]);

    const fetchJobs = async () => {
        try {
            const res = await fetch(`${API}/jobs/`);
            const data = await res.json();
            setJobs(Array.isArray(data) ? data : []);
            setFilteredJobs(Array.isArray(data) ? data : []);

            const locs = [...new Set((data || []).map(j => j.job_location).filter(Boolean))];
            setLocations(locs);
        } catch (err) {
            console.error('Error fetching jobs:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        let filtered = jobs.filter(job => {
            if (search) {
                const searchIn = `${job.role} ${job.description || ''} ${(job.skills || []).join(' ')}`.toLowerCase();
                if (!searchIn.includes(search.toLowerCase())) return false;
            }
            if (locationFilter && job.job_location !== locationFilter) return false;
            if (experienceFilter && (job.years_of_experience || 0) > parseInt(experienceFilter)) return false;
            return true;
        });

        // Apply sorting
        filtered.sort((a, b) => {
            switch (sortBy) {
                case 'newest':
                    return new Date(b.created_at || 0) - new Date(a.created_at || 0);
                case 'oldest':
                    return new Date(a.created_at || 0) - new Date(b.created_at || 0);
                case 'experience_low':
                    return (a.years_of_experience || 0) - (b.years_of_experience || 0);
                case 'experience_high':
                    return (b.years_of_experience || 0) - (a.years_of_experience || 0);
                case 'title_az':
                    return (a.role || '').localeCompare(b.role || '');
                case 'title_za':
                    return (b.role || '').localeCompare(a.role || '');
                default:
                    return 0;
            }
        });

        setFilteredJobs(filtered);
        setCurrentPage(1); // Reset to page 1 when filters change
    }, [search, locationFilter, experienceFilter, sortBy, jobs]);

    // Start application - fetch questions and check for existing resume
    const startApplication = async (job) => {
        setApplyingJob(job);
        setAnswers({});
        setResumeFile(null);
        setApplicationId(null);
        setApplicationStep('screening');
        setLoadingQuestions(true);

        try {
            const res = await fetch(`${API}/questions/job/${job.job_id}`, {
                headers: getAuthHeaders()
            });
            const data = await res.json();
            setQuestions(Array.isArray(data) ? data : []);
        } catch (err) {
            console.error('Error fetching questions:', err);
            setQuestions([]);
        } finally {
            setLoadingQuestions(false);
        }
    };

    const handleAnswer = (questionId, value) => {
        setAnswers(prev => ({
            ...prev,
            [questionId]: value
        }));
    };

    const submitApplication = async () => {
        const unansweredRequired = questions.filter(question =>
            question.is_required && !String(answers[question.question_id] || '').trim()
        );
        if (unansweredRequired.length > 0) {
            alert('Please answer all required screening questions before submitting.');
            return;
        }

        setSubmitting(true);
        const user = getUser();

        try {
            const screeningAnswers = questions.length > 0
                ? questions.map(q => ({
                    question_id: q.question_id,
                    question: q.question_text,
                    answer: answers[q.question_id] || ''
                }))
                : null;

            const appRes = await fetch(`${API}/applications/`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    job_id: applyingJob.job_id,
                    user_id: user.user_id,
                    screening_answers: screeningAnswers
                })
            });

            if (!appRes.ok) {
                const data = await appRes.json();
                throw new Error(data.detail || 'Failed to submit application');
            }
            const created = await appRes.json();
            if (created.resume_required) {
                setApplicationId(created.application_id);
                setApplicationStep('resume');
            } else {
                alert('Your application has been received. You can check its status under My Applications.');
                closeApplicationModal();
            }

        } catch (err) {
            alert(`❌ ${err.message || 'Failed to submit application'}`);
        } finally {
            setSubmitting(false);
        }
    };

    const uploadApplicationResume = async () => {
        if (!applicationId || !resumeFile) {
            alert('Choose a PDF or Word resume to continue.');
            return;
        }
        setSubmitting(true);
        try {
            const formData = new FormData();
            formData.append('file', resumeFile);
            const response = await fetch(`${API}/applications/${applicationId}/resume`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` },
                body: formData,
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Resume upload failed. Please try again.');
            alert('Your resume has been received. You can check the application under My Applications.');
            closeApplicationModal();
        } catch (err) {
            alert(err.message || 'Resume upload failed. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    const closeApplicationModal = () => {
        setApplyingJob(null);
        setQuestions([]);
        setAnswers({});
        setResumeFile(null);
        setApplicationId(null);
        setApplicationStep('screening');
    };

    const handleResumeChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            // Validate file type
            const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
            if (!validTypes.includes(file.type)) {
                alert('Please upload a PDF or Word document.');
                return;
            }
            // Validate the same 10 MB limit enforced by the backend.
            if (file.size > 10 * 1024 * 1024) {
                alert('File size must be 10MB or less.');
                return;
            }
            setResumeFile(file);
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return 'Recently';
        const date = new Date(dateStr);
        const now = new Date();
        const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        return date.toLocaleDateString();
    };

    if (loading) {
        return (
            <div className={styles.loading}>
                <div className="loading-spinner"></div>
                <p>Loading jobs...</p>
            </div>
        );
    }

    return (
        <div className="container">
            <div className={styles.hero}>
                <h2>🔍 Discover Your Next Opportunity</h2>
                <p>Browse open positions and find your perfect match with AI-powered recommendations</p>
            </div>

            <div className={styles.filters}>
                <input
                    type="text"
                    placeholder="Search jobs by title, skills, or keywords..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className={styles.searchBox}
                />
                <select value={locationFilter} onChange={(e) => setLocationFilter(e.target.value)} className={styles.filterSelect}>
                    <option value="">All Locations</option>
                    {locations.map(loc => <option key={loc} value={loc}>{loc}</option>)}
                </select>
                <select value={experienceFilter} onChange={(e) => setExperienceFilter(e.target.value)} className={styles.filterSelect}>
                    <option value="">Any Experience</option>
                    <option value="0">Entry Level (0 years)</option>
                    <option value="1">1+ years</option>
                    <option value="3">3+ years</option>
                    <option value="5">5+ years</option>
                </select>
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className={styles.sortSelect}>
                    <option value="newest">Newest First</option>
                    <option value="oldest">Oldest First</option>
                    <option value="experience_low">Experience: Low to High</option>
                    <option value="experience_high">Experience: High to Low</option>
                    <option value="title_az">Title: A-Z</option>
                    <option value="title_za">Title: Z-A</option>
                </select>
            </div>

            <div className={styles.statsBar}>
                <span><strong>{jobs.length}</strong> jobs available</span>
                {filteredJobs.length !== jobs.length && (
                    <span>Showing <strong>{filteredJobs.length}</strong> of {jobs.length}</span>
                )}
            </div>

            <div className={styles.jobsGrid}>
                {filteredJobs.length === 0 ? (
                    <div className={styles.noJobs}>
                        <h3>No jobs found</h3>
                        <p>Try adjusting your search filters</p>
                    </div>
                ) : (
                    filteredJobs
                        .slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
                        .map(job => (
                            <div key={job.job_id} className={styles.jobCard}>
                                <h3>{job.role}</h3>
                                <div className={styles.jobMeta}>
                                    <span>📍 {job.job_location || 'Remote'}</span>
                                    <span>💼 {job.years_of_experience || 0}+ years</span>
                                    {job.highest_education_qualification && (
                                        <span>🎓 {job.highest_education_qualification}</span>
                                    )}
                                </div>
                                <p className={styles.jobDesc}>{job.description || 'No description provided.'}</p>
                                <div className={styles.skills}>
                                    {(job.skills || []).slice(0, 5).map(skill => (
                                        <span key={skill} className="skill-tag">{skill}</span>
                                    ))}
                                    {(job.skills || []).length > 5 && (
                                        <span className="skill-tag">+{job.skills.length - 5} more</span>
                                    )}
                                </div>
                                <div className={styles.jobFooter}>
                                    <span className={styles.postedDate}>{formatDate(job.created_at)}</span>
                                    <div>
                                        <button className={styles.btnView} onClick={() => setSelectedJob(job)}>
                                            View Details
                                        </button>
                                        {!recruiterUser && (
                                            <button className={styles.btnApply} onClick={() => startApplication(job)}>
                                                Apply
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))
                )}
            </div>

            {/* Pagination */}
            {filteredJobs.length > itemsPerPage && (
                <div className={styles.pagination}>
                    <button
                        className={styles.pageBtn}
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                    >
                        ← Prev
                    </button>

                    <div className={styles.pageNumbers}>
                        {Array.from({ length: Math.ceil(filteredJobs.length / itemsPerPage) }, (_, i) => i + 1)
                            .filter(page => {
                                const total = Math.ceil(filteredJobs.length / itemsPerPage);
                                if (total <= 7) return true;
                                if (page === 1 || page === total) return true;
                                if (Math.abs(page - currentPage) <= 1) return true;
                                return false;
                            })
                            .map((page, idx, arr) => (
                                <span key={page}>
                                    {idx > 0 && arr[idx - 1] !== page - 1 && <span className={styles.ellipsis}>...</span>}
                                    <button
                                        className={`${styles.pageNum} ${currentPage === page ? styles.activePage : ''}`}
                                        onClick={() => setCurrentPage(page)}
                                    >
                                        {page}
                                    </button>
                                </span>
                            ))
                        }
                    </div>

                    <button
                        className={styles.pageBtn}
                        onClick={() => setCurrentPage(p => Math.min(Math.ceil(filteredJobs.length / itemsPerPage), p + 1))}
                        disabled={currentPage >= Math.ceil(filteredJobs.length / itemsPerPage)}
                    >
                        Next →
                    </button>

                    <select
                        className={styles.perPageSelect}
                        value={itemsPerPage}
                        onChange={(e) => {
                            setItemsPerPage(Number(e.target.value));
                            setCurrentPage(1);
                        }}
                    >
                        <option value={6}>6 per page</option>
                        <option value={9}>9 per page</option>
                        <option value={12}>12 per page</option>
                        <option value={24}>24 per page</option>
                    </select>
                </div>
            )}

            {/* Job Details Modal */}
            {selectedJob && !applyingJob && (
                <div className="modal-overlay" onClick={() => setSelectedJob(null)}>
                    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                        <button className="modal-close" onClick={() => setSelectedJob(null)}>×</button>
                        <h2>{selectedJob.role}</h2>
                        <div className={styles.jobMeta}>
                            <span>📍 {selectedJob.job_location || 'Remote'}, {selectedJob.job_country || ''}</span>
                            <span>💼 {selectedJob.years_of_experience || 0}+ years experience</span>
                        </div>

                        <div className={styles.modalSection}>
                            <h4>Description</h4>
                            <p>{selectedJob.description || 'No description provided.'}</p>
                        </div>

                        <div className={styles.modalSection}>
                            <h4>Responsibilities</h4>
                            <p>{selectedJob.responsibilities || 'Not specified.'}</p>
                        </div>

                        <div className={styles.modalSection}>
                            <h4>Required Skills</h4>
                            <div className={styles.skills}>
                                {(selectedJob.skills || []).map(skill => (
                                    <span key={skill} className="skill-tag">{skill}</span>
                                ))}
                            </div>
                        </div>

                        <div className={styles.modalActions}>
                            {!recruiterUser && (
                                <button className={styles.btnApply} onClick={() => startApplication(selectedJob)}>
                                    Apply Now
                                </button>
                            )}
                            <button className={styles.btnView} onClick={() => setSelectedJob(null)}>Close</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Application Modal with Screening Questions */}
            {applyingJob && (
                <div className="modal-overlay" onClick={closeApplicationModal}>
                    <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                        <button className="modal-close" onClick={closeApplicationModal}>×</button>

                        <h2>Apply: {applyingJob.role}</h2>
                        <p style={{ color: '#888', marginBottom: '25px' }}>
                            📍 {applyingJob.job_location || 'Remote'}
                        </p>

                        {applicationStep === 'resume' ? (
                            <div className={styles.resumeSection}>
                                <h4 style={{ color: '#22d3ee', marginBottom: '12px' }}>📄 Finish your application</h4>
                                <p style={{ color: '#888', marginBottom: '18px' }}>
                                    Screening is complete. Upload a PDF or Word resume (up to 10 MB) to finish your application.
                                </p>
                                <p className={styles.integrityNotice} role="note">
                                    Your resume is parsed for skills and experience after it is received. If automatic parsing is unavailable, the uploaded file is kept for recruiter review.
                                </p>
                                <div className={styles.resumeUpload}>
                                    <input
                                        type="file"
                                        id="resumeInput"
                                        accept=".pdf,.docx"
                                        onChange={handleResumeChange}
                                        className={styles.fileInput}
                                    />
                                    <label htmlFor="resumeInput" className={styles.fileLabel}>
                                        {resumeFile ? `📎 ${resumeFile.name}` : '+ Select Resume File'}
                                    </label>
                                    {resumeFile && (
                                        <button type="button" className={styles.removeFile} onClick={() => setResumeFile(null)}>×</button>
                                    )}
                                </div>
                            </div>
                        ) : loadingQuestions ? (
                            <div style={{ textAlign: 'center', padding: '30px' }}>
                                <div className="loading-spinner"></div>
                                <p style={{ color: '#888' }}>Loading screening questions...</p>
                            </div>
                        ) : questions.length === 0 ? (
                            <div className={styles.noQuestions}>
                                <p>No screening questions for this position.</p>
                                <p style={{ color: '#888', fontSize: '14px' }}>
                                    Click submit to send your application.
                                </p>
                            </div>
                        ) : (
                            <div className={styles.questionsSection}>
                                <h4 style={{ color: '#22d3ee', marginBottom: '20px' }}>
                                    📝 Screening Questions ({questions.length})
                                </h4>
                                <p className={styles.integrityNotice} role="note">
                                    Free-text answers are checked for web-source similarity and AI-writing indicators. If a check is inconclusive or unavailable, the recruiter reviews the application manually. Automated indicators are estimates and cannot prove who wrote an answer.
                                </p>
                                {questions.map((q, idx) => (
                                    <div key={q.question_id} className={styles.questionCard}>
                                        <div className={styles.questionHeader}>
                                            <span>Question {idx + 1}</span>
                                            <span className={styles.questionType}>{q.question_type}</span>
                                        </div>
                                        <p className={styles.questionText}>{q.question_text}</p>

                                        {q.question_type === 'multiple_choice' ? (
                                            <div className={styles.options}>
                                                {(q.options || []).map((opt, i) => (
                                                    <label key={i} className={styles.option}>
                                                        <input
                                                            type="radio"
                                                            name={`q_${q.question_id}`}
                                                            value={opt}
                                                            checked={answers[q.question_id] === opt}
                                                            onChange={() => handleAnswer(q.question_id, opt)}
                                                        />
                                                        <span>{opt}</span>
                                                    </label>
                                                ))}
                                            </div>
                                        ) : (
                                            <textarea
                                                className={styles.textAnswer}
                                                placeholder="Type your answer here..."
                                                value={answers[q.question_id] || ''}
                                                onChange={(e) => handleAnswer(q.question_id, e.target.value)}
                                                rows={3}
                                            />
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}

                        <div className={styles.modalActions}>
                            <button
                                className={styles.btnApply}
                                onClick={applicationStep === 'resume' ? uploadApplicationResume : submitApplication}
                                disabled={submitting}
                            >
                                {submitting
                                    ? (applicationStep === 'resume' ? 'Uploading...' : 'Submitting...')
                                    : (applicationStep === 'resume' ? 'Upload Resume and Finish' : (questions.length ? 'Submit Answers' : 'Submit Application'))}
                            </button>
                            <button className={styles.btnView} onClick={closeApplicationModal}>
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )
            }
        </div >
    );
}
