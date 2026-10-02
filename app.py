from flask import Flask, jsonify
from flask_cors import CORS
from extensions import db
from models.usuario import Usuario
from routes.routes.usuarios import usuarios_bp
from models.pet import Pet
from routes.routes.pets import pets_bp

app = Flask(__name__)

CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///clinica.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

app.register_blueprint(usuarios_bp)
app.register_blueprint(pets_bp)


@app.route("/")
def inicio():
    return jsonify({
        "mensagem": "API da Clínica Veterinária UNIESP funcionando!"
    })

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)