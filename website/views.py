from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from . import db
from .models import User

from website.library.portfolio import RISK_VALUES, create_portfolio

views = Blueprint('views', __name__)


@views.route('/', methods=['GET', 'POST'])
def home():
    risk_question = 'Как я отношусь к риску?'
    time_question = 'На какой срок я собираюсь инвестировать?'
    max_instruments_question = 'Сколько инструментов я готов купить?'
    questions = [
        {
            'question': risk_question,
            'options': RISK_VALUES
        },
        {
            'question': time_question,
            'options': [
                {'value': 'month_1', 'label': '1 месяц'},
                {'value': 'month_6', 'label': '6 месяцев'},
                {'value': 'year_1', 'label': '1 год'},
                {'value': 'year_2', 'label': '2 года'},
                {'value': 'year_3', 'label': '3 года'},
                {'value': 'year_more', 'label': 'больше 3 лет'},
            ]
        },
        {
            'question': max_instruments_question,
            'options': [
                {'value': '5', 'label': 'Не более 5'},
                {'value': '10', 'label': 'Не более 10'},
                {'value': '20', 'label': 'Не более 20'},
                {'value': '-1', 'label': 'Мне не важно'},
            ]
        }
    ]
    if request.method == 'POST':
        risk_answer = request.form.get(risk_question)
        time_answer = request.form.get(time_question)
        capital_answer = float(request.form.get('capital'))
        max_instruments_answer = int(request.form.get(max_instruments_question))
        if max_instruments_answer == -1:
            max_instruments_answer = None
        portfolio = create_portfolio(capital=capital_answer, risk=risk_answer, max_instruments=max_instruments_answer)
        return render_template('portfolio.html', portfolio=portfolio, user=current_user)
    return render_template('form.html', questions=questions, user=current_user)
