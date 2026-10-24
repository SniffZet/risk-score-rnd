import { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ClientsTable } from './components/ClientsTable'; // Импортируем новый компонент таблицы
import './App.css';

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [login, setLogin] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [activeTab, setActiveTab] = useState<string>('home');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    if (tab) setActiveTab(tab);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set('tab', activeTab);
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', newUrl);
  }, [activeTab]);

  const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);
  const handleHomeClick = () => { setActiveTab('home'); setIsSidebarOpen(false); };
  const handleClientsClick = () => { setActiveTab('clients'); setIsSidebarOpen(false); };
  const handleLogout = () => { setIsAuthenticated(false); setIsSidebarOpen(false); setActiveTab('home'); };

  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsAuthenticated(true);
    setIsModalOpen(false);
    setLogin('');
    setPassword('');
  };

  return (
    <div className="app-container">
      <header className="main-header">
        <button className="menu-btn" onClick={toggleSidebar}>☰</button>
        <h1>АНАЛИЗАТОР РИСКОВ ОТТОКА</h1>
      </header>

      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        isAuthenticated={isAuthenticated}
        onLoginClick={() => { setIsSidebarOpen(false); setIsModalOpen(true); }}
        onHomeClick={handleHomeClick}
        onClientsClick={handleClientsClick}
        onLogoutClick={handleLogout}
      />

      {isSidebarOpen && <div className="overlay" onClick={() => setIsSidebarOpen(false)} />}

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
                <input type="text" value={login} onChange={(e) => setLogin(e.target.value)} required />
              </div>
              <div className="form-group">
                <label>Пароль:</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </div>
              <button type="submit" className="submit-btn">Войти</button>
            </form>
          </div>
        </div>
      )}

      <main className="main-content">
        {activeTab === 'home' && (
          <div>
            <h2>Главная страница</h2>
            <p>Добро пожаловать в Анализатор рисков оттока. Откройте вкладку "Клиенты" в меню для работы со списком.</p>
          </div>
        )}

        {/* Подключаем таблицу одной строкой */}
        {activeTab === 'clients' && <ClientsTable activeTab={activeTab} />}

        <p style={{ marginTop: '30px' }}>
          Статус: <b>{isAuthenticated ? "Вы авторизованы" : "Вы гость"}</b>
        </p>
      </main>
    </div>
  );
}

export default App;
