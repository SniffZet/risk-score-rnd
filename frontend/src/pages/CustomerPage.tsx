import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useResource } from '../api/live';
import { PageSkeleton } from '../components/Skeleton';
import { JournalList } from '../components/JournalList';
import { LevelBadge } from '../components/LevelBadge';
import { date, eur, pct, score, STATUS_LABEL, TERM_LABEL } from '../format';

export const CustomerPage: React.FC<{ id: number; onBack: () => void }> = ({ id, onBack }) => {
  const { data: c, error } = useResource(() => api.customer(id), [id]);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onBack(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onBack]);

  const copyEmail = async () => {
    if (!c) return;
    try {
      await navigator.clipboard.writeText(c.email);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  return (
    <div>
      <button className="back-btn" onClick={onBack} title="Esc">← К списку клиентов</button>
      {error && <p className="error">{error}</p>}
      {!c && !error && <PageSkeleton />}
      {c && (
        <>
          <div className="customer-head">
            <h2>{c.email}</h2>
            <span className="email-actions">
              <a href={`mailto:${c.email}`} title="Написать письмо">✉ написать</a>
              <button className="icon-btn" onClick={copyEmail} title="Скопировать email" aria-label="Скопировать email">{copied ? '✓' : '⧉'}</button>
            </span>
            <span className="muted">ID {c.accountId}</span>
            <LevelBadge level={c.level} />
          </div>

          <div className="tiles">
            <div className="tile tile-accent">
              <div className="tile-label">Risk score</div>
              <div className="tile-value">{score(c.score)}</div>
              <div className="tile-sub">
                {c.loyalty === null ? 'нет активных услуг — оценки нет' : `лояльность ${c.loyalty} из 100`}
              </div>
            </div>
            <div className="tile">
              <div className="tile-label">Можем потерять</div>
              <div className="tile-value">{eur(c.expectedLoss)}</div>
              <div className="tile-sub">
                из {eur(c.revenue)} выручки в горизонте
                {c.revenueFull > c.revenue && <> · по прайсу {eur(c.revenueFull)}, ограничено платёжеспособностью {eur(c.capacity)}</>}
              </div>
            </div>
            <div className="tile">
              <div className="tile-label">Доступно для списаний</div>
              <div className="tile-value">{eur(c.availableFunds)}</div>
              <div className="tile-sub">основной баланс {eur(c.balance)}</div>
            </div>
            <div className="tile">
              <div className="tile-label">Пополнено всего</div>
              <div className="tile-value">{eur(c.totalReplenished)}</div>
              <div className="tile-sub">способен заплатить за горизонт {eur(c.capacity)}</div>
            </div>
          </div>

          <section className={`card ${c.action ? 'action-card' : ''}`}>
            <h3>Что делать</h3>
            {c.action ? (
              <>
                <p><span className="action-badge">{c.action.title}</span></p>
                <p>{c.action.text}</p>
              </>
            ) : (
              <p className="muted">{c.score === null ? 'Нет активных услуг: клиент для возврата, а не удержания.' : 'Действий не требуется: признаков риска нет.'}</p>
            )}
          </section>

          <section className="card">
            <h3>Почему такая оценка</h3>
            {c.reasons.length === 0 ? (
              <p className="muted">{c.score === null ? 'У клиента нет активных услуг.' : 'Признаков риска не найдено.'}</p>
            ) : (
              <ul className="reasons">
                {c.reasons.map((r) => (
                  <li key={`${r.feature}-${r.serviceId}-${r.text}`}>
                    <div className="reason-head">
                      <b>{r.title}{r.kind === 'protective' && <span className="tag-protective">защитный</span>}</b>
                      <span className="muted">
                        {r.kind === 'protective'
                          ? `снижает риск на ${pct(r.impact)} = вес ${r.weight} × сила ${r.strength}`
                          : `вклад ${pct(r.impact)} = вес ${r.weight} × сила ${r.strength}`}
                      </span>
                    </div>
                    <div className={`reason-bar ${r.kind === 'protective' ? 'protective' : ''}`}><div style={{ width: pct(r.impact) }} /></div>
                    <div>{r.text}</div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card">
            <h3>Услуги</h3>
            <div className="table-responsive">
              <table className="clients-table">
                <thead>
                  <tr>
                    <th>Услуга</th>
                    <th>Статус</th>
                    <th className="num">Цена</th>
                    <th>Истекает</th>
                    <th>Автопродление</th>
                    <th className="num">Риск</th>
                    <th className="num">Можем потерять</th>
                  </tr>
                </thead>
                <tbody>
                  {c.services.map((s) => (
                    <tr key={s.serviceId}>
                      <td>{s.name}</td>
                      <td>{STATUS_LABEL[s.status]}</td>
                      <td className="num">{eur(s.price)} / {TERM_LABEL[s.paymentTerm]}</td>
                      <td>
                        {date(s.expiresAt)}
                        {s.nextChargeAt !== s.expiresAt && <div className="muted sub">списание {date(s.nextChargeAt)}</div>}
                      </td>
                      <td>{s.autoProlong ? 'вкл.' : 'выкл.'}</td>
                      <td className="num">{pct(s.risk)}</td>
                      <td className="num">
                        {eur(s.expectedLoss)}
                        <div className="muted sub">из {eur(s.revenue)}{s.revenueFull > s.revenue && <> · по прайсу {eur(s.revenueFull)}</>}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card">
            <h3>История изменений</h3>
            <JournalList events={c.history ?? []} empty="Изменений услуг этого клиента анализатор пока не наблюдал." />
          </section>
        </>
      )}
    </div>
  );
};
