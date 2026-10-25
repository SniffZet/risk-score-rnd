import React from 'react';
import type { CustomerListItem, SortKey, SortOrder } from '../api/types';
import { eur0 } from '../format';
import { ScorePill } from './ScorePill';

const COLUMNS: { key: SortKey; label: string; num?: boolean; width: string }[] = [
  { key: 'accountId', label: 'ID', width: '6%' },
  { key: 'email', label: 'Email', width: '21%' },
  { key: 'balance', label: 'Баланс', num: true, width: '10%' },
  { key: 'totalReplenished', label: 'Пополнено', num: true, width: '11%' },
  { key: 'score', label: 'Score · уровень', num: true, width: '14%' },
];
const REASON_WIDTH = '27%';
const LOSS_WIDTH = '11%';

const SORT_VALUE: Record<SortKey, (c: CustomerListItem) => number | string | null> = {
  accountId: (c) => c.accountId,
  email: (c) => c.email.toLowerCase(),
  balance: (c) => c.balance,
  totalReplenished: (c) => c.totalReplenished,
  score: (c) => c.score,
  expectedLoss: (c) => c.expectedLoss,
  revenue: (c) => c.revenue,
  loyalty: (c) => c.loyalty,
};

export function sortCustomers(items: CustomerListItem[], sort: SortKey, order: SortOrder) {
  const dir = order === 'asc' ? 1 : -1;
  return [...items].sort((a, b) => {
    const x = SORT_VALUE[sort](a), y = SORT_VALUE[sort](b);
    if (x === null || y === null) return x === y ? 0 : x === null ? 1 : -1;
    if (x === y) return (b.expectedLoss - a.expectedLoss) * (order === 'asc' ? -1 : 1);
    return (x < y ? -1 : 1) * dir;
  });
}

export function nextSort(current: SortKey, order: SortOrder, key: SortKey): [SortKey, SortOrder] {
  if (current === key) return [key, order === 'asc' ? 'desc' : 'asc'];
  return [key, key === 'accountId' || key === 'email' ? 'asc' : 'desc'];
}

function reasonCell(c: CustomerListItem) {
  if (c.score === null) return <span className="muted">Нет активных услуг — оценки нет</span>;
  if (c.reasons.length === 0) return <span className="muted">Признаков риска нет</span>;
  const rest = c.reasons.slice(1);
  return (
    <>
      <div className="reason-line">
        <span className="ellipsis" title={c.reasons.map((r) => r.text).join('\n')}>{c.reasons[0].text}</span>
        {rest.length > 0 && <span className="more-chip" title={rest.map((r) => r.text).join('\n')}>+{rest.length}</span>}
      </div>
      {c.action && <span className="action-badge small" title={c.action.text}>{c.action.title}</span>}
    </>
  );
}

interface CustomersTableProps {
  items: CustomerListItem[];
  sort: SortKey;
  order: SortOrder;
  onSort: (key: SortKey) => void;
  onOpen: (id: number) => void;
}

export const CustomersTable: React.FC<CustomersTableProps> = ({ items, sort, order, onSort, onOpen }) => {
  const icon = (key: SortKey) => (sort !== key ? ' ↕' : order === 'asc' ? ' ↑' : ' ↓');
  const aria = (key: SortKey) => (sort !== key ? 'none' : order === 'asc' ? 'ascending' : 'descending');

  const header = (key: SortKey, label: string, num?: boolean) => (
    <th key={key} className={`sortable ${num ? 'num' : ''}`} aria-sort={aria(key)} onClick={() => onSort(key)}>
      {label}{icon(key)}
    </th>
  );

  return (
    <div className="table-responsive">
      <table className="clients-table fit">
        <colgroup>
          {COLUMNS.map((col) => <col key={col.key} style={{ width: col.width }} />)}
          <col style={{ width: REASON_WIDTH }} />
          <col style={{ width: LOSS_WIDTH }} />
        </colgroup>
        <thead>
          <tr>
            {COLUMNS.map(({ key, label, num }) => header(key, label, num))}
            <th>Главная причина и что делать</th>
            {header('expectedLoss', 'Потери', true)}
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr><td colSpan={7} className="empty">Клиенты не найдены</td></tr>
          )}
          {items.map((c) => (
            <tr
              key={c.accountId}
              className="clickable"
              tabIndex={0}
              role="link"
              aria-label={`Открыть карточку ${c.email}`}
              onClick={() => onOpen(c.accountId)}
              onKeyDown={(e) => { if (e.key === 'Enter') onOpen(c.accountId); }}
            >
              <td className="muted">{c.accountId}</td>
              <td className="ellipsis" title={c.email}>{c.email}</td>
              <td className="num">{eur0(c.balance)}</td>
              <td className="num">{eur0(c.totalReplenished)}</td>
              <td className="num"><ScorePill score={c.score} level={c.level} loyalty={c.loyalty} /></td>
              <td className="reason-cell">{reasonCell(c)}</td>
              <td className="num"><b>{eur0(c.expectedLoss)}</b></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
