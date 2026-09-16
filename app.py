from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)

CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///clinica.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


@app.route("/")
def inicio():
    return jsonify({
        "mensagem": "API da Clínica Veterinária UNIESP funcionando!"
    })


if __name__ == "__main__":
    app.run(debug=True)