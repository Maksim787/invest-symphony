import datetime
from flask import Blueprint, render_template, request

from website.library import RISK_VALUES, create_portfolio, create_graphs

# Create /views
views = Blueprint("views", __name__)

# Define questions in the form
RISK_QUESTION = "Как я отношусь к риску?"
TIME_QUESTION = "На какой срок я собираюсь инвестировать?"
MAX_INSTRUMENTS_QUESTION = "Сколько инструментов я готов купить?"
BONDS_OR_SHARES_QUESTION = "Инструменты какого типа вы хотели бы взять в портфель?"
ALL_QUESTIONS = [
    {
        "question": RISK_QUESTION,
        "options": RISK_VALUES
    },
    {
        "question": TIME_QUESTION,
        "options": [
            {"value": "month_1", "label": "1 месяц"},
            {"value": "month_6", "label": "6 месяцев"},
            {"value": "year_1", "label": "1 год"},
            {"value": "year_2", "label": "2 года"},
            {"value": "year_3", "label": "3 года"},
            {"value": "year_more", "label": "больше 3 лет"},
        ]
    },
    {
        "question": MAX_INSTRUMENTS_QUESTION,
        "options": [
            {"value": "5", "label": "Не более 5"},
            {"value": "10", "label": "Не более 10"},
            {"value": "20", "label": "Не более 20"},
            {"value": "-1", "label": "Мне не важно"},
        ]
    },
    {
        "question": BONDS_OR_SHARES_QUESTION,
        "options": [
            {"value": "both", "label": "И акции, и облигации"},
            {"value": "shares", "label": "Только акции"},
            {"value": "bonds", "label": "Только облигации"},
        ]
    }
]


def parse_time_answer(time_answer: str) -> datetime.timedelta | None:
    if time_answer.startswith('month_'):
        months = int(time_answer.removeprefix('month_'))
        return datetime.timedelta(days=30 * months)
    elif time_answer.startswith('year_'):
        if time_answer == 'year_more':
            return None
        years = int(time_answer.removeprefix('year_'))
        return datetime.timedelta(days=365 * years)
    else:
        assert False, 'Unreachable'


@views.route("/", methods=["GET"])
def home_get():
    """
    Return form with questions
    """
    return render_template("form.html", questions=ALL_QUESTIONS)


@views.route("/", methods=["POST"])
def home_post():
    """
    Construct portfolio for given answers
    """
    # Get answers for questions
    risk_answer = request.form.get(RISK_QUESTION)

    time_answer = parse_time_answer(request.form.get(TIME_QUESTION))

    capital_answer = float(request.form.get("capital"))

    max_instruments_answer = int(request.form.get(MAX_INSTRUMENTS_QUESTION))
    if max_instruments_answer == -1:
        max_instruments_answer = None

    bonds_or_shares_answer = request.form.get(BONDS_OR_SHARES_QUESTION)

    # Construct portfolio
    portfolio = create_portfolio(total_capital=capital_answer, risk=risk_answer, max_instruments=max_instruments_answer, time_answer=time_answer, bonds_or_shares_answer=bonds_or_shares_answer)

    # Create graphs for portfolio
    graphs = create_graphs(portfolio)

    # Show portfolio
    return render_template("portfolio.html", portfolio=portfolio, graphs=graphs)
