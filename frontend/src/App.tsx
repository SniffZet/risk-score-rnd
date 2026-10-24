import { useState } from 'react';
import { Sidebar } from './components/Sidebar/Sidebar';
import './App.css';

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [login, setLogin] = useState<string>('');
  const [password, setPassword] = useState<string>('');

  // 1. Добавляем стейт для отслеживания текущего экрана ('home', 'profile', 'settings')
  const [activeTab, setActiveTab] = useState<string>('home');

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  // 2. Теперь эта функция не просто закрывает меню, а возвращает на главный экран
  const handleHomeClick = () => {
    setActiveTab('home');    // Переключаем экран на главный
    setIsSidebarOpen(false); // Закрываем сайдбар
    setIsModalOpen(false);   // Закрываем модалку, если была открыта
  };

  const handleLoginSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setIsAuthenticated(true);
    setIsModalOpen(false);
    setLogin('');
    setPassword('');
  };

  const handleLogout = () => {
      setIsAuthenticated(false);
      setIsModalOpen(false);
      setActiveTab('home')
  }

  const handleProfil = () => {
      setActiveTab('profil')
  }
  return (
    <div className="app-container">
      <header className="main-header">
        <button className="menu-btn" onClick={toggleSidebar}>
          ☰
        </button>
        <h1>АНАЛИЗАТОР РИСКОВ ОТТОКА</h1>
      </header>

      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        isAuthenticated={isAuthenticated}
        onLoginClick={() => {
          setIsSidebarOpen(false);
          setIsModalOpen(true);
        }}
        onHomeClick={handleHomeClick}
        onLogoutClick={handleLogout}
        onProfilClick={}
      />

      {isSidebarOpen && (
        <div className="overlay" onClick={() => setIsSidebarOpen(false)} />
      )}

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

      {/* 3. Меняем контент в зависимости от activeTab */}
      <main className="main-content">
        {activeTab === 'home' && (
          <div>
            <h2>Главная страница</h2>
            <p>Добро пожаловать в Анализатор рисков оттока. Здесь отображается основной контент...</p>
          </div>
        )}

        {activeTab === 'profile' && (
          <div>
            <h2>Личный профиль</h2>
            <p>Информация о пользователе и его статистика рисков.</p>
          </div>
        )}

        {/*<p style={{ marginTop: '20px' }}>*/}
        {/*  Статус: <b>{isAuthenticated ? "Вы авторизованы" : "Вы гость"}</b>*/}
        {/*</p>*/}
      </main>
    </div>
  );
}

export default App;
