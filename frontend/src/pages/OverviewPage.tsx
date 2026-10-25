import React, { useState } from 'react';
import { api } from '../api/client';
import { useResource } from '../api/live';
import { PageSkeleton } from '../components/Skeleton';
import type { Level, SortKey, SortOrder } from '../api/types';
import { ChurnChart } from '../components/ChurnChart';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { CustomersTable, nextSort } from '../components/CustomersTable';
import { FeatureImpactTable } from '../components/FeatureImpact';
import { JournalList } from '../components/JournalList';
import { LevelBar, SummaryTiles } from '../components/SummaryTiles';
import { TermBreakdown } from '../components/TermBreakdown';
import { date, eur } from '../format';

const TOP = 10;
const JOURNAL = 8;

interface OverviewPageProps {
  onOpenCustomer: (id: number) => void;
  onShowAll: () => void;
  onSelectLevel: (level: Level) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onOpenCustomer, onShowAll, onSelectLevel }) => {
  const [sort, setSort] = useState<SortKey>('score');
  const [order, setOrder] = useState<SortOrder>('desc');
  const summary = useResource(() => api.summary(), []);
  const top = useResource(() => api.customers({ level: 'high,medium', sort_by: sort, sort_order: order, limit: TOP, offset: 0 }), [sort, order]);
  const chart = useResource(() => api.churnChart(), []);
  const journal = useResource(() => api.journal({ limit: JOURNAL }), []);

  if (summary.error) return <p className="error">{summary.error}</p>;
  if (!summary.data) return <PageSkeleton />;
  const s = summary.data;

  return (
    <div>
      <h2>Обзор</h2>
      <p className="muted">Расчёт на {date(s.referenceTime)}, горизонт прогноза {s.horizonDays} дн.</p>

      <SummaryTiles summary={s} onSelectLevel={onSelectLevel} />

      <section className="card">
        <h3>Клиенты по уровню риска</h3>
        <LevelBar summary={s} onSelectLevel={onSelectLevel} />
      </section>

      <section className="card">
        <h3>Топ-{TOP} в зоне риска</h3>
        <p className="muted">
          Выберите, кому уделить внимание первым. При одинаковой оценке риска выше клиент с большими ожидаемыми потерями.
        </p>
        <div className="priority-controls" aria-label="Приоритет клиентов">
          <span className="muted">В первую очередь:</span>
          <button className={`chip ${sort === 'score' && order === 'desc' ? 'active' : ''}`} aria-pressed={sort === 'score' && order === 'desc'} onClick={() => { setSort('score'); setOrder('desc'); }}>Высокий риск</button>
          <button className={`chip ${sort === 'expectedLoss' && order === 'desc' ? 'active' : ''}`} aria-pressed={sort === 'expectedLoss' && order === 'desc'} onClick={() => { setSort('expectedLoss'); setOrder('desc'); }}>Большие потери</button>
        </div>
        {top.error && <p className="error">{top.error}</p>}
        {top.data && (
          <CustomersTable
            items={top.data.items}
            sort={sort}
            order={order}
            onSort={(key) => { const [k, o] = nextSort(sort, order, key); setSort(k); setOrder(o); }}
            onOpen={onOpenCustomer}
          />
        )}
        <button className="link-btn more-btn" onClick={onShowAll}>Вся зона риска →</button>
      </section>

      <section className="card">
        <h3>Отток услуг: факт и прогноз</h3>
        {chart.error && <p className="error">{chart.error}</p>}
        {chart.data && <ErrorBoundary title="График не отобразился"><ChurnChart chart={chart.data} /></ErrorBoundary>}
      </section>

      <section className="card">
        <h3>Что создаёт риск</h3>
        <p className="muted">
          Сколько клиентов задел каждый признак и какую долю ожидаемых потерь он объясняет. Потери
          услуги делятся между её признаками пропорционально вкладу, поэтому сумма по строкам равна общей оценке.
        </p>
        <ErrorBoundary title="Таблица признаков не отобразилась">
          <FeatureImpactTable features={s.features ?? []} total={s.expectedLossTotal} customers={s.customersTotal} />
        </ErrorBoundary>
      </section>

      <section className="card">
        <h3>Как рассчитаны потери</h3>
        <p>Оценка за {s.horizonDays} дн. учитывает стоимость услуг, доступные средства клиента и риск непродления.</p>
        <details className="explanation"><summary>Методика и разбивка по периодам оплаты</summary>
        <p>
          Для каждой живой услуги клиента считаем выручку, которую она принесёт за {s.horizonDays} дн.
          (цена, приведённая к горизонту), и умножаем на вероятность, что услугу не продлят.
          Вероятность складывается из сработавших признаков: статус «ожидает оплаты», нехватка
          баланса на ближайшие продления, выключенное автопродление у истекающей услуги и т.д.
          Баланс учитывается дважды. Во-первых, деньги со счёта по порядку списываются на ближайшие
          продления, и то, на что их не хватит, поднимает риск. Во-вторых, выручка клиента за горизонт
          ограничена его платёжеспособностью: доступные средства плюс средний темп пополнений за всё
          время. Больше этого бизнес не получил бы и без оттока. Сумма по всем клиентам —{' '}
          <b>{eur(s.expectedLossTotal)}</b> из {eur(s.revenueTotal)} платёжеспособной выручки
          {s.revenueFullTotal > s.revenueTotal && <> (по прайсу было бы {eur(s.revenueFullTotal)})</>}.
        </p>
        <ErrorBoundary title="Разбивка по периодам не отобразилась"><TermBreakdown summary={s} /></ErrorBoundary>
        </details>
      </section>

      <section className="card">
        <h3>Последние изменения в данных</h3>
        <p className="muted">
          История статусов, которой нет в исходных данных: анализатор сравнивает каждый новый снимок с предыдущим.
        </p>
        {journal.error && <p className="error">{journal.error}</p>}
        {journal.data && (
          <JournalList
            events={Array.isArray(journal.data) ? journal.data : []}
            onOpenCustomer={onOpenCustomer}
            empty="Пока виден только один снимок. Догрузите изменения на странице настроек или через PATCH /api/v1/source/snapshot."
          />
        )}
      </section>
    </div>
  );
};
