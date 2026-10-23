import streamlit as st
import pandas as pd
import plotly.express as px

# Настраиваем страницу: делаем её широкой и задаем название во вкладке браузера
st.set_page_config(page_title="Анализатор рисков оттока", layout="wide", initial_sidebar_state="expanded")

# --- СТИЛИЗАЦИЯ ИНТЕРФЕЙСА ---
st.markdown("""
    <style>
    .main-title { font-size:32px !important; font-weight: 700; color: #1E293B; margin-bottom: 20px; }
    .card-loss { background-color: #FEE2E2; padding: 20px; border-radius: 10px; border-left: 5px solid #EF4444; }
    .card-metric { background-color: #F8FAFC; padding: 20px; border-radius: 10px; border: 1px solid #E2E8F0; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Панель маркетолога: Анализатор рисков оттока клиентов")
st.caption("Хакатон РНД · Уровень Middle")

# --- ФЕЙКОВЫЕ ДАННЫЕ ДЛЯ ДЕМОНСТРАЦИИ (Вместо базы данных) ---
# Данные сразу переведены из еврокопеек в нормальные Евро (€)
mock_customers = [
    {"id": "cust_101", "email": "ivanov@mail.ru", "balance_eur": 12.50, "total_replenished_eur": 450.00, "risk_score": 85.0, "risk_level": "Высокий 🔴", "potential_loss_eur": 45.00, "risk_reason": "Статус prolong_wait | На балансе 0"},
    {"id": "cust_102", "email": "petrov@yandex.ru", "balance_eur": 1.10, "total_replenished_eur": 1200.00, "risk_score": 72.0, "risk_level": "Высокий 🔴", "potential_loss_eur": 89.90, "risk_reason": "Недостаточно средств для автопродления VPS"},
    {"id": "cust_103", "email": "smirnov@gmail.com", "balance_eur": 55.00, "total_replenished_eur": 80.00, "risk_score": 45.0, "risk_level": "Средний 🟡", "potential_loss_eur": 15.00, "risk_reason": "Отключено автопродление услуги Backup"},
    {"id": "cust_104", "email": "kuznetsov@tech.co", "balance_eur": 0.00, "total_replenished_eur": 3400.00, "risk_score": 92.0, "risk_level": "Высокий 🔴", "potential_loss_eur": 250.00, "risk_reason": "Срок услуги истекает сегодня | Баланс пуст"},
    {"id": "cust_105", "email": "sidorov@vse-servery.ru", "balance_eur": 150.00, "total_replenished_eur": 5000.00, "risk_score": 12.0, "risk_level": "Низкий 🟢", "potential_loss_eur": 0.00, "risk_reason": "Риски не обнаружены. Клиент стабилен."},
]

# Превращаем список в удобную таблицу Pandas
df = pd.DataFrame(mock_customers)

# --- БОКОВАЯ ПАНЕЛЬ (SIDEBAR): НАСТРОЙКИ МОДЕЛИ ---
st.sidebar.image("https://icons8.com", width=60)
st.sidebar.header("⚙️ Коэффициенты модели")
st.sidebar.markdown("Передвигайте ползунки, чтобы изменить вес факторов риска в формуле **Risk Score**:")

# Ползунки (Слайдеры)
w_wait = st.sidebar.slider("Статус ожидания оплаты (prolong_wait)", 0, 100, 80)
w_money = st.sidebar.slider("Нехватка средств на балансе", 0, 100, 40)
w_auto = st.sidebar.slider("Отключено автопродление", 0, 100, 20)

# Кнопка применения
if st.sidebar.button("🔄 Пересчитать риски на лету", use_container_width=True):
    st.sidebar.success("Коэффициенты применены! Данные обновлены без перезагрузки страницы.")
    # Тут в будущем будет отправка данных на бэкенд, а пока просто симулируем обновление
    st.toast("Данные успешно пересчитаны!")

# --- БЛОК 1: ГЛАВНЫЕ МЕТРИКИ (КАРТОЧКИ) ---
st.markdown("### 📈 Сводные показатели рисков")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown('<div class="card-loss"><b>Потенциальные потери бизнеса</b><br><span style="font-size: 24px; font-weight:bold; color:#DC2626;">€ 384.90</span></div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="card-metric"><b>Клиенты в критической зоне 🔴</b><br><span style="font-size: 24px; font-weight:bold; color:#EF4444;">3 пользователя</span></div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="card-metric"><b>Средний уровень риска 🟡</b><br><span style="font-size: 24px; font-weight:bold; color:#F59E0B;">1 пользователь</span></div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="card-metric"><b>Лояльные клиенты 🟢</b><br><span style="font-size: 24px; font-weight:bold; color:#10B981;">1 пользователь</span></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- БЛОК 2: АНАЛИТИЧЕСКИЕ ГРАФИКИ ---
col_chart1, col_chart2 = st.columns([1, 1])

with col_chart1:
    st.markdown("##### Распределение клиентов по уровням риска")
    df_chart = pd.DataFrame({
        "Уровень": ["Высокий", "Средний", "Низкий"],
        "Количество": [3, 1, 1]
    })
    fig_bar = px.bar(df_chart, x="Уровень", y="Количество", color="Уровень",
                     color_discrete_map={"Высокий": "#EF4444", "Средний": "#F59E0B", "Низкий": "#10B981"})
    fig_bar.update_layout(showlegend=False, height=300, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_bar, use_container_width=True)

with col_chart2:
    st.markdown("##### Топ-3 потенциальных убытка (€)")
    # Берем только тех, у кого есть потери
    df_loss = df[df["potential_loss_eur"] > 0].sort_values(by="potential_loss_eur", ascending=False).head(3)
    fig_pie = px.pie(df_loss, values="potential_loss_eur", names="email", hole=0.4,
                     color_discrete_sequence=px.colors.sequential.Reds_r)
    fig_pie.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_pie, use_container_width=True)

# --- БЛОК 3: ТАБЛИЦА С СОРТИРОВКОЙ ДЛЯ МАРКЕТОЛОГА ---
st.markdown("### 🔝 Рейтинг клиентов под угрозой оттока")

# Инструменты управления таблицей (Сортировка по требованиям ТЗ)
col_sort1, col_sort2, _ = st.columns([2, 2, 4])
with col_sort1:
    sort_column = st.selectbox("Сортировать по столбцу:",
                               ["risk_score", "balance_eur", "total_replenished_eur", "id"],
                               format_func=lambda x: {
                                   "risk_score": "Risk Score (Уровень риска)",
                                   "balance_eur": "Текущий баланс",
                                   "total_replenished_eur": "Общая сумма пополнений",
                                   "id": "Идентификатор (ID)"
                               }[x])
with col_sort2:
    sort_order = st.radio("Порядок сортировки:", ["По убыванию 🔽", "По возрастанию 🔼"], horizontal=True)

# Применяем сортировку к нашей таблице
is_ascending = sort_order == "По возрастанию 🔼"
df_sorted = df.sort_values(by=sort_column, ascending=is_ascending)

# Переименовываем столбцы для красивого отображения в интерфейсе
df_display = df_sorted.rename(columns={
    "id": "ID Клиента",
    "email": "Email",
    "balance_eur": "Баланс (€)",
    "total_replenished_eur": "Всего пополнено (€)",
    "risk_score": "Risk Score",
    "risk_level": "Уровень риска",
    "potential_loss_eur": "Возможная потеря (€)",
    "risk_reason": "Причина риска (Обоснование)"
})

# Выводим интерактивную таблицу на экран
st.dataframe(df_display, use_container_width=True, hide_index=True)
