from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from . import db
from .models import User

from website.library.stock_only_portfolio import RISK_VALUES, create_stock_only_portfolio

views = Blueprint('views', __name__)


@views.route('/', methods=['GET', 'POST'])
def home():
    risk_question = 'Как вы относитесь к риску?'
    time_question = 'На какой срок вы собираетесь инвестировать?'
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
        }
    ]
    if request.method == 'POST':
        risk_answer = request.form.get(questions[0]['question'])
        time_answer = request.form.get(questions[1]['question'])
        capital_answer = float(request.form.get('capital'))
        portfolio = create_stock_only_portfolio(capital=capital_answer, risk=risk_answer)
        return render_template('portfolio.html', portfolio=portfolio, user=current_user)
    return render_template('form.html', questions=questions, user=current_user)
