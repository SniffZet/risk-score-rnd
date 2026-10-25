import React from 'react';
import type { PaymentTerm, Summary } from '../api/types';
import { eur, pct, TERM_LABEL_LONG } from '../format';

export const TermBreakdown: React.FC<{ summary: Summary }> = ({ summary }) => {
  const rows = (Object.keys(TERM_LABEL_LONG) as PaymentTerm[])
    .map((term) => ({ term, revenue: summary.revenueByTerm?.[term] ?? 0, loss: summary.expectedLossByTerm?.[term] ?? 0 }))
    .filter((r) => r.revenue > 0 || r.loss > 0)
    .sort((a, b) => b.loss - a.loss);
  const total = summary.expectedLossTotal;

  return (
    <div className="table-responsive">
      <table className="clients-table">
        <thead>
          <tr>
            <th>Период оплаты</th>
            <th className="num">Выручка в горизонте</th>
            <th className="num">Можем потерять</th>
            <th className="num">Доля потерь</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.term}>
              <td>{TERM_LABEL_LONG[r.term]}</td>
              <td className="num">{eur(r.revenue)}</td>
              <td className="num">{eur(r.loss)}</td>
              <td className="num">{total > 0 ? pct(r.loss / total) : '—'}</td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={4} className="empty">Живых услуг нет</td></tr>}
        </tbody>
      </table>
    </div>
  );
};
