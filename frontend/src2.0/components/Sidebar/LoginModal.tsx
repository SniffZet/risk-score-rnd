import React, { useState } from 'react';
import './LoginModal.css'; // Добавьте стили по вкусу

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSubmit: () => void; // Функция, которая сработает при успешном входе
}

export const LoginModal: React.FC<LoginModalProps> = ({ isOpen, onClose, onLoginSubmit }) => {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');

  if (!isOpen) return null; // Если модалка закрыта, ничего не рендерим

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Здесь обычно отправляют запрос на сервер
    console.log('Отправка данных:', { login, password });

    // Имитируем успешный вход
    onLoginSubmit();
    onClose(); // Закрываем окно после входа
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Авторизация</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
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
  );
};
