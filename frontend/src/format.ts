import type { Level, PaymentTerm, ServiceStatus, Transition } from './api/types';

const euro = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'EUR' });

const euro0 = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0 });

export const eur = (cents: number) => euro.format(cents / 100);

export const eur0 = (cents: number) => euro0.format(cents / 100);

export const time = (d: Date) => d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

export const score = (s: number | null) => (s === null ? '—' : s.toFixed(1));

export const pct = (x: number) => `${Math.round(x * 100)}%`;

export const date = (iso: string) =>
  new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

export const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' });

export const LEVELS: Level[] = ['high', 'medium', 'low', 'no_data'];

export const LEVEL_LABEL: Record<Level, string> = {
  high: 'Высокий',
  medium: 'Средний',
  low: 'Низкий',
  no_data: 'Нет оценки',
};

export const STATUS_LABEL: Record<ServiceStatus, string> = {
  active: 'Активна',
  suspended: 'Выключена',
  prolong_wait: 'Ожидает оплаты',
  deleted: 'Удалена',
  blocked: 'Заблокирована',
};

export const TERM_LABEL: Record<PaymentTerm, string> = {
  hour: 'час',
  week: 'неделя',
  month: 'месяц',
  quarter_year: 'квартал',
  half_year: 'полгода',
  year: 'год',
};

export const TERM_LABEL_LONG: Record<PaymentTerm, string> = {
  hour: 'Почасовые',
  week: 'Понедельные',
  month: 'Помесячные',
  quarter_year: 'Поквартальные',
  half_year: 'Полугодовые',
  year: 'Годовые',
};

export const transitionText = (e: Transition) => {
  if (e.field === 'autoProlong') {
    return `автопродление: ${e.old === 'on' ? 'вкл.' : 'выкл.'} → ${e.new === 'on' ? 'вкл.' : 'выкл.'}`;
  }
  const label = (v: string | null) => (v && v in STATUS_LABEL ? STATUS_LABEL[v as ServiceStatus] : v ?? '—');
  return `статус: ${label(e.old)} → ${label(e.new)}`;
};
