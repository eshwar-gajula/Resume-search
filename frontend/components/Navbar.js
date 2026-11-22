'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { getUser, isLoggedIn, isRecruiter, logout } from '@/lib/auth';
import styles from './Navbar.module.css';

export default function Navbar() {
    const pathname = usePathname();
    const [user, setUser] = useState(null);
    const [loggedIn, setLoggedIn] = useState(false);
    const [recruiter, setRecruiter] = useState(false);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        // Only check auth state after component mounts (client-side)
        setMounted(true);
        setUser(getUser());
        setLoggedIn(isLoggedIn());
        setRecruiter(isRecruiter());
    }, []);

    // Re-check auth state when pathname changes (e.g., after login)
    useEffect(() => {
        if (mounted) {
            setUser(getUser());
            setLoggedIn(isLoggedIn());
            setRecruiter(isRecruiter());
        }
    }, [pathname, mounted]);

    const handleLogout = () => {
        logout();
    };

    // Don't show navbar on login/register pages
    if (pathname === '/login' || pathname === '/register') {
        return null;
    }

    // Prevent hydration mismatch - show nothing until mounted
    if (!mounted) {
        return (
            <nav className={styles.navbar}>
                <div className={styles.container}>
                    <Link href="/jobs" className={styles.logo}>
                        ResumeAI
                    </Link>
                    <div className={styles.links}>
                        <Link href="/jobs" className={styles.link}>Browse Jobs</Link>
                    </div>
                </div>
            </nav>
        );
    }

    return (
        <nav className={styles.navbar}>
            <div className={styles.container}>
                <Link href="/jobs" className={styles.logo}>
                    ResumeAI
                </Link>
                <div className={styles.links}>
                    <Link
                        href="/jobs"
                        className={`${styles.link} ${pathname === '/jobs' ? styles.active : ''}`}
                    >
                        Browse Jobs
                    </Link>

                    {/* Recruiter-only links - hidden for job seekers */}
                    {loggedIn && recruiter && (
                        <>
                            <Link
                                href="/recruiter/post-job"
                                className={`${styles.link} ${pathname === '/recruiter/post-job' ? styles.active : ''}`}
                            >
                                Post a Job
                            </Link>
                            <Link
                                href="/recruiter/review-applicants"
                                className={`${styles.link} ${pathname === '/recruiter/review-applicants' ? styles.active : ''}`}
                            >
                                Review Applicants
                            </Link>
                            <Link
                                href="/recruiter/flagged-applications"
                                className={`${styles.link} ${styles.flaggedLink} ${pathname === '/recruiter/flagged-applications' ? styles.active : ''}`}
                            >
                                🚨 Flagged
                            </Link>
                        </>
                    )}

                    {/* Job seeker links */}
                    {loggedIn && !recruiter && (
                        <Link
                            href="/my-applications"
                            className={`${styles.link} ${pathname === '/my-applications' ? styles.active : ''}`}
                        >
                            My Applications
                        </Link>
                    )}

                    {/* Auth section */}
                    {loggedIn ? (
                        <>
                            <Link
                                href="/profile"
                                className={`${styles.link} ${pathname === '/profile' ? styles.active : ''}`}
                            >
                                Profile
                            </Link>
                            <span className={styles.userName}>{user?.first_name || 'User'}</span>
                            <button onClick={handleLogout} className={styles.logoutBtn}>
                                Logout
                            </button>
                        </>
                    ) : (
                        <Link href="/login" className={styles.loginBtn}>
                            Login
                        </Link>
                    )}
                </div>
            </div>
        </nav>
    );
}
