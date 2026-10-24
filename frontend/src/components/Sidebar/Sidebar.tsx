import React from 'react';
import './Sidebar.css';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  isAuthenticated: boolean;
  onLoginClick: () => void; // Добавляем функцию клика по кнопке "Войти"
  onHomeClick: () => void; // на главную
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  isAuthenticated,
  onLoginClick,
  onHomeClick
}) => {
  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <h3>Меню</h3>
        <button className="close-btn" onClick={onClose}>
          ✕
        </button>
      </div>

      <nav className="sidebar-menu">
        <ul>
          {/* Заменили ссылку на кнопку для перехвата клика */}
          {!isAuthenticated && (
            <li>
              <button className="menu-btn" onClick={onLoginClick}>
                Войти в аккаунт
              </button>
            </li>
          )}

          {/* Кнопка Выйти (в реальном приложении сюда тоже вешают onClick={onLogout}) */}
          {isAuthenticated && (
            <li><a href='#logout'>Выйти из аккаунта</a></li>
          )}

          <li>
              <button className="menu-btn" onClick={onHomeClick}>
                  На главную
              </button>
          </li>
          <li><a href="#profile">Профиль</a></li>
          <li><a href="#settings">Настройки приоритета</a></li>
        </ul>
      </nav>
    </aside>
  );
};
