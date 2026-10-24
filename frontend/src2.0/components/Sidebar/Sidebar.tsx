import React from 'react';
import './Sidebar.css';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  isAuthenticated: boolean;
  onLoginClick: () => void;
  onHomeClick: () => void;
  onLogoutClick: () => void;
  onClientsClick: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  isAuthenticated,
  onLoginClick,
  onHomeClick,
  onLogoutClick,
    onClientsClick
}) => {
  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <h3>Меню</h3>
        <button className="close-btn" onClick={onClose}>✕</button>
      </div>

      <nav className="sidebar-menu">
        <ul>
          {!isAuthenticated && (
            <li>
              <button className="menu-btn" onClick={onLoginClick}>
                Войти в аккаунт
              </button>
            </li>
          )}

          {isAuthenticated && (
            <li>
              <button className="menu-btn" onClick={onLogoutClick}>
                Выйти из аккаунта
              </button>
            </li>
          )}

          <li>
            <button className="menu-btn" onClick={onHomeClick}>
              Главная
            </button>
          </li>
          <li>
            <button className="menu-btn" onClick={onClientsClick}>
              Клиенты
            </button>
          </li>

          <li><a href="#settings">Настройки приоритета</a></li>
        </ul>
      </nav>
    </aside>
  );
};
