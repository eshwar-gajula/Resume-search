'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { isLoggedIn, isRecruiter, saveAuth } from '@/lib/auth';
import styles from './page.module.css';

import API from '@/lib/config';

export default function RegisterPage() {
    const router = useRouter();
    const [userType, setUserType] = useState('job_seeker');
    const [formData, setFormData] = useState({
        firstName: '',
        lastName: '',
        email: '',
        password: '',
        mobile: '',
        country: '',
        gender: '',
        preferredLocation: '',
        hasExperience: false,
        yearsOfExperience: 0,
        hasGraduated: true,
        graduationYear: '',
        noticePeriod: ''
    });
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (isLoggedIn()) {
            if (isRecruiter()) {
                router.push('/recruiter/post-job');
            } else {
                router.push('/jobs');
            }
        }
    }, [router]);

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData({
            ...formData,
            [name]: type === 'checkbox' ? checked : value
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');

        setLoading(true);

        try {
            // Step 1: Register user
            const res = await fetch(`${API}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    first_name: formData.firstName,
                    last_name: formData.lastName,
                    email: formData.email,
                    password: formData.password,
                    user_type: userType,
                    mobile: formData.mobile || null,
                    country: formData.country || null,
                    gender: formData.gender || null,
                    preferred_location: formData.preferredLocation || null,
                    has_experience: formData.hasExperience,
                    years_of_experience: formData.hasExperience ? parseInt(formData.yearsOfExperience) || 0 : 0,
                    graduation_year: formData.hasGraduated && formData.graduationYear ? parseInt(formData.graduationYear) : null,
                    notice_period: formData.noticePeriod ? parseInt(formData.noticePeriod) : null
                })
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || 'Registration failed. Please try again.');
            }

            // Save auth immediately
            saveAuth(data.access_token, data.user);

            setSuccess('🎉 Registration complete! Redirecting...');

            setTimeout(() => {
                if (data.user.user_type === 'recruiter') {
                    router.push('/recruiter/post-job');
                } else {
                    router.push('/jobs');
                }
            }, 1500);

        } catch (err) {
            console.error('Registration error:', err);
            setError(err.message || 'Network error. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className={styles.container}>
            <div className={styles.card}>
                <div className={styles.logo}>
                    <h1>ResumeAI</h1>
                    <p>Create your account</p>
                </div>

                {error && <div className={styles.error}>{error}</div>}
                {success && <div className={styles.success}>{success}</div>}

                {/* User Type Toggle */}
                <div className={styles.toggle}>
                    <div
                        className={`${styles.toggleOption} ${userType === 'job_seeker' ? styles.active : ''}`}
                        onClick={() => setUserType('job_seeker')}
                    >
                        👤 Job Seeker
                    </div>
                    <div
                        className={`${styles.toggleOption} ${userType === 'recruiter' ? styles.active : ''}`}
                        onClick={() => setUserType('recruiter')}
                    >
                        💼 Recruiter
                    </div>
                </div>

                <div className={styles.roleDesc}>
                    {userType === 'recruiter'
                        ? <><strong>Recruiter:</strong> Post job openings, review applications, and find the perfect candidates using AI-powered matching.</>
                        : <><strong>Job Seeker:</strong> Upload your resume, browse jobs, and apply to positions. Our AI will match you with the best opportunities.</>
                    }
                </div>

                <form onSubmit={handleSubmit}>
                    {/* Basic Info - Both */}
                    <div className={styles.section}>
                        <h3>Basic Information</h3>
                        <div className={styles.formRow}>
                            <div className={styles.formGroup}>
                                <label>First Name *</label>
                                <input
                                    type="text"
                                    name="firstName"
                                    value={formData.firstName}
                                    onChange={handleChange}
                                    placeholder="John"
                                    required
                                />
                            </div>
                            <div className={styles.formGroup}>
                                <label>Last Name *</label>
                                <input
                                    type="text"
                                    name="lastName"
                                    value={formData.lastName}
                                    onChange={handleChange}
                                    placeholder="Doe"
                                    required
                                />
                            </div>
                        </div>

                        <div className={styles.formGroup}>
                            <label>Email Address *</label>
                            <input
                                type="email"
                                name="email"
                                value={formData.email}
                                onChange={handleChange}
                                placeholder="you@example.com"
                                required
                            />
                        </div>

                        <div className={styles.formGroup}>
                            <label>Password *</label>
                            <input
                                type="password"
                                name="password"
                                value={formData.password}
                                onChange={handleChange}
                                    placeholder="Min. 8 characters"
                                required
                                    minLength={8}
                            />
                        </div>

                        <div className={styles.formRow}>
                            <div className={styles.formGroup}>
                                <label>Mobile *</label>
                                <input
                                    type="tel"
                                    name="mobile"
                                    value={formData.mobile}
                                    onChange={handleChange}
                                    placeholder="+91 9876543210"
                                    required
                                />
                            </div>
                            <div className={styles.formGroup}>
                                <label>Country *</label>
                                <input
                                    type="text"
                                    name="country"
                                    value={formData.country}
                                    onChange={handleChange}
                                    placeholder="India"
                                    required
                                />
                            </div>
                        </div>
                    </div>

                    {/* Job Seeker Specific Fields */}
                    {userType === 'job_seeker' && (
                        <>
                            <div className={styles.section}>
                                <h3>Profile Details</h3>

                                {/* Gender & Location Row */}
                                <div className={styles.formRow}>
                                    <div className={styles.formGroup}>
                                        <label>Gender *</label>
                                        <select
                                            name="gender"
                                            value={formData.gender}
                                            onChange={handleChange}
                                            required
                                        >
                                            <option value="">Select</option>
                                            <option value="male">Male</option>
                                            <option value="female">Female</option>
                                            <option value="other">Other</option>
                                            <option value="prefer_not_to_say">Prefer not to say</option>
                                        </select>
                                    </div>
                                    <div className={styles.formGroup}>
                                        <label>Preferred Location *</label>
                                        <input
                                            type="text"
                                            name="preferredLocation"
                                            value={formData.preferredLocation}
                                            onChange={handleChange}
                                            placeholder="e.g., Bangalore, Remote"
                                            required
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className={styles.section}>
                                <h3>Education</h3>
                                <div className={styles.checkboxGroup}>
                                    <label>
                                        <input
                                            type="checkbox"
                                            name="hasGraduated"
                                            checked={formData.hasGraduated}
                                            onChange={handleChange}
                                        />
                                        <span>I have completed my graduation</span>
                                    </label>
                                </div>
                                {formData.hasGraduated && (
                                    <div className={styles.formGroup}>
                                        <label>Graduation Year *</label>
                                        <input
                                            type="number"
                                            name="graduationYear"
                                            value={formData.graduationYear}
                                            onChange={handleChange}
                                            placeholder="2023"
                                            min="1970"
                                            max="2030"
                                            required
                                        />
                                    </div>
                                )}
                            </div>

                            <div className={styles.section}>
                                <h3>Work Experience</h3>
                                <div className={styles.checkboxGroup}>
                                    <label>
                                        <input
                                            type="checkbox"
                                            name="hasExperience"
                                            checked={formData.hasExperience}
                                            onChange={handleChange}
                                        />
                                        <span>I have work experience</span>
                                    </label>
                                </div>
                                {formData.hasExperience && (
                                    <div className={styles.formRow}>
                                        <div className={styles.formGroup}>
                                            <label>Years of Experience *</label>
                                            <input
                                                type="number"
                                                name="yearsOfExperience"
                                                value={formData.yearsOfExperience}
                                                onChange={handleChange}
                                                placeholder="2"
                                                min="0"
                                                max="50"
                                                required
                                            />
                                        </div>
                                        <div className={styles.formGroup}>
                                            <label>Notice Period (days)</label>
                                            <input
                                                type="number"
                                                name="noticePeriod"
                                                value={formData.noticePeriod}
                                                onChange={handleChange}
                                                placeholder="30"
                                                min="0"
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>

                            <p className={styles.hint}>
                                You can upload your resume after completing the screening questions for a job.
                            </p>
                        </>
                    )}

                    <button type="submit" disabled={loading} className={styles.submitBtn}>
                        {loading ? 'Creating account...' : 'Create Account'}
                    </button>
                </form>

                <div className={styles.divider}>
                    <span>Already have an account?</span>
                </div>

                <div className={styles.loginLink}>
                    <Link href="/login">Sign in instead →</Link>
                </div>
            </div>
        </div >
    );
}
