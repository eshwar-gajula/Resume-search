'use client';

import { useState, useEffect } from 'react';
import { isLoggedIn, isRecruiter, getAuthHeaders } from '@/lib/auth';
import { useRouter } from 'next/navigation';
import AccessDenied from '@/components/AccessDenied';
import styles from './page.module.css';

import API from '@/lib/config';

export default function PostJobPage() {
    const router = useRouter();
    const [hasAccess, setHasAccess] = useState(null); // null = loading, true/false = checked
    const [formData, setFormData] = useState({
        role: '',
        description: '',
        responsibilities: '',
        skills: '',
        job_location: '',
        job_country: '',
        years_of_experience: 0,
        highest_education_qualification: ''
    });
    const [questions, setQuestions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState('');
    const [error, setError] = useState('');

    useEffect(() => {
        // Check access on mount
        if (!isLoggedIn()) {
            router.push('/login');
            return;
        }
        setHasAccess(isRecruiter());
    }, [router]);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: name === 'years_of_experience' ? parseInt(value) || 0 : value
        }));
    };

    const addQuestion = () => {
        setQuestions([...questions, {
            question_text: '',
            question_type: 'text',
            options: []
        }]);
    };

    const updateQuestion = (idx, field, value) => {
        const updated = [...questions];
        updated[idx][field] = value;
        setQuestions(updated);
    };

    const removeQuestion = (idx) => {
        setQuestions(questions.filter((_, i) => i !== idx));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        setSuccess('');

        try {
            const jobRes = await fetch(`${API}/jobs/`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    ...formData,
                    skills: formData.skills.split(',').map(s => s.trim()).filter(Boolean)
                })
            });

            if (!jobRes.ok) {
                const data = await jobRes.json();
                throw new Error(data.detail || 'Failed to create job');
            }

            const job = await jobRes.json();

            if (questions.length > 0) {
                const qRes = await fetch(`${API}/questions/bulk/${job.job_id}`, {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify(
                        questions.map((q, idx) => ({
                            job_id: job.job_id,
                            question_text: q.question_text,
                            question_type: q.question_type,
                            options: q.question_type === 'multiple_choice'
                                ? (q.options_text || '').split(',').map(o => o.trim()).filter(Boolean)
                                : [],
                            order: idx
                        }))
                    )
                });

                if (!qRes.ok) {
                    console.warn('Failed to add questions, but job was created');
                }
            }

            setSuccess('✅ Job posted successfully!');
            setFormData({
                role: '', description: '', responsibilities: '', skills: '',
                job_location: '', job_country: '', years_of_experience: 0,
                highest_education_qualification: ''
            });
            setQuestions([]);

        } catch (err) {
            setError(err.message || 'Failed to post job');
        } finally {
            setLoading(false);
        }
    };

    // Loading state
    if (hasAccess === null) {
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
                message="This page is reserved for recruiters to post job listings. If you're looking for opportunities, browse our available positions!"
                linkText="Browse Jobs"
                linkHref="/jobs"
            />
        );
    }

    return (
        <div className="container">
            <div className={styles.header}>
                <h2>📝 Post a New Job</h2>
                <p>Fill in the details to create a job listing</p>
            </div>

            {success && <div className="success-message">{success}</div>}
            {error && <div className="error-message">{error}</div>}

            <form onSubmit={handleSubmit} className={styles.form}>
                <div className={styles.section}>
                    <h3>Basic Information</h3>

                    <div className={styles.formGroup}>
                        <label>Job Title / Role *</label>
                        <input
                            type="text"
                            name="role"
                            value={formData.role}
                            onChange={handleChange}
                            placeholder="e.g., Senior Software Engineer"
                            required
                        />
                    </div>

                    <div className={styles.formGroup}>
                        <label>Description *</label>
                        <textarea
                            name="description"
                            value={formData.description}
                            onChange={handleChange}
                            placeholder="Describe the role and what the candidate will be doing..."
                            rows={4}
                            required
                        />
                    </div>

                    <div className={styles.formGroup}>
                        <label>Responsibilities</label>
                        <textarea
                            name="responsibilities"
                            value={formData.responsibilities}
                            onChange={handleChange}
                            placeholder="List the key responsibilities..."
                            rows={3}
                        />
                    </div>

                    <div className={styles.formGroup}>
                        <label>Required Skills (comma-separated) *</label>
                        <input
                            type="text"
                            name="skills"
                            value={formData.skills}
                            onChange={handleChange}
                            placeholder="e.g., Python, React, SQL, AWS"
                            required
                        />
                    </div>
                </div>

                <div className={styles.section}>
                    <h3>Requirements</h3>

                    <div className={styles.formRow}>
                        <div className={styles.formGroup}>
                            <label>Location</label>
                            <input
                                type="text"
                                name="job_location"
                                value={formData.job_location}
                                onChange={handleChange}
                                placeholder="e.g., Bangalore"
                            />
                        </div>
                        <div className={styles.formGroup}>
                            <label>Country</label>
                            <input
                                type="text"
                                name="job_country"
                                value={formData.job_country}
                                onChange={handleChange}
                                placeholder="e.g., India"
                            />
                        </div>
                    </div>

                    <div className={styles.formRow}>
                        <div className={styles.formGroup}>
                            <label>Years of Experience</label>
                            <input
                                type="number"
                                name="years_of_experience"
                                value={formData.years_of_experience}
                                onChange={handleChange}
                                min="0"
                            />
                        </div>
                        <div className={styles.formGroup}>
                            <label>Education</label>
                            <select
                                name="highest_education_qualification"
                                value={formData.highest_education_qualification}
                                onChange={handleChange}
                            >
                                <option value="">Any</option>
                                <option value="Bachelor's">Bachelor's</option>
                                <option value="Master's">Master's</option>
                                <option value="PhD">PhD</option>
                            </select>
                        </div>
                    </div>
                </div>

                <div className={styles.section}>
                    <div className={styles.sectionHeader}>
                        <h3>Screening Questions (Optional)</h3>
                        <button type="button" onClick={addQuestion} className={styles.addBtn}>
                            + Add Question
                        </button>
                    </div>

                    {questions.map((q, idx) => (
                        <div key={idx} className={styles.questionCard}>
                            <div className={styles.questionHeader}>
                                <span>Question {idx + 1}</span>
                                <button type="button" onClick={() => removeQuestion(idx)} className={styles.removeBtn}>
                                    ×
                                </button>
                            </div>
                            <div className={styles.formGroup}>
                                <input
                                    type="text"
                                    placeholder="Enter your question"
                                    value={q.question_text}
                                    onChange={(e) => updateQuestion(idx, 'question_text', e.target.value)}
                                />
                            </div>
                            <div className={styles.formRow}>
                                <select
                                    value={q.question_type}
                                    onChange={(e) => updateQuestion(idx, 'question_type', e.target.value)}
                                >
                                    <option value="text">Text Answer</option>
                                    <option value="multiple_choice">Multiple Choice</option>
                                </select>
                                {q.question_type === 'multiple_choice' && (
                                    <input
                                        type="text"
                                        placeholder="Options (comma-separated)"
                                        value={q.options_text || ''}
                                        onChange={(e) => updateQuestion(idx, 'options_text', e.target.value)}
                                    />
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                <button type="submit" disabled={loading} className="btn btn-primary">
                    {loading ? 'Posting...' : 'Post Job'}
                </button>
            </form>
        </div>
    );
}
