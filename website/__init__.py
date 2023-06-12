from pathlib import Path
import asyncio

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

from download_data.download_tickers import download_tickers
from download_data.download_day_close_or_candles import download_day_close_or_candles, TimeSeriesConfig, TimeSeriesType


db = SQLAlchemy()
DB_NAME = "database.db"


def create_app():
    download_all_data()

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'some secret key'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    db.init_app(app)

    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    from .models import User

    with app.app_context():
        db.create_all()

    login_manager = LoginManager()
    login_manager.login_view = None
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    return app


def download_all_data():
    # Download data
    data_path = Path('data')
    if not data_path.exists():
        data_path.mkdir()
        asyncio.run(download_tickers())
        asyncio.run(download_day_close_or_candles(
            time_series_folder=Path('data/day_close/'),
            time_series_config=TimeSeriesConfig(TimeSeriesType.CLOSE)
        ))


def create_database(app):
    db.create_all(app=app)
    print('Created Database!')
