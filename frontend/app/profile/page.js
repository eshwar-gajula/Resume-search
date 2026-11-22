'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { isLoggedIn, getUser, getAuthHeaders, isRecruiter, saveAuth } from '@/lib/auth';
import styles from './page.module.css';

import API from '@/lib/config';

export default function ProfilePage() {
    const router = useRouter();
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState({ type: '', text: '' });
    const [isEditing, setIsEditing] = useState(false);

    const [formData, setFormData] = useState({
        first_name: '',
        last_name: '',
        mobile: '',
        country: '',
        gender: '',
        preferred_location: '',
        has_experience: false,
        years_of_experience: 0,
        graduation_year: '',
        notice_period: ''
    });

    useEffect(() => {
        if (!isLoggedIn()) {
            router.push('/login');
            return;
        }
        loadUserData();
    }, [router]);

    const loadUserData = async () => {
        const currentUser = getUser();
        if (!currentUser) {
            router.push('/login');
            return;
        }

        try {
            // Fetch fresh user data from API
            const res = await fetch(`${API}/users/${currentUser.user_id}`, {
                headers: getAuthHeaders()
            });

            if (res.ok) {
                const userData = await res.json();
                setUser(userData);
                setFormData({
                    first_name: userData.first_name || '',
                    last_name: userData.last_name || '',
                    mobile: userData.mobile || '',
                    country: userData.country || '',
                    gender: userData.gender || '',
                    preferred_location: userData.preferred_location || '',
                    has_experience: userData.has_experience || false,
                    years_of_experience: userData.years_of_experience || 0,
                    graduation_year: userData.graduation_year || '',
                    notice_period: userData.notice_period || ''
                });
            } else {
                // Fallback to local storage data
                setUser(currentUser);
                setFormData({
                    first_name: currentUser.first_name || '',
                    last_name: currentUser.last_name || '',
                    mobile: currentUser.mobile || '',
                    country: currentUser.country || '',
                    gender: currentUser.gender || '',
                    preferred_location: currentUser.preferred_location || '',
                    has_experience: currentUser.has_experience || false,
                    years_of_experience: currentUser.years_of_experience || 0,
                    graduation_year: currentUser.graduation_year || '',
                    notice_period: currentUser.notice_period || ''
                });
            }
        } catch (err) {
            console.error('Error loading user data:', err);
            setUser(getUser());
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    const handleSave = async () => {
        setSaving(true);
        setMessage({ type: '', text: '' });

        try {
            const res = await fetch(`${API}/users/${user.user_id}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    ...formData,
                    years_of_experience: formData.has_experience ? parseInt(formData.years_of_experience) || 0 : 0,
                    graduation_year: formData.graduation_year ? parseInt(formData.graduation_year) : null,
                    notice_period: formData.notice_period ? parseInt(formData.notice_period) : null
                })
            });

            if (res.ok) {
                const updatedUser = await res.json();
                setUser(updatedUser);

                // Update local storage
                const token = localStorage.getItem('authToken');
                saveAuth(token, updatedUser);

                setMessage({ type: 'success', text: 'Profile updated successfully!' });
                setIsEditing(false);
            } else {
                const data = await res.json();
                setMessage({ type: 'error', text: data.detail || 'Failed to update profile' });
            }
        } catch (err) {
            setMessage({ type: 'error', text: 'Network error. Please try again.' });
        } finally {
            setSaving(false);
        }
    };

    const cancelEdit = () => {
        setFormData({
            first_name: user.first_name || '',
            last_name: user.last_name || '',
            mobile: user.mobile || '',
            country: user.country || '',
            gender: user.gender || '',
            preferred_location: user.preferred_location || '',
            has_experience: user.has_experience || false,
            years_of_experience: user.years_of_experience || 0,
            graduation_year: user.graduation_year || '',
            notice_period: user.notice_period || ''
        });
        setIsEditing(false);
        setMessage({ type: '', text: '' });
    };

    if (loading) {
        return (
            <div className={styles.loading}>
                <div className="loading-spinner"></div>
                <p>Loading profile...</p>
            </div>
        );
    }

    const recruiterUser = isRecruiter();

    return (
        <div className="container">
            <div className={styles.header}>
                <h2>👤 My Profile</h2>
                <p>Manage your personal information and resume</p>
            </div>

            {message.text && (
                <div className={`${styles.message} ${styles[message.type]}`}>
                    {message.text}
                </div>
            )}

            <div className={styles.profileCard}>
                <div className={styles.cardHeader}>
                    <h3>Personal Information</h3>
                    {!isEditing ? (
                        <button className={styles.editBtn} onClick={() => setIsEditing(true)}>
                            ✏️ Edit
                        </button>
                    ) : (
                        <div className={styles.editActions}>
                            <button className={styles.saveBtn} onClick={handleSave} disabled={saving}>
                                {saving ? 'Saving...' : '💾 Save'}
                            </button>
                            <button className={styles.cancelBtn} onClick={cancelEdit}>
                                Cancel
                            </button>
                        </div>
                    )}
                </div>

                <div className={styles.cardBody}>
                    <div className={styles.formRow}>
                        <div className={styles.field}>
                            <label>First Name</label>
                            {isEditing ? (
                                <input
                                    type="text"
                                    name="first_name"
                                    value={formData.first_name}
                                    onChange={handleChange}
                                />
                            ) : (
                                <span>{user?.first_name || '-'}</span>
                            )}
                        </div>
                        <div className={styles.field}>
                            <label>Last Name</label>
                            {isEditing ? (
                                <input
                                    type="text"
                                    name="last_name"
                                    value={formData.last_name}
                                    onChange={handleChange}
                                />
                            ) : (
                                <span>{user?.last_name || '-'}</span>
                            )}
                        </div>
                    </div>

                    <div className={styles.formRow}>
                        <div className={styles.field}>
                            <label>Email</label>
                            <span className={styles.readonly}>{user?.email}</span>
                        </div>
                        <div className={styles.field}>
                            <label>Mobile</label>
                            {isEditing ? (
                                <input
                                    type="tel"
                                    name="mobile"
                                    value={formData.mobile}
                                    onChange={handleChange}
                                />
                            ) : (
                                <span>{user?.mobile || '-'}</span>
                            )}
                        </div>
                    </div>

                    <div className={styles.formRow}>
                        <div className={styles.field}>
                            <label>Country</label>
                            {isEditing ? (
                                <input
                                    type="text"
                                    name="country"
                                    value={formData.country}
                                    onChange={handleChange}
                                />
                            ) : (
                                <span>{user?.country || '-'}</span>
                            )}
                        </div>
                        <div className={styles.field}>
                            <label>Account Type</label>
                            <span className={styles.badge}>
                                {recruiterUser ? '💼 Recruiter' : '👤 Job Seeker'}
                            </span>
                        </div>
                    </div>

                    {/* Job Seeker specific fields */}
                    {!recruiterUser && (
                        <>
                            <div className={styles.divider}></div>
                            <h4 className={styles.sectionTitle}>Professional Details</h4>

                            <div className={styles.formRow}>
                                <div className={styles.field}>
                                    <label>Gender</label>
                                    {isEditing ? (
                                        <select name="gender" value={formData.gender} onChange={handleChange}>
                                            <option value="">Select</option>
                                            <option value="male">Male</option>
                                            <option value="female">Female</option>
                                            <option value="other">Other</option>
                                            <option value="prefer_not_to_say">Prefer not to say</option>
                                        </select>
                                    ) : (
                                        <span>{formData.gender || '-'}</span>
                                    )}
                                </div>
                                <div className={styles.field}>
                                    <label>Preferred Location</label>
                                    {isEditing ? (
                                        <input
                                            type="text"
                                            name="preferred_location"
                                            value={formData.preferred_location}
                                            onChange={handleChange}
                                        />
                                    ) : (
                                        <span>{user?.preferred_location || '-'}</span>
                                    )}
                                </div>
                            </div>

                            <div className={styles.formRow}>
                                <div className={styles.field}>
                                    <label>Graduation Year</label>
                                    {isEditing ? (
                                        <input
                                            type="number"
                                            name="graduation_year"
                                            value={formData.graduation_year}
                                            onChange={handleChange}
                                            min="1970"
                                            max="2030"
                                        />
                                    ) : (
                                        <span>{user?.graduation_year || '-'}</span>
                                    )}
                                </div>
                                <div className={styles.field}>
                                    <label>Notice Period (days)</label>
                                    {isEditing ? (
                                        <input
                                            type="number"
                                            name="notice_period"
                                            value={formData.notice_period}
                                            onChange={handleChange}
                                            min="0"
                                        />
                                    ) : (
                                        <span>{user?.notice_period ? `${user.notice_period} days` : '-'}</span>
                                    )}
                                </div>
                            </div>

                            <div className={styles.formRow}>
                                <div className={styles.field}>
                                    <label>Work Experience</label>
                                    {isEditing ? (
                                        <div className={styles.checkboxField}>
                                            <input
                                                type="checkbox"
                                                name="has_experience"
                                                checked={formData.has_experience}
                                                onChange={handleChange}
                                            />
                                            <span>I have work experience</span>
                                        </div>
                                    ) : (
                                        <span>{user?.has_experience ? 'Yes' : 'No'}</span>
                                    )}
                                </div>
                                {(formData.has_experience || user?.has_experience) && (
                                    <div className={styles.field}>
                                        <label>Years of Experience</label>
                                        {isEditing ? (
                                            <input
                                                type="number"
                                                name="years_of_experience"
                                                value={formData.years_of_experience}
                                                onChange={handleChange}
                                                min="0"
                                                max="50"
                                            />
                                        ) : (
                                            <span>{user?.years_of_experience || 0} years</span>
                                        )}
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>
            </div>

            {/* Resume Section - Job Seekers only */}
            {!recruiterUser && (
                <div className={styles.profileCard}>
                    <div className={styles.cardHeader}>
                        <h3>📄 Resume</h3>
                    </div>
                    <div className={styles.cardBody}>
                        {user?.resume_path ? (
                            <div className={styles.currentResume}>
                                <div className={styles.resumeInfo}>
                                    <span className={styles.resumeIcon}>📎</span>
                                    <div>
                                        <p className={styles.resumeName}>{user.resume_path.split('/').pop()}</p>
                                        <p className={styles.resumeStatus}>✅ Resume on file</p>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <p className={styles.noResume}>Upload your resume after completing the screening step for a job.</p>
                        )}
                        <Link href="/jobs" className="btn btn-secondary">Browse jobs</Link>
                    </div>
                </div>
            )}
        </div>
    );
}
