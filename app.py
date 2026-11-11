import os
from datetime import timedelta

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from extensions import db, jwt

from models.usuario import Usuario
from models.veterinario import Veterinario
from models.disponibilidade import Disponibilidade
from models.pet import Pet
from models.consulta import Consulta

from routes.usuarios import usuarios_bp
from routes.routes.veterinarios import veterinarios_bp
from routes.routes.disponibilidade import disponibilidade_bp
from routes.routes.pets import pets_bp
from routes.consultas import consultas_bp


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
    app.register_blueprint(consultas_bp)


    @app.get("/openapi.yaml")
    def arquivo_openapi():
        return send_from_directory(
            os.path.join(app.root_path, "docs"),
            "openapi.yaml"
        )
    @app.get("/docs/<path:nome_arquivo>")
    def arquivos_documentacao(nome_arquivo):
        return send_from_directory(
            os.path.join(app.root_path, "docs"),
            nome_arquivo
        )

    @app.get("/docs/")
    def swagger_ui():
        return """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>Swagger - Clínica Veterinária</title>
            <link rel="stylesheet"
              href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
            <script>
                SwaggerUIBundle({
                    url: "/docs/openapi.yaml",
                    dom_id: "#swagger-ui"
                });
            </script>
        </body>
        </html>
        """


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
