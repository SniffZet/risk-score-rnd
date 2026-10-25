import React from 'react';

interface Props {
  children: React.ReactNode;
  title?: string;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error('Ошибка рендера:', error);
  }

  render() {
    if (this.state.error) {
      return (
        <section className="card error-card">
          <h3>{this.props.title ?? 'Не удалось показать блок'}</h3>
          <p className="error">{this.state.error.message}</p>
          <p className="muted">
            Чаще всего так бывает, когда панель новее бэкенда: перезапустите бэкенд и обновите страницу.
          </p>
          <button className="btn" onClick={() => this.setState({ error: null })}>Попробовать снова</button>
        </section>
      );
    }
    return this.props.children;
  }
}
