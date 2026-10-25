import React, { useState } from 'react';
import type { ChurnChart as ChurnChartData } from '../api/types';
import { shortDate } from '../format';

const W = 720;
const H = 240;
const PAD = { top: 14, right: 8, bottom: 36, left: 32 };

export const ChurnChart: React.FC<{ chart: ChurnChartData }> = ({ chart }) => {
  const [hover, setHover] = useState<number | null>(null);
  const { points, bucket, referenceDate } = chart;
  if (!Array.isArray(points)) return <p className="error">Ответ бэкенда в старом формате: перезапустите бэкенд и обновите страницу.</p>;
  if (points.length === 0) return <p className="muted">Удалений и ожидаемых непродлений нет.</p>;

  const max = Math.max(1, ...points.map((p) => Math.max(p.deleted, p.servicesAtRisk, p.expectedNonrenewals)));
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const slot = plotW / points.length;
  const barW = Math.max(2, Math.min(18, slot / 2 - 2));
  const y = (v: number) => PAD.top + plotH - (v / max) * plotH;
  const cx = (i: number) => PAD.left + slot * i + slot / 2;
  const ticks = [0, Math.round(max / 2), Math.ceil(max)].filter((t, i, a) => a.indexOf(t) === i);

  let refIndex = points.findIndex((p) => p.date > referenceDate);
  if (refIndex < 0) refIndex = points.length;
  refIndex = Math.max(0, refIndex - 1);
  const nowX = PAD.left + refIndex * slot;

  const labelEvery = Math.max(1, Math.ceil(points.length / Math.floor(plotW / 64)));
  const label = (iso: string) => (bucket === 'week' ? `с ${shortDate(iso)}` : shortDate(iso));
  const forecast = points.slice(refIndex);
  const linePath = forecast.map((p, i) => `${cx(refIndex + i).toFixed(1)},${y(p.expectedNonrenewals).toFixed(1)}`).join(' ');

  return (
    <div className="chart">
      <ul className="legend">
        <li><span className="legend-swatch swatch-fact" />Удалено (факт)</li>
        <li><span className="legend-swatch swatch-observed" />из них переход наблюдал анализатор</li>
        <li><span className="legend-swatch swatch-forecast" />Услуг под риском на дату продления (прогноз)</li>
        <li><span className="legend-swatch swatch-line" />Ожидаемые непродления (прогноз)</li>
      </ul>
      <div className="chart-box">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Отток услуг: факт и прогноз">
          <defs>
            <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" className="forecast-bg" />
              <line x1="0" y1="0" x2="0" y2="6" className="forecast-line" strokeWidth="3" />
            </pattern>
          </defs>

          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} className="grid" />
              <text x={PAD.left - 6} y={y(t) + 4} textAnchor="end" className="axis">{t}</text>
            </g>
          ))}

          <rect x={nowX} y={PAD.top} width={W - PAD.right - nowX} height={plotH} className="forecast-zone" />

          {points.map((p, i) => (
            <g key={p.date} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={PAD.left + slot * i} y={PAD.top} width={slot} height={plotH} fill="transparent" />
              {p.deleted > 0 && (
                <rect x={cx(i) - barW - 1} y={y(p.deleted)} width={barW} height={y(0) - y(p.deleted)} rx={2} className="bar-fact" />
              )}
              {p.deletedObserved > 0 && (
                <rect x={cx(i) - barW - 1} y={y(p.deletedObserved)} width={barW} height={y(0) - y(p.deletedObserved)} rx={2} className="bar-observed" />
              )}
              {p.servicesAtRisk > 0 && (
                <rect x={cx(i) + 1} y={y(p.servicesAtRisk)} width={barW} height={y(0) - y(p.servicesAtRisk)} rx={2}
                      fill="url(#hatch)" className="bar-forecast" />
              )}
              {i % labelEvery === 0 && (
                <text x={cx(i)} y={H - PAD.bottom + 16} textAnchor="middle" className="axis">{shortDate(p.date)}</text>
              )}
            </g>
          ))}

          {forecast.length > 1 && <polyline points={linePath} className="line-forecast" />}
          {forecast.map((p, i) => p.expectedNonrenewals > 0 && (
            <circle key={p.date} cx={cx(refIndex + i)} cy={y(p.expectedNonrenewals)} r={3} className="dot-forecast" />
          ))}

          <line x1={nowX} x2={nowX} y1={PAD.top} y2={y(0)} className="now-line" />
          <text x={nowX > W - 140 ? nowX - 4 : nowX + 4} y={PAD.top + 10} textAnchor={nowX > W - 140 ? 'end' : 'start'}
                className="axis">расчёт на {shortDate(referenceDate)}</text>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} className="baseline" />
        </svg>

        {hover !== null && (
          <div className="chart-tooltip" style={{ left: `${(cx(hover) / W) * 100}%` }}>
            <b>{label(points[hover].date)}</b>
            <div>Удалено: {points[hover].deleted}{points[hover].deletedObserved > 0 && ` (наблюдалось ${points[hover].deletedObserved})`}</div>
            <div>Услуг под риском: {points[hover].servicesAtRisk}</div>
            <div>Ожидаемых непродлений: {points[hover].expectedNonrenewals.toFixed(1)}</div>
          </div>
        )}
      </div>
      <p className="muted chart-note">
        Интервал: {bucket === 'week' ? 'неделя' : 'день'}. Дата удаления оценочная (конец оплаченного периода), если переход
        в «удалена» не наблюдался самим анализатором. Прогноз считается моделью и меняется вместе с весами.
      </p>
      <details className="chart-table">
        <summary>Таблица</summary>
        <table className="clients-table">
          <thead><tr><th>Дата</th><th className="num">Удалено (факт)</th><th className="num">Наблюдалось</th><th className="num">Под риском (прогноз)</th><th className="num">Непродления (прогноз)</th></tr></thead>
          <tbody>
            {points.filter((p) => p.deleted || p.servicesAtRisk || p.expectedNonrenewals).map((p) => (
              <tr key={p.date}>
                <td>{label(p.date)}</td>
                <td className="num">{p.deleted}</td>
                <td className="num">{p.deletedObserved}</td>
                <td className="num">{p.servicesAtRisk}</td>
                <td className="num">{p.expectedNonrenewals.toFixed(1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
};
