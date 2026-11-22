'use client';

import { Suspense } from 'react';
import SkillTestContent from './SkillTestContent';

export default function SkillTestPage() {
    return (
        <Suspense fallback={
            <div style={{ textAlign: 'center', padding: '60px' }}>
                <div className="loading-spinner"></div>
                <p style={{ color: '#888' }}>Loading...</p>
            </div>
        }>
            <SkillTestContent />
        </Suspense>
    );
}
