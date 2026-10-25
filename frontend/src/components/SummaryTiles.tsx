import React from 'react';
import type { Summary } from '../api/types';
import { eur, LEVEL_LABEL, LEVELS } from '../format';

export const SummaryTiles: React.FC<{ summary: Summary }> = ({ summary }) => (
  <div className="tiles">
    <div className="tile tile-accent">
      <div className="tile-label">Можем потерять за {summary.horizonDays} дн.</div>
      <div className="tile-value">{eur(summary.expectedLossTotal)}</div>
      <div className="tile-sub">
        из {eur(summary.revenueTotal)}, которые клиенты способны заплатить
        {summary.revenueFullTotal > summary.revenueTotal && <> · по прайсу {eur(summary.revenueFullTotal)}</>}
      </div>
    </div>
    <div className="tile">
      <div className="tile-label">Клиентов с высоким риском</div>
      <div className="tile-value">{summary.customersByLevel.high}</div>
      <div className="tile-sub">из {summary.customersTotal}</div>
    </div>
    <div className="tile">
      <div className="tile-label">Услуг под риском</div>
      <div className="tile-value">{summary.servicesAtRisk}</div>
      <div className="tile-sub">риск не ниже среднего порога</div>
    </div>
    <div className="tile">
      <div className="tile-label">Без оценки</div>
      <div className="tile-value">{summary.customersByLevel.no_data}</div>
      <div className="tile-sub">нет активных услуг</div>
    </div>
  </div>
);

export const LevelBar: React.FC<{ summary: Summary }> = ({ summary }) => {
  const total = summary.customersTotal || 1;
  return (
    <div className="level-bar-wrap">
      <div className="level-bar" role="img" aria-label="Распределение клиентов по уровням риска">
        {LEVELS.filter((l) => summary.customersByLevel[l] > 0).map((l) => (
          <div
            key={l}
            className={`level-seg seg-${l}`}
            style={{ flexGrow: summary.customersByLevel[l] / total }}
            title={`${LEVEL_LABEL[l]}: ${summary.customersByLevel[l]} клиентов, потери ${eur(summary.expectedLossByLevel[l])}`}
          />
        ))}
      </div>
      <ul className="legend">
        {LEVELS.map((l) => (
          <li key={l}>
            <span className={`legend-dot seg-${l}`} />
            {LEVEL_LABEL[l]}: <b>{summary.customersByLevel[l]}</b>
            <span className="muted"> · {eur(summary.expectedLossByLevel[l])}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};
