'use client';

/**
 * Auth Utility - Centralized authentication management for Next.js
 */

import API_BASE from '@/lib/config';

// Get stored auth data (client-side only)
export function getToken() {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('authToken');
}

export function getUser() {
    if (typeof window === 'undefined') return {};
    try {
        return JSON.parse(localStorage.getItem('user') || '{}');
    } catch {
        return {};
    }
}

export function isLoggedIn() {
    const token = getToken();
    const user = getUser();
    return !!(token && user.user_id);
}

export function isRecruiter() {
    return getUser().user_type === 'recruiter';
}

export function isJobSeeker() {
    return getUser().user_type === 'job_seeker';
}

// Logout and redirect
export function logout() {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    window.location.href = '/login';
}

// Save auth data after login
export function saveAuth(token, user) {
    localStorage.setItem('authToken', token);
    localStorage.setItem('user', JSON.stringify(user));
}

// Helper to get auth headers for API calls
export function getAuthHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`
    };
}

// Auth check hook (for use in components)
export function checkAuth(router) {
    if (!isLoggedIn()) {
        router.push('/login');
        return false;
    }
    return true;
}

export function checkRecruiter(router) {
    if (!isLoggedIn()) {
        router.push('/login');
        return false;
    }
    if (!isRecruiter()) {
        alert('Access denied. Recruiter account required.');
        router.push('/jobs');
        return false;
    }
    return true;
}

export function checkJobSeeker(router) {
    if (!isLoggedIn()) {
        router.push('/login');
        return false;
    }
    if (!isJobSeeker()) {
        alert('This page is for job seekers. Redirecting to recruiter dashboard.');
        router.push('/recruiter/post-job');
        return false;
    }
    return true;
}
