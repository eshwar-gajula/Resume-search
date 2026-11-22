'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { checkJobSeeker, getAuthHeaders } from '@/lib/auth';
import styles from './page.module.css';

import API from '@/lib/config';

export default function SkillTestContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const jobId = searchParams.get('job_id');
    const applicationId = searchParams.get('application_id');

    const [questions, setQuestions] = useState([]);
    const [answers, setAnswers] = useState({});
    const [jobInfo, setJobInfo] = useState(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [submitted, setSubmitted] = useState(false);

    useEffect(() => {
        if (!checkJobSeeker(router)) return;
        if (jobId) {
            loadTest();
        } else {
            setLoading(false);
        }
    }, [router, jobId]);

    const loadTest = async () => {
        try {
            // Fetch job info
            const jobRes = await fetch(`${API}/jobs/${jobId}`, {
                headers: getAuthHeaders()
            });
            const job = await jobRes.json();
            setJobInfo(job);

            // Fetch questions
            const qRes = await fetch(`${API}/questions/job/${jobId}`, {
                headers: getAuthHeaders()
            });
            const qData = await qRes.json();
            setQuestions(qData);
        } catch (err) {
            console.error('Error loading test:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleAnswer = (questionId, value) => {
        setAnswers(prev => ({
            ...prev,
            [questionId]: value
        }));
    };

    const handleSubmit = async () => {
        if (!applicationId) {
            alert('Open this assessment from one of your applications so your answers can be saved.');
            return;
        }

        if (Object.keys(answers).length < questions.length) {
            alert('Please answer all questions before submitting.');
            return;
        }

        setSubmitting(true);
        try {
            const res = await fetch(`${API}/questions/answers/${applicationId}`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    answers: Object.entries(answers).map(([qId, answer]) => ({
                        question_id: parseInt(qId),
                        answer_text: answer
                    }))
                })
            });

            if (res.ok) {
                setSubmitted(true);
            } else {
                const data = await res.json();
                alert(`Error: ${data.detail || 'Failed to submit'}`);
            }
        } catch (err) {
            alert('Network error. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className={styles.loading}>
                <div className="loading-spinner"></div>
                <p>Loading skill test...</p>
            </div>
        );
    }

    if (!jobId) {
        return (
            <div className="container">
                <div className={styles.noTest}>
                    <h2>No Test Selected</h2>
                    <p>Please select a job from your applications to take the skill test.</p>
                    <button onClick={() => router.push('/my-applications')} className="btn btn-primary">
                        View My Applications
                    </button>
                </div>
            </div>
        );
    }

    if (submitted) {
        return (
            <div className="container">
                <div className={styles.success}>
                    <h2>✅ Test Submitted!</h2>
                    <p>Your answers have been recorded. The recruiter will review your responses.</p>
                    <button onClick={() => router.push('/my-applications')} className="btn btn-primary">
                        Back to Applications
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="container">
            <div className={styles.header}>
                <h2>📝 Skill Assessment</h2>
                {jobInfo && <p>Position: <strong>{jobInfo.role}</strong></p>}
            </div>

            <p className={styles.integrityNotice} role="note">
                Free-text answers may be sent to external services for web-source similarity and AI-writing pattern checks. When AI use cannot be ruled out, the application is routed to recruiter review. Automated checks cannot prove authorship.
            </p>

            {questions.length === 0 ? (
                <div className={styles.noQuestions}>
                    <p>No questions available for this job.</p>
                    <button onClick={() => router.push('/my-applications')} className="btn btn-secondary">
                        Back to Applications
                    </button>
                </div>
            ) : (
                <div className={styles.questions}>
                    {questions.map((q, idx) => (
                        <div key={q.question_id} className={styles.questionCard}>
                            <div className={styles.questionHeader}>
                                <span className={styles.questionNum}>Question {idx + 1}</span>
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
                                    rows={4}
                                />
                            )}
                        </div>
                    ))}

                    <div className={styles.actions}>
                        <button
                            className="btn btn-primary"
                            onClick={handleSubmit}
                            disabled={submitting}
                        >
                            {submitting ? 'Submitting...' : 'Submit Answers'}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
