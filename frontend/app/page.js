'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isLoggedIn, isRecruiter } from '@/lib/auth';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to appropriate page based on auth status
    if (isLoggedIn()) {
      if (isRecruiter()) {
        router.push('/recruiter/post-job');
      } else {
        router.push('/jobs');
      }
    } else {
      router.push('/login');
    }
  }, [router]);

  return (
    <div style={{ textAlign: 'center', padding: '100px 20px' }}>
      <div className="loading-spinner"></div>
      <p style={{ color: '#888' }}>Redirecting...</p>
    </div>
  );
}
