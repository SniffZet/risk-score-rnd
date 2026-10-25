import React from 'react';
import type { Level } from '../api/types';
import { LEVEL_LABEL } from '../format';

export const LevelBadge: React.FC<{ level: Level }> = ({ level }) => (
  <span
    className={`badge badge-${level}`}
    title={level === 'no_data' ? 'У клиента нет активных услуг — оценивать нечего' : undefined}
  >
    {LEVEL_LABEL[level]}
  </span>
);
