import React from 'react';
import type { Tab } from '../../App';
import './Sidebar.css';

interface SidebarProps {
  isOpen: boolean;
  activeTab: Tab;
  username: string;
  badges?: Partial<Record<Tab, number | undefined>>;
  onClose: () => void;
  onNavigate: (tab: Tab) => void;
  onLogoutClick: () => void;
}

const icon = (d: string) => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={d} />
  </svg>
);

const ITEMS: { tab: Tab; label: string; icon: React.ReactNode }[] = [
  { tab: 'overview', label: 'Обзор', icon: icon('M3 10.5 10 4l7 6.5M5 9v7h4v-4h2v4h4V9') },
  { tab: 'clients', label: 'Клиенты', icon: icon('M7.5 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2 17c0-3 2.5-5 5.5-5s5.5 2 5.5 5M13 3.5a3 3 0 0 1 0 5.5M15 12c1.8.6 3 2.4 3 5') },
  { tab: 'settings', label: 'Настройки модели', icon: icon('M4 5h8M16 5h0M4 10h2M10 10h6M4 15h6M14 15h2M12 3v4M6 8v4M10 13v4') },
];

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  activeTab,
  username,
  badges,
  onClose,
  onNavigate,
  onLogoutClick,
}) => {
  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span>
            Risk Score
            <span className="brand-sub">анализатор оттока</span>
          </span>
        </div>
        <button className="close-btn" onClick={onClose} aria-label="Закрыть меню">✕</button>
      </div>

      <nav className="sidebar-menu">
        <ul>
          {ITEMS.map(({ tab, label, icon }) => (
            <li key={tab}>
              <button
                className={activeTab === tab ? 'active' : ''}
                aria-current={activeTab === tab ? 'page' : undefined}
                onClick={() => onNavigate(tab)}
              >
                {icon}
                {label}
                {badges?.[tab] ? (
                  <span className="nav-badge" title="Клиентов с высоким риском">{badges[tab]}</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="sidebar-footer">
        <span className="avatar" aria-hidden="true">{username.slice(0, 1)}</span>
        <span className="username" title={username}>{username}</span>
        <button onClick={onLogoutClick}>Выйти</button>
      </div>
    </aside>
  );
};
