import React, { useContext, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { LiveContext, useResource } from '../api/live';
import type { Settings, SettingsPatch, Summary } from '../api/types';
import { PageSkeleton } from '../components/Skeleton';
import { LevelBar, SummaryTiles } from '../components/SummaryTiles';
import { eur, LEVEL_LABEL, pct } from '../format';

const SAVE_DELAY_MS = 400;

type Mode = 'apply' | 'preview';

const merge = (a: SettingsPatch, b: SettingsPatch): SettingsPatch => ({ ...a, ...b, weights: { ...a.weights, ...b.weights } });
const hasChanges = (p: SettingsPatch) => Object.keys(p).some((k) => k !== 'weights') || Object.keys(p.weights ?? {}).length > 0;

export const SettingsPage: React.FC = () => {
  const { refresh } = useContext(LiveContext);
  const { data, error } = useResource(() => api.settings(), []);
  const summary = useResource(() => api.summary(), []);

  const [mode, setMode] = useState<Mode>('apply');
  const [draft, setDraft] = useState<Settings | null>(null);
  const [staged, setStaged] = useState<SettingsPatch>({});
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Summary | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const dirty = useRef(false);

  useEffect(() => {
    if (data && !dirty.current) setDraft(data);
  }, [data]);

  useEffect(() => {
    if (tick === 0 || !hasChanges(staged)) return;
    const t = window.setTimeout(async () => {
      setBusy(true);
      try {
        if (mode === 'apply') {
          const patch = staged;
          setStaged({});
          const res = await api.patchSettings(patch);
          setDraft(res);
          dirty.current = false;
          refresh();
        } else {
          const res = await api.previewSettings(staged);
          setPreview(res.summary);
        }
        setSaveError(null);
      } catch (e) {
        setSaveError((e as Error).message);
      } finally {
        setBusy(false);
      }
    }, SAVE_DELAY_MS);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  const change = (patch: SettingsPatch) => {
    dirty.current = true;
    setDraft((d) => d && ({ ...d, ...patch, weights: { ...d.weights, ...patch.weights } }));
    setStaged((s) => merge(s, patch));
    setTick((t) => t + 1);
  };

  const applyStaged = async () => {
    setBusy(true);
    try {
      const res = await api.patchSettings(staged);
      setStaged({});
      setPreview(null);
      setDraft(res);
      dirty.current = false;
      setSaveError(null);
      refresh();
    } catch (e) {
      setSaveError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const discardStaged = () => {
    setStaged({});
    setPreview(null);
    dirty.current = false;
    if (data) setDraft(data);
  };

  const switchMode = (next: Mode) => {
    if (next === mode) return;
    discardStaged();
    setMode(next);
  };

  const numberField = (key: 'highThreshold' | 'mediumThreshold' | 'horizonDays' | 'expiringWindowDays' | 'prolongWaitGraceDays' | 'paymentLookbackDays' | 'newCustomerDays' | 'loyalTenureDays',
                       label: string, hint: string, min: number, max?: number) => (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={draft?.[key] ?? ''}
        onChange={(e) => { if (e.target.value !== '') change({ [key]: Number(e.target.value) }); }}
      />
      <small className="muted">{hint}</small>
    </label>
  );

  const impactOf = (code: string) => summary.data?.features?.find((x) => x.feature === code);
  const lossTotal = summary.data?.expectedLossTotal ?? 0;

  if (error) return <p className="error">{error}</p>;
  if (!data || !draft) return <PageSkeleton tiles={false} />;

  return (
    <div>
      <h2>Настройки модели</h2>
      <p className="muted">
        Риск услуги = 1 − ∏(1 − вес × сила признака); score клиента — максимальный риск среди его услуг × 100.
      </p>

      <div className="mode-switch" role="radiogroup" aria-label="Режим изменений">
        <button className={mode === 'apply' ? 'active' : ''} onClick={() => switchMode('apply')} role="radio" aria-checked={mode === 'apply'}>
          Применять сразу
        </button>
        <button className={mode === 'preview' ? 'active' : ''} onClick={() => switchMode('preview')} role="radio" aria-checked={mode === 'preview'}>
          Что-если
        </button>
        <span className="muted">
          {mode === 'apply'
            ? 'Изменения сохраняются автоматически и сразу пересчитывают оценки во всей панели.'
            : 'Изменения считаются на копии, в модель попадут только по кнопке «Применить».'}
        </span>
      </div>

      {summary.data && <SummaryTiles summary={summary.data} />}
      {summary.data && <section className="card"><LevelBar summary={summary.data} /></section>}

      {mode === 'preview' && summary.data && (
        <section className="card preview-card">
          <div className="card-head">
            <h3>Что-если: сравнение с текущей моделью</h3>
            <span>
              <button className="btn" onClick={applyStaged} disabled={busy || !hasChanges(staged)}>Применить</button>{' '}
              <button className="link-btn" onClick={discardStaged} disabled={!hasChanges(staged)}>Отменить</button>
            </span>
          </div>
          {!preview && <p className="muted">Подвиньте вес или порог, и здесь появится сводка с новыми настройками.</p>}
          {preview && <PreviewDiff current={summary.data} next={preview} />}
        </section>
      )}

      {saveError && <p className="error">Не сохранено: {saveError}</p>}
      {busy && <p className="muted">{mode === 'apply' ? 'Сохранение…' : 'Считаем…'}</p>}

      <section className="card">
        <div className="card-head">
          <h3>Веса признаков</h3>
          <button
            className="link-btn"
            onClick={() => change({ weights: Object.fromEntries(data.features.map((f) => [f.code, f.default_weight])) })}
          >
            Сбросить к базовым
          </button>
        </div>
        <p className="muted">0 — признак выключен, 1 — один этот признак даёт максимальный риск.</p>
        {data.features.map((f) => {
          const w = draft.weights[f.code] ?? f.default_weight;
          return (
            <div key={f.code} className="weight-row">
              <div>
                <b>{f.title}</b>
                {f.kind === 'protective' && <span className="tag-protective">защитный: снижает риск</span>}
                <div className="muted">{f.description}</div>
                {impactOf(f.code) && summary.data && (
                  <div className="weight-impact">
                    сработал у {impactOf(f.code)!.customers} из {summary.data.customersTotal} клиентов
                    {lossTotal > 0 && f.kind !== 'protective' && <> · объясняет {pct(impactOf(f.code)!.expectedLoss / lossTotal)} потерь</>}
                  </div>
                )}
              </div>
              <input
                type="range"
                min={f.min_weight}
                max={f.max_weight}
                step={0.05}
                value={w}
                aria-label={f.title}
                onChange={(e) => change({ weights: { [f.code]: Number(e.target.value) } })}
              />
              <span className="weight-value">{w.toFixed(2)}</span>
            </div>
          );
        })}
      </section>

      <section className="card">
        <h3>Пороги, горизонт и деньги</h3>
        <div className="fields">
          {numberField('highThreshold', 'Порог «высокий»', 'score от этого значения — высокий риск', 0, 100)}
          {numberField('mediumThreshold', 'Порог «средний»', 'не выше порога «высокий»', 0, 100)}
          {numberField('horizonDays', 'Горизонт прогноза, дн.', 'за какой срок считаем продления и потери', 1)}
          {numberField('expiringWindowDays', 'Окно «скоро истекает», дн.', 'для услуг без автопродления', 1)}
          {numberField('prolongWaitGraceDays', 'Ожидание оплаты, дн.', 'через сколько prolong_wait станет deleted', 0)}
          {numberField('paymentLookbackDays', 'Давность неоплат, дн.', 'неоплаченные продления старше не учитываются', 1)}
          {numberField('newCustomerDays', 'Новый клиент, дн.', 'первый период после прихода, когда отток самый высокий', 1)}
          {numberField('loyalTenureDays', 'Давний клиент, дн.', 'возраст активной услуги, с которого срабатывает защитный признак', 1)}
          <label className="field">
            <span>Крупный клиент от, €</span>
            <input
              type="number"
              min={0}
              value={Math.round(draft.bigSpenderThreshold / 100)}
              onChange={(e) => { if (e.target.value !== '') change({ bigSpenderThreshold: Math.round(Number(e.target.value) * 100) }); }}
            />
            <small className="muted">сумма пополнений за всё время, с которой клиент считается крупным</small>
          </label>
          <label className="field">
            <span>Момент расчёта</span>
            <select
              value={draft.referenceTime === 'now' ? 'now' : ''}
              onChange={(e) => change({ referenceTime: e.target.value || null })}
            >
              <option value="">последнее событие в данных</option>
              <option value="now">текущее время</option>
            </select>
            <small className="muted">тестовые данные заморожены во времени</small>
          </label>
          <label className="field checkbox">
            <input
              type="checkbox"
              checked={draft.capRevenueByCapacity}
              onChange={(e) => change({ capRevenueByCapacity: e.target.checked })}
            />
            <span>Ограничивать выручку платёжеспособностью клиента</span>
          </label>
          <label className="field checkbox">
            <input
              type="checkbox"
              checked={draft.countWithdrawBalance}
              onChange={(e) => change({ countWithdrawBalance: e.target.checked })}
            />
            <span>Считать реферальный баланс доступным для продлений</span>
          </label>
        </div>
      </section>

      <SnapshotUpload onUploaded={refresh} />
    </div>
  );
};

const PreviewDiff: React.FC<{ current: Summary; next: Summary }> = ({ current, next }) => {
  const delta = (a: number, b: number, money = false) => {
    const d = b - a;
    if (d === 0) return <span className="muted">без изменений</span>;
    return <span className={d > 0 ? 'delta-up' : 'delta-down'}>{d > 0 ? '+' : '−'}{money ? eur(Math.abs(d)) : Math.abs(d)}</span>;
  };
  const rows: { label: string; a: number; b: number; money?: boolean }[] = [
    { label: 'Можем потерять', a: current.expectedLossTotal, b: next.expectedLossTotal, money: true },
    { label: `${LEVEL_LABEL.high} риск`, a: current.customersByLevel.high, b: next.customersByLevel.high },
    { label: `${LEVEL_LABEL.medium} риск`, a: current.customersByLevel.medium, b: next.customersByLevel.medium },
    { label: `${LEVEL_LABEL.low} риск`, a: current.customersByLevel.low, b: next.customersByLevel.low },
    { label: 'Услуг под риском', a: current.servicesAtRisk, b: next.servicesAtRisk },
  ];
  return (
    <div className="table-responsive">
      <table className="clients-table">
        <thead><tr><th>Показатель</th><th className="num">Сейчас</th><th className="num">Что-если</th><th className="num">Разница</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td>{r.label}</td>
              <td className="num">{r.money ? eur(r.a) : r.a}</td>
              <td className="num"><b>{r.money ? eur(r.b) : r.b}</b></td>
              <td className="num">{delta(r.a, r.b, r.money)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const SnapshotUpload: React.FC<{ onUploaded: () => void }> = ({ onUploaded }) => {
  const [mode, setMode] = useState<'replace' | 'upsert'>('replace');
  const [status, setStatus] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setStatus('Загрузка…');
    setFailed(false);
    try {
      const parsed = JSON.parse(await file.text());
      const res = mode === 'replace' ? await api.putSnapshot(parsed) : await api.patchSnapshot(parsed);
      const { counts, applied, transitions } = res;
      setStatus(
        mode === 'replace'
          ? `Загружен ${file.name}: ${counts.accounts} аккаунтов, ${counts.services} услуг, ${counts.transactions} транзакций — оценки пересчитаны, изменений услуг записано в журнал: ${transitions}`
          : `Догружено из ${file.name}: ${applied.accounts} аккаунтов, ${applied.services} услуг, ${applied.transactions} транзакций — всего в данных ${counts.services} услуг, изменений записано в журнал: ${transitions}`,
      );
      onUploaded();
    } catch (err) {
      setFailed(true);
      setStatus(`Не удалось загрузить: ${(err as Error).message}`);
    }
  };

  return (
    <section className="card">
      <h3>Исходные данные</h3>
      <p className="muted">JSON с массивами accounts, services, transactions — как data/data.json.</p>
      <div className="fields">
        <label className="field">
          <span>Режим</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as 'replace' | 'upsert')}>
            <option value="replace">Заменить данные полностью</option>
            <option value="upsert">Догрузить изменения (upsert по id)</option>
          </select>
          <small className="muted">
            {mode === 'replace'
              ? 'Текущий снимок заменяется целиком, изменения статусов попадают в журнал.'
              : 'Записи с известным id заменяются, новые добавляются, остальные не трогаются: так приходит поток в реальном времени.'}
          </small>
        </label>
        <label className="field">
          <span>Файл</span>
          <input type="file" accept="application/json,.json" onChange={handleFile} />
        </label>
      </div>
      {status && <p className={failed ? 'error' : 'muted'}>{status}</p>}
    </section>
  );
};
