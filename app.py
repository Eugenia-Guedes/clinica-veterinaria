from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///clinica.db"

db = SQLAlchemy(app)


@app.route("/")
def inicio():
    return jsonify({
        "mensagem": "API da Clínica Veterinária UNIESP"
    })


if __name__ == "__main__":
    app.run(debug=True)