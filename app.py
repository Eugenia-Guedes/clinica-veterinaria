from flask import Flask, jsonify
from flask_cors import CORS
from extensions import db
from models.usuario import Usuario

app = Flask(__name__)

CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///clinica.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


@app.route("/")
def inicio():
    return jsonify({
        "mensagem": "API da Clínica Veterinária UNIESP funcionando!"
    })

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)