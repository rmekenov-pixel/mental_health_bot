import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
from datetime import datetime, timedelta
from database.db import AsyncSessionLocal
from database.models import TestResult, CheckIn
from sqlalchemy import select


async def generate_chart(telegram_id: int) -> io.BytesIO | None:
    async with AsyncSessionLocal() as session:
        week_ago = datetime.utcnow() - timedelta(days=7)

        test_result = await session.execute(
            select(TestResult)
            .where(TestResult.telegram_id == telegram_id)
            .where(TestResult.created_at >= week_ago)
            .order_by(TestResult.created_at)
        )
        tests = test_result.scalars().all()

        checkin_result = await session.execute(
            select(CheckIn)
            .where(CheckIn.telegram_id == telegram_id)
            .where(CheckIn.created_at >= week_ago)
            .order_by(CheckIn.created_at)
        )
        checkins = checkin_result.scalars().all()

    if not tests and not checkins:
        return None

    fig, axes = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle('Динамика за последние 7 дней', fontsize=14, fontweight='bold')

    if tests:
        dates = [t.created_at for t in tests]
        scores = [t.score for t in tests]
        names = [t.test_name for t in tests]

        axes[0].plot(dates, scores, 'o-', color='#5B86E5', linewidth=2, markersize=8)
        for i, (d, s, n) in enumerate(zip(dates, scores, names)):
            axes[0].annotate(f'{n}: {s}', (d, s), textcoords="offset points",
                           xytext=(0, 10), ha='center', fontsize=8)
        axes[0].set_title('Результаты тестов')
        axes[0].set_ylabel('Баллы')
        axes[0].grid(True, alpha=0.3)
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    else:
        axes[0].text(0.5, 0.5, 'Нет данных тестов за 7 дней',
                    ha='center', va='center', transform=axes[0].transAxes)
        axes[0].set_title('Результаты тестов')

    if checkins:
        dates = [c.created_at for c in checkins]
        moods = [c.mood for c in checkins]
        anxieties = [c.anxiety for c in checkins]
        energies = [c.energy for c in checkins]

        axes[1].plot(dates, moods, 'o-', color='#36D1DC', label='Настроение', linewidth=2)
        axes[1].plot(dates, anxieties, 's-', color='#FF6B6B', label='Тревога', linewidth=2)
        axes[1].plot(dates, energies, '^-', color='#FFA500', label='Энергия', linewidth=2)
        axes[1].set_title('Чек-ины')
        axes[1].set_ylabel('Оценка (1-10)')
        axes[1].set_ylim(0, 11)
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    else:
        axes[1].text(0.5, 0.5, 'Нет чек-инов за 7 дней',
                    ha='center', va='center', transform=axes[1].transAxes)
        axes[1].set_title('Чек-ины')

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf