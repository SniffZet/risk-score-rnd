import React from 'react';
import type { Level } from '../api/types';
import { LEVEL_LABEL } from '../format';

export const ScorePill: React.FC<{ score: number | null; level: Level; loyalty?: number | null }> = ({ score, level, loyalty }) => {
  if (score === null) {
    return (
      <span className="score-pill score-none" title="Нет активных услуг — оценивать нечего">
        <span className="score-num">—</span>
        <span className="score-level">{LEVEL_LABEL.no_data}</span>
      </span>
    );
  }
  const title = `score ${score.toFixed(1)} из 100`
    + (loyalty !== null && loyalty !== undefined ? ` · лояльность ${loyalty}` : '');
  return (
    <span className={`score-pill level-${level}`} title={title}>
      <span className="score-num">{score.toFixed(1)}</span>
      <span className="score-level">{LEVEL_LABEL[level]}</span>
      <span className="score-track" aria-hidden="true">
        <span className="score-fill" style={{ width: `${Math.max(2, Math.min(100, score))}%` }} />
      </span>
    </span>
  );
};
