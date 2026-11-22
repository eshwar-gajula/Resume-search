'use client';

import Link from 'next/link';
import styles from './AccessDenied.module.css';

export default function AccessDenied({
    title = "Access Restricted",
    message = "You don't have permission to access this page.",
    linkText = "Go to Jobs",
    linkHref = "/jobs"
}) {
    return (
        <div className={styles.container}>
            <div className={styles.card}>
                <div className={styles.icon}>🔒</div>
                <h2>{title}</h2>
                <p>{message}</p>
                <Link href={linkHref} className={styles.link}>
                    {linkText}
                </Link>
            </div>
        </div>
    );
}
