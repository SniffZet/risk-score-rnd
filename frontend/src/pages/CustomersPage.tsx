import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useResource } from '../api/live';
import type { Level, SortKey, SortOrder } from '../api/types';
import { CustomersTable, nextSort } from '../components/CustomersTable';
import { PageSkeleton } from '../components/Skeleton';
import { LEVEL_LABEL } from '../format';

const PAGE_SIZE = 20;
const SORT_KEYS: SortKey[] = ['accountId', 'email', 'balance', 'totalReplenished', 'score', 'expectedLoss', 'revenue', 'loyalty'];

type Zone = '' | 'risk' | Level;
const ZONES: { value: Zone; label: string; hint: string }[] = [
  { value: '', label: 'Все', hint: 'все клиенты' },
  { value: 'risk', label: 'Зона риска', hint: 'высокий и средний уровень' },
  { value: 'high', label: LEVEL_LABEL.high, hint: 'score не ниже порога «высокий»' },
  { value: 'medium', label: LEVEL_LABEL.medium, hint: 'score между порогами' },
  { value: 'low', label: LEVEL_LABEL.low, hint: 'score ниже порога «средний»' },
  { value: 'no_data', label: LEVEL_LABEL.no_data, hint: 'нет живых услуг, оценивать нечего' },
];
const zoneToLevel = (z: Zone) => (z === 'risk' ? 'high,medium' : z || undefined);

function readParams() {
  const p = new URLSearchParams(window.location.search);
  const zone = p.get('level') ?? '';
  return {
    search: p.get('search') ?? '',
    zone: (ZONES.some((z) => z.value === zone) ? zone : '') as Zone,
    sort: (SORT_KEYS.includes(p.get('sort') as SortKey) ? p.get('sort') : 'score') as SortKey,
    order: (p.get('order') === 'asc' ? 'asc' : 'desc') as SortOrder,
    page: Number(p.get('page') ?? 1),
  };
}

export const CustomersPage: React.FC<{ onOpenCustomer: (id: number) => void }> = ({ onOpenCustomer }) => {
  const initial = readParams();
  const [searchInput, setSearchInput] = useState(initial.search);
  const [search, setSearch] = useState(initial.search);
  const [zone, setZone] = useState<Zone>(initial.zone);
  const [sort, setSort] = useState<SortKey>(initial.sort);
  const [order, setOrder] = useState<SortOrder>(initial.order);
  const [page, setPage] = useState(initial.page);
  const [exportError, setExportError] = useState<string | null>(null);
  const summary = useResource(() => api.summary(), []);

  useEffect(() => {
    const t = window.setTimeout(() => { setSearch(searchInput); setPage(1); }, 300);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const set = (k: string, v: string) => (v ? p.set(k, v) : p.delete(k));
    set('search', search);
    set('level', zone);
    set('sort', sort);
    set('order', order);
    set('page', page > 1 ? String(page) : '');
    window.history.replaceState(null, '', `${window.location.pathname}?${p}`);
  }, [search, zone, sort, order, page]);

  const { data, error } = useResource(
    () => api.customers({
      search: search || undefined,
      level: zoneToLevel(zone),
      sort_by: sort,
      sort_order: order,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [search, zone, sort, order, page],
  );

  const handleSort = (key: SortKey) => {
    const [s, o] = nextSort(sort, order, key);
    setSort(s);
    setOrder(o);
    setPage(1);
  };

  const pickZone = (next: Zone) => { setZone(next); setPage(1); };
  const resetFilters = () => { setSearchInput(''); setSearch(''); setZone(''); setSort('score'); setOrder('desc'); setPage(1); };
  const filtersActive = Boolean(search || zone || sort !== 'score' || order !== 'desc');

  const handleExport = async () => {
    setExportError(null);
    try {
      const blob = await api.exportCsv({ search: search || undefined, level: zoneToLevel(zone), sort_by: sort, sort_order: order });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `customers-${zone || 'all'}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setExportError((e as Error).message);
    }
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const counts = summary.data?.customersByLevel;
  const zoneCount = (z: Zone): number | null => {
    if (!counts || !summary.data) return null;
    if (z === '') return summary.data.customersTotal;
    if (z === 'risk') return counts.high + counts.medium;
    return counts[z];
  };

  return (
    <div className="clients-section">
      <h2>Кто в зоне риска</h2>
      <p className="muted">
        Зона риска — клиенты с высоким и средним уровнем. Самый высокий score сверху, при равном score выше тот,
        где больше ожидаемых потерь. Клик по заголовку — сортировка, повторный клик — в обратную сторону.
      </p>

      <div className="chips" role="radiogroup" aria-label="Сегмент">
        {ZONES.map((z) => (
          <button
            key={z.value || 'all'}
            className={`chip ${zone === z.value ? 'active' : ''} ${z.value ? `chip-${z.value}` : ''}`}
            role="radio"
            aria-checked={zone === z.value}
            title={z.hint}
            onClick={() => pickZone(z.value)}
          >
            {z.label}
            {zoneCount(z.value) !== null && <span className="chip-count">{zoneCount(z.value)}</span>}
          </button>
        ))}
      </div>

      <div className="filters-container">
        <input
          type="search"
          placeholder="Поиск по email…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="search-input"
          aria-label="Поиск по email"
        />
        <button className="btn" onClick={handleExport} title="Выгрузить текущий список целиком">Скачать CSV</button>
      </div>

      {error && <p className="error">{error}</p>}
      {exportError && <p className="error">Не удалось выгрузить: {exportError}</p>}

      {!data && !error && <PageSkeleton tiles={false} />}

      {data && (
        <>
          <p className="result-count muted">
            {data.total === 0 ? 'Ничего не найдено' : `Найдено ${data.total}`}
            {filtersActive && <> · <button className="link-btn inline" onClick={resetFilters}>сбросить фильтры</button></>}
          </p>
          <CustomersTable items={data.items} sort={sort} order={order} onSort={handleSort} onOpen={onOpenCustomer} />
          {data.total === 0 && filtersActive && (
            <p className="muted">Попробуйте другой сегмент или часть email без домена.</p>
          )}
        </>
      )}

      {totalPages > 1 && (
        <div className="pagination">
          <button onClick={() => setPage((p) => Math.max(p - 1, 1))} disabled={page === 1}>Назад</button>
          <span>Страница {page} из {totalPages} · всего {data?.total}</span>
          <button onClick={() => setPage((p) => Math.min(p + 1, totalPages))} disabled={page === totalPages}>Вперёд</button>
        </div>
      )}
    </div>
  );
};
