export type Level = 'high' | 'medium' | 'low' | 'no_data';
export type ServiceStatus = 'active' | 'suspended' | 'prolong_wait' | 'deleted' | 'blocked';
export type PaymentTerm = 'hour' | 'week' | 'month' | 'quarter_year' | 'half_year' | 'year';

export interface Reason {
  feature: string;
  title: string;
  serviceId: number;
  strength: number;
  weight: number;
  impact: number;
  text: string;
  kind: 'risk' | 'protective';
}

export interface Action {
  code: string;
  title: string;
  text: string;
}

export interface ServiceRisk {
  serviceId: number;
  name: string;
  status: ServiceStatus;
  paymentTerm: PaymentTerm;
  price: number;
  expiresAt: string;
  autoProlong: boolean;
  risk: number;
  revenue: number;
  revenueFull: number;
  expectedLoss: number;
  nextChargeAt: string;
  reasons: Reason[];
}

export interface Transition {
  at: string;
  serviceId: number;
  ownerId: number;
  serviceName: string;
  field: 'status' | 'autoProlong';
  old: string | null;
  new: string;
}

export interface CustomerListItem {
  accountId: number;
  email: string;
  balance: number;
  totalReplenished: number;
  availableFunds: number;
  capacity: number;
  score: number | null;
  level: Level;
  loyalty: number | null;
  expectedLoss: number;
  revenue: number;
  revenueFull: number;
  action: Action | null;
  reasons: Reason[];
}

export interface CustomerDetail extends CustomerListItem {
  services: ServiceRisk[];
  history: Transition[];
}

export interface CustomerList {
  items: CustomerListItem[];
  total: number;
  limit: number;
  offset: number;
}

export type SortKey = 'accountId' | 'email' | 'balance' | 'totalReplenished' | 'score' | 'expectedLoss' | 'revenue' | 'loyalty';
export type SortOrder = 'asc' | 'desc';

export type LevelFilter = Level | string;

export interface CustomersQuery {
  search?: string;
  level?: LevelFilter;
  sort_by: SortKey;
  sort_order: SortOrder;
  limit: number;
  offset: number;
}

export interface ExportQuery {
  search?: string;
  level?: LevelFilter;
  sort_by?: SortKey;
  sort_order?: SortOrder;
}

export interface FeatureImpact {
  feature: string;
  title: string;
  weight: number;
  customers: number;
  services: number;
  expectedLoss: number;
  kind: 'risk' | 'protective';
}

export interface Summary {
  referenceTime: string;
  horizonDays: number;
  customersTotal: number;
  customersByLevel: Record<Level, number>;
  expectedLossTotal: number;
  expectedLossByLevel: Record<Level, number>;
  revenueTotal: number;
  revenueFullTotal: number;
  servicesAtRisk: number;
  revenueByTerm: Record<PaymentTerm, number>;
  expectedLossByTerm: Record<PaymentTerm, number>;
  features: FeatureImpact[];
}

export interface ChurnPoint {
  date: string;
  deleted: number;
  deletedObserved: number;
  expectedNonrenewals: number;
  servicesAtRisk: number;
}

export interface ChurnChart {
  bucket: 'day' | 'week';
  referenceDate: string;
  horizonDays: number;
  points: ChurnPoint[];
}

export interface FeatureMeta {
  code: string;
  title: string;
  description: string;
  default_weight: number;
  min_weight: number;
  max_weight: number;
  kind: 'risk' | 'protective';
}

export interface Settings {
  weights: Record<string, number>;
  highThreshold: number;
  mediumThreshold: number;
  horizonDays: number;
  expiringWindowDays: number;
  prolongWaitGraceDays: number;
  paymentLookbackDays: number;
  countWithdrawBalance: boolean;
  capRevenueByCapacity: boolean;
  bigSpenderThreshold: number;
  newCustomerDays: number;
  loyalTenureDays: number;
  referenceTime: string | null;
}

export interface ModelSettings extends Settings {
  features: FeatureMeta[];
}

export type SettingsPatch = Partial<Omit<Settings, 'weights'>> & { weights?: Record<string, number> };

export interface SettingsPreview {
  settings: ModelSettings;
  summary: Summary;
}

export interface SnapshotResult {
  status: string;
  counts: Record<'accounts' | 'services' | 'transactions', number>;
  applied: Record<'accounts' | 'services' | 'transactions', number>;
  transitions: number;
  summary: Summary | null;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface User {
  id: number;
  username: string;
}

export interface Providers {
  password: boolean;
  oidc: boolean;
  oidcName: string | null;
  oidcLoginUrl: string | null;
}
