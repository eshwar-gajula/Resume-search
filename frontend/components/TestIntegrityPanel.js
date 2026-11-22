'use client';

import styles from './TestIntegrityPanel.module.css';

function statusText(status) {
    switch (status) {
        case 'checked': return 'Checked';
        case 'not_configured': return 'Not configured';
        case 'insufficient_text': return 'Insufficient text';
        case 'unavailable': return 'Check unavailable';
        default: return 'Not checked';
    }
}

function statusClass(level) {
    if (level === 'high') return styles.high;
    if (level === 'moderate') return styles.moderate;
    if (level === 'low') return styles.low;
    return styles.neutral;
}

function verdictText(verdict) {
    switch (verdict) {
        case 'ai_generated': return 'Likely AI-generated';
        case 'human_written': return 'Likely human-written';
        case 'undetectable': return 'Undetectable';
        default: return 'No classification';
    }
}

function verdictClass(verdict) {
    if (verdict === 'ai_generated') return styles.high;
    if (verdict === 'human_written') return styles.low;
    return styles.neutral;
}

export default function TestIntegrityPanel({
    report,
    answers = [],
    matchOriginality = null,
    plagiarismScore = null,
    passedPlagiarism = null,
    onRunCheck,
    checking = false,
}) {
    const ai = report?.ai_detection;
    const web = report?.web_similarity;
    const rawMatchEstimate = matchOriginality || report?.match_originality;
    const matchEstimate = rawMatchEstimate ? {
        score: rawMatchEstimate.score ?? rawMatchEstimate.originality_score,
        suspicion_level: rawMatchEstimate.suspicion_level,
        signals: rawMatchEstimate.signals || rawMatchEstimate.suspicion_flags || [],
        summary: rawMatchEstimate.summary || rawMatchEstimate.assessment || '',
    } : null;
    const webScore = web?.score ?? plagiarismScore;
    const webPassed = web?.passed ?? passedPlagiarism;
    const webStatus = web?.status || (webScore !== null && webScore !== undefined ? 'checked' : 'not_checked');
    const routing = report?.routing;
    const hasAnswers = Array.isArray(answers) && answers.length > 0;

    return (
        <section className={styles.panel} aria-labelledby="test-integrity-title">
            <div className={styles.header}>
                <div>
                    <h4 id="test-integrity-title">Candidate answer review</h4>
                    <p>AI-authorship estimate and web-source similarity are checked separately.</p>
                </div>
                {onRunCheck && (
                    <button className={styles.runButton} onClick={onRunCheck} disabled={checking || !hasAnswers}>
                        {checking ? 'Checking…' : report ? 'Run checks again' : 'Run checks'}
                    </button>
                )}
            </div>

            <p className={styles.notice}>
                AI-writing signals and web-source similarity are separate checks. A concerning, inconclusive, or unavailable result is routed for human review; no automated result proves authorship or rejects an applicant.
            </p>
            {routing?.decision === 'manual_review' && (
                <div className={styles.reviewNotice}>
                    <strong>Manual review required</strong>
                    <p>{routing.summary || 'Review the answers and check context before making a decision.'}</p>
                    {routing.reasons?.length > 0 && (
                        <ul className={styles.reviewReasons}>
                            {routing.reasons.map((reason, index) => (
                                <li key={`${reason}-${index}`}>{reason.replace(/_/g, ' ')}</li>
                            ))}
                        </ul>
                    )}
                </div>
            )}

            <div className={styles.grid}>
                <article className={styles.result}>
                    <div className={styles.resultHeader}>
                        <h5>AI-authorship detector</h5>
                        <span className={`${styles.badge} ${ai?.status === 'checked' ? verdictClass(ai.verdict) : styles.neutral}`}>
                            {ai?.status === 'checked' ? verdictText(ai.verdict) : statusText(ai?.status)}
                        </span>
                    </div>
                    {ai?.summary && <p>{ai.summary}</p>}
                    {!ai?.summary && <p>No AI detector result has been saved for these answers.</p>}
                    {ai?.truncated && <p className={styles.small}>The provider checks up to 12,000 characters per submission.</p>}
                </article>

                <article className={styles.result}>
                    <div className={styles.resultHeader}>
                        <h5>Web-source similarity</h5>
                        <span className={`${styles.badge} ${webStatus === 'checked' ? (webPassed === false ? styles.high : styles.low) : styles.neutral}`}>
                            {statusText(webStatus)}
                        </span>
                    </div>
                    {webStatus === 'checked' ? (
                        <>
                            <p className={styles.score}>{Number(webScore).toFixed(1)}% provider-reported match</p>
                            <p>{webPassed === false ? 'Similarity is above the review threshold.' : 'No high web-source overlap was reported.'}</p>
                        </>
                    ) : (
                        <p>{web?.summary || 'No web-source check has been run for these answers.'}</p>
                    )}
                    {web?.truncated && <p className={styles.small}>The provider checks up to 3,000 characters per submission.</p>}
                </article>
            </div>

            {matchEstimate && (
                <article className={styles.matchEstimate}>
                    <div className={styles.resultHeader}>
                        <h5>Match-analysis originality estimate</h5>
                        <span className={`${styles.badge} ${statusClass(matchEstimate.suspicion_level)}`}>
                            {matchEstimate.suspicion_level || 'inconclusive'} suspicion
                        </span>
                    </div>
                    {matchEstimate.score !== null && matchEstimate.score !== undefined && (
                        <p className={styles.score}>{Number(matchEstimate.score).toFixed(0)}/100 originality score</p>
                    )}
                    {matchEstimate.summary && <p>{matchEstimate.summary}</p>}
                    {matchEstimate.signals?.length > 0 && (
                        <ul className={styles.signals}>
                            {matchEstimate.signals.map((signal, index) => <li key={`${signal}-${index}`}>{signal.replace(/_/g, ' ')}</li>)}
                        </ul>
                    )}
                    <p className={styles.small}>This score comes from the resume-match assessment. Scores below 40 are routed to recruiter manual review.</p>
                </article>
            )}

            <div className={styles.answers}>
                <h5>Submitted answers ({answers.length})</h5>
                {!hasAnswers ? (
                    <p>No submitted test answers are available.</p>
                ) : (
                    answers.map((answer, index) => (
                        <article className={styles.answer} key={`${answer.question_id ?? 'q'}-${index}`}>
                            <p className={styles.question}>Q{index + 1}: {answer.question || 'Question'}</p>
                            <p className={styles.answerText}>{answer.answer_text ?? answer.answer ?? ''}</p>
                            {answer.is_correct !== null && answer.is_correct !== undefined && (
                                <span className={styles.small}>Auto-graded: {answer.is_correct ? 'correct' : 'incorrect'}</span>
                            )}
                        </article>
                    ))
                )}
            </div>
        </section>
    );
}
