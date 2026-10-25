import { useEffect, useState } from 'react';
import { api, hasToken, setUnauthorizedHandler } from './api/client';
import { LiveContext, useLiveVersion } from './api/live';
import type { Summary, User } from './api/types';
import { time } from './format';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Sidebar } from './components/Sidebar/Sidebar';
import { CustomerPage } from './pages/CustomerPage';
import { CustomersPage } from './pages/CustomersPage';
import { LoginPage } from './pages/LoginPage';
import { OverviewPage } from './pages/OverviewPage';
import { SettingsPage } from './pages/SettingsPage';
import './App.css';

export type Tab = 'overview' | 'clients' | 'settings';

const TITLES: Record<Tab, string> = {
  overview: 'Обзор',
  clients: 'Клиенты',
  settings: 'Настройки модели',
};

interface Route {
  tab: Tab;
  customer: number | null;
}

function readRoute(): Route {
  const p = new URLSearchParams(window.location.search);
  const tab = p.get('tab') as Tab;
  const customer = Number(p.get('customer'));
  return { tab: tab in TITLES ? tab : 'overview', customer: customer > 0 ? customer : null };
}

function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [route, setRoute] = useState<Route>(readRoute);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  const [quick, setQuick] = useState('');
  const [navTick, setNavTick] = useState(0);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const live = useLiveVersion(!!user);

  useEffect(() => {
    if (!user) return;
    api.summary().then(setSummary).catch(() => {});
    if (live.version > 0) setUpdatedAt(new Date());
  }, [user, live.version]);

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    if (!hasToken()) setUser(null);
    else api.me().then(setUser).catch(() => setUser(null));
  }, []);

  useEffect(() => {
    const onPop = () => setRoute(readRoute());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = (next: Route) => {
    const p = new URLSearchParams({ tab: next.tab });
    if (next.customer) p.set('customer', String(next.customer));
    window.history.pushState({ inApp: true }, '', `${window.location.pathname}?${p}`);
    setRoute(next);
    setIsSidebarOpen(false);
  };

  const openCustomer = (id: number) => navigate({ tab: 'clients', customer: id });

  const openZone = (zone: string) => {
    const p = new URLSearchParams({ tab: 'clients', level: zone });
    window.history.pushState({ inApp: true }, '', `${window.location.pathname}?${p}`);
    setRoute({ tab: 'clients', customer: null });
    setNavTick((t) => t + 1);
    setIsSidebarOpen(false);
  };

  const quickSearch = () => {
    const value = quick.trim();
    if (!value) return;
    setQuick('');
    if (/^\d+$/.test(value)) {
      openCustomer(Number(value));
      return;
    }
    const p = new URLSearchParams({ tab: 'clients', search: value });
    window.history.pushState({ inApp: true }, '', `${window.location.pathname}?${p}`);
    setRoute({ tab: 'clients', customer: null });
    setNavTick((t) => t + 1);
    setIsSidebarOpen(false);
  };

  const handleLogout = async () => {
    await api.logout().catch(() => {});
    setUser(null);
    setIsSidebarOpen(false);
  };

  if (user === undefined) return null;
  if (user === null) return <LoginPage onLogin={setUser} />;

  return (
    <LiveContext.Provider value={live}>
      <div className="app-container">
        <header className="main-header">
          <button className="menu-btn" onClick={() => setIsSidebarOpen(!isSidebarOpen)} aria-label="Меню">☰</button>
          <h1>Анализатор рисков оттока</h1>
          <span className="header-sep" aria-hidden="true">/</span>
          <span className="header-tab">{TITLES[route.tab]}</span>
          <form className="quick-search" role="search" onSubmit={(e) => { e.preventDefault(); quickSearch(); }}>
            <input
              type="search"
              value={quick}
              onChange={(e) => setQuick(e.target.value)}
              placeholder="ID или email клиента"
              aria-label="Быстрый переход к клиенту"
            />
          </form>
          <span
            className={`live-status ${live.connected ? 'on' : 'off'}`}
            data-live={live.connected ? 'on' : 'off'}
            title={live.connected ? 'Данные обновляются автоматически' : 'Переподключение…'}
          >
            <span className="live-dot" aria-hidden="true" />
            <span className="live-text">
              {live.connected ? (updatedAt ? `Онлайн · обновлено ${time(updatedAt)}` : 'Онлайн') : 'Переподключение…'}
            </span>
          </span>
        </header>

        <Sidebar
          isOpen={isSidebarOpen}
          activeTab={route.tab}
          username={user.username}
          badges={{ clients: summary?.customersByLevel.high }}
          onClose={() => setIsSidebarOpen(false)}
          onNavigate={(tab) => navigate({ tab, customer: null })}
          onLogoutClick={handleLogout}
        />

        {isSidebarOpen && <div className="overlay" onClick={() => setIsSidebarOpen(false)} />}

        <main className="main-content">
          <ErrorBoundary key={`${route.tab}-${route.customer ?? ''}-${navTick}`} title="Страница не отобразилась">
            {route.tab === 'overview' && (
              <OverviewPage onOpenCustomer={openCustomer} onShowAll={() => openZone('risk')} />
            )}
            {route.tab === 'clients' && route.customer !== null && (
              <CustomerPage
                id={route.customer}
                onBack={() => window.history.state?.inApp ? window.history.back() : navigate({ tab: 'clients', customer: null })}
              />
            )}
            {route.tab === 'clients' && route.customer === null && <CustomersPage onOpenCustomer={openCustomer} />}
            {route.tab === 'settings' && <SettingsPage />}
          </ErrorBoundary>
        </main>
      </div>
    </LiveContext.Provider>
  );
}

export default App;
