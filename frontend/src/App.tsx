import { useState } from 'react';
import { Sidebar } from './components/Sidebar/Sidebar';
import './App.css';

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);

  // Новые стейты для авторизации и модального окна
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  // Стейты для полей ввода формы
  const [login, setLogin] = useState<string>('');
  const [password, setPassword] = useState<string>('');

  const handleHomeClick = () => {
      setIsSidebarOpen(false);
      setIsModalOpen(false)
  };
  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  // Обработчик отправки формы авторизации
  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Имитируем успешный вход
    setIsAuthenticated(true);
    setIsModalOpen(false); // Закрываем окно авторизации

    // Очищаем поля формы
    setLogin('');
    setPassword('');
  };

  return (
    <div className="app-container">
      {/* Кнопка для открытия сайдбара */}
      <header className="main-header">
        <button className="menu-btn" onClick={toggleSidebar}>
          ☰
        </button>
        <h1>АНАЛИЗАТОР РИСКОВ ОТТОКА</h1>
      </header>

      {/* Компонент боковой панели с переданными пропсами авторизации */}
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        isAuthenticated={isAuthenticated}
        onLoginClick={() => {
          setIsSidebarOpen(false); // Закрываем сайдбар
          setIsModalOpen(true);    // Открываем модальное окно входа
        }}
        onHomeClick={handleHomeClick}
      />

      {/* Затемняющий слой заднего фона для Сайдбара */}
      {isSidebarOpen && (
        <div className="overlay" onClick={() => setIsSidebarOpen(false)} />
      )}

      {/* --- МОДАЛЬНОЕ ОКНО АВТОРИЗАЦИИ (Встроенное) --- */}
      {isModalOpen && (
        <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Авторизация</h2>
              <button className="modal-close-btn" onClick={() => setIsModalOpen(false)}>✕</button>
            </div>

            <form onSubmit={handleLoginSubmit} className="login-form">
              <div className="form-group">
                <label>Логин или Email:</label>
                <input
                  type="text"
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label>Пароль:</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <button type="submit" className="submit-btn">Войти</button>
            </form>
          </div>
        </div>
      )}

      <main className="main-content">
        <p>Основной контент страницы...</p>
        <p>Статус: <b>{isAuthenticated ? "Вы авторизованы" : "Вы гость"}</b></p>
      </main>
    </div>
  );
}

export default App;
