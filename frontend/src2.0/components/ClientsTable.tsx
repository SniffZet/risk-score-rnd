import React, { useState, useEffect } from 'react';

interface Client {
  id: number;
  email: string;
  balance: number;
  deposits: number;
  score: number | null;
  level: 'high' | 'medium' | 'low' | 'none';
  reason: string;
  expectedLoss: number;
}

const MOCK_CLIENTS: Client[] = [
  { id: 1, email: 'ivan@mail.com', balance: 1250.50, deposits: 5000, score: 85, level: 'high', reason: 'Частый вывод средств', expectedLoss: 450.00 },
  { id: 2, email: 'petr@gmail.com', balance: 4500.00, deposits: 12000, score: 42, level: 'medium', reason: 'Снижение активности', expectedLoss: 200.50 },
  { id: 3, email: 'anna@yandex.ru', balance: 120.00, deposits: 300, score: 12, level: 'low', reason: 'Нет отклонений', expectedLoss: 0.00 },
  { id: 4, email: 'alex@risk.io', balance: 8900.99, deposits: 25000, score: null, level: 'none', reason: 'Новый аккаунт', expectedLoss: 0.00 },
  { id: 5, email: 'sergey@bk.ru', balance: 0.00, deposits: 1500, score: 92, level: 'high', reason: 'Отрицательный баланс в архиве', expectedLoss: 1200.00 },
  { id: 6, email: 'elena@gmail.com', balance: 350.25, deposits: 900, score: 55, level: 'medium', reason: 'Редкие сессии', expectedLoss: 50.00 },
  { id: 7, email: 'dmitry@mail.ru', balance: 15400.00, deposits: 45000, score: 18, level: 'low', reason: 'Стабильный профиль', expectedLoss: 0.00 }
];

type SortKey = 'id' | 'email' | 'balance' | 'deposits' | 'score';
type SortOrder = 'asc' | 'desc';

interface ClientsTableProps {
  activeTab: string;
}

export const ClientsTable: React.FC<ClientsTableProps> = ({ activeTab }) => {
  const [searchEmail, setSearchEmail] = useState<string>('');
  const [riskFilter, setRiskFilter] = useState<string>('all');
  const [sortKey, setSortKey] = useState<SortKey>('id');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = 10;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const search = params.get('search');
    if (search) setSearchEmail(search);
    const filter = params.get('risk');
    if (filter) setRiskFilter(filter);
    const sKey = params.get('sortKey') as SortKey;
    if (sKey) setSortKey(sKey);
    const sOrder = params.get('sortOrder') as SortOrder;
    if (sOrder) setSortOrder(sOrder);
    const page = params.get('page');
    if (page) setCurrentPage(Number(page));
  }, []);

  useEffect(() => {
    if (activeTab !== 'clients') return;
    const params = new URLSearchParams(window.location.search);
    params.set('tab', activeTab);
    if (searchEmail) params.set('search', searchEmail);
    else params.delete('search');
    if (riskFilter !== 'all') params.set('risk', riskFilter);
    else params.delete('risk');
    params.set('sortKey', sortKey);
    params.set('sortOrder', sortOrder);
    if (currentPage > 1) params.set('page', String(currentPage));
    else params.delete('page');

    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, '', newUrl);
  }, [activeTab, searchEmail, riskFilter, sortKey, sortOrder, currentPage]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('asc');
    }
    setCurrentPage(1);
  };

  const renderSortIcon = (key: SortKey) => {
    if (sortKey !== key) return ' ↕';
    return sortOrder === 'asc' ? ' ↑' : ' ↓';
  };

  const formatEuro = (value: number) => {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })
      .format(value)
      .replace(',', '.');
  };

  const filteredClients = MOCK_CLIENTS.filter(client => {
    const matchesEmail = client.email.toLowerCase().includes(searchEmail.toLowerCase());
    const matchesRisk = riskFilter === 'all' ? true : client.level === riskFilter;
    return matchesEmail && matchesRisk;
  });

  const sortedClients = [...filteredClients].sort((a, b) => {
    let aVal = a[sortKey];
    let bVal = b[sortKey];
    if (aVal === null) return sortOrder === 'asc' ? 1 : -1;
    if (bVal === null) return sortOrder === 'asc' ? -1 : 1;
    if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
    return 0;
  });

  const totalPages = Math.ceil(sortedClients.length / itemsPerPage);
  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentClients = sortedClients.slice(indexOfFirstItem, indexOfLastItem);

  return (
    <div className="clients-section">
      <h2>База клиентов компании</h2>

      <div className="filters-container">
        <input
          type="text"
          placeholder="Поиск по email..."
          value={searchEmail}
          onChange={(e) => { setSearchEmail(e.target.value); setCurrentPage(1); }}
          className="search-input"
        />
        <select
          value={riskFilter}
          onChange={(e) => { setRiskFilter(e.target.value); setCurrentPage(1); }}
          className="filter-select"
        >
          <option value="all">Все уровни риска</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
          <option value="none">Нет оценки</option>
        </select>
      </div>

      <div className="table-responsive">
        <table className="clients-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('id')}>ID{renderSortIcon('id')}</th>
              <th onClick={() => handleSort('email')}>Email{renderSortIcon('email')}</th>
              <th onClick={() => handleSort('balance')}>Баланс{renderSortIcon('balance')}</th>
              <th onClick={() => handleSort('deposits')}>Сумма пополнений{renderSortIcon('deposits')}</th>
              <th onClick={() => handleSort('score')}>Score{renderSortIcon('score')}</th>
              <th>Уровень</th>
              <th>Главная причина</th>
              <th>Ожидаемые потери</th>
            </tr>
          </thead>
          <tbody>
            {currentClients.length > 0 ? (
              currentClients.map(client => (
                <tr key={client.id}>
                  <td>{client.id}</td>
                  <td>{client.email}</td>
                  <td>{formatEuro(client.balance)}</td>
                  <td>{formatEuro(client.deposits)}</td>
                  <td>{client.score !== null ? client.score : '—'}</td>
                  <td>
                    <span className={`badge badge-${client.level}`} title={client.level === 'none' ? "Нет активных услуг" : undefined}>
                      {client.level === 'none' ? 'нет оценки' : client.level}
                    </span>
                  </td>
                  <td>{client.reason}</td>
                  <td>{formatEuro(client.expectedLoss)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '20px' }}>Клиенты не найдены</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))} disabled={currentPage === 1}>Назад</button>
          <span>Страница {currentPage} из {totalPages}</span>
          <button onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))} disabled={currentPage === totalPages}>Вперед</button>
        </div>
      )}
    </div>
  );
};
