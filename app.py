import os
from datetime import timedelta

from flask import Flask, jsonify
from flask_cors import CORS

from extensions import db, jwt

from models.usuario import Usuario
from models.veterinario import Veterinario
from models.disponibilidade import Disponibilidade
from models.pet import Pet

from routes.usuarios import usuarios_bp
from routes.routes.veterinarios import veterinarios_bp
from routes.routes.disponibilidade import disponibilidade_bp
from routes.routes.pets import pets_bp


def create_app(config=None):
    app = Flask(__name__)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL", "sqlite:///clinica.db"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv(
            "JWT_SECRET_KEY",
            "CHAVE_TEMPORARIA_DESENVOLVIMENTO_UNIESP_2026"
        ),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=1),
    )

    if config:
        app.config.update(config)

    CORS(app)

    db.init_app(app)
    jwt.init_app(app)

    app.register_blueprint(usuarios_bp)
    app.register_blueprint(veterinarios_bp)
    app.register_blueprint(disponibilidade_bp)
    app.register_blueprint(pets_bp)

    @app.get("/")
    def inicio():
        return jsonify(
            mensagem="API da Clínica Veterinária UNIESP funcionando!"
        )

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
