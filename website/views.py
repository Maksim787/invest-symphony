from flask import Blueprint, render_template, request

from website.library.portfolio import RISK_VALUES, create_portfolio

# Create /views
views = Blueprint("views", __name__)

# Define questions in the form
RISK_QUESTION = "Как я отношусь к риску?"
TIME_QUESTION = "На какой срок я собираюсь инвестировать?"
MAX_INSTRUMENTS_QUESTION = "Сколько инструментов я готов купить?"
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
    }
]


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
    time_answer = request.form.get(TIME_QUESTION)  # TODO: currently unused, filter bonds by this field
    capital_answer = float(request.form.get("capital"))
    max_instruments_answer = int(request.form.get(MAX_INSTRUMENTS_QUESTION))
    if max_instruments_answer == -1:
        max_instruments_answer = None
    # Construct portfolio
    portfolio = create_portfolio(capital=capital_answer, risk=risk_answer, max_instruments=max_instruments_answer)
    # TODO: add here graphs for portfolio
    # Show portfolio
    return render_template("portfolio.html", portfolio=portfolio)
