import pytest

from app import create_app
from extensions import db


@pytest.fixture
def app():
    """
    Cria uma aplicação isolada para cada teste.

    Utiliza SQLite em memória para impedir que os testes
    alterem o banco de dados utilizado pela aplicação.
    """

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": (
            "chave-segura-exclusiva-para-testes-uniesp-2026"
        ),
    })

    with app.app_context():
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """
    Disponibiliza um cliente HTTP para testar as rotas da API.
    """

    return app.test_client()