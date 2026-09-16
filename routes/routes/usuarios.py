from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash

from extensions import db
from models.usuario import Usuario


usuarios_bp = Blueprint("usuarios", __name__)


@usuarios_bp.route("/usuarios", methods=["POST"])
def cadastrar_usuario():
    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Dados não enviados"
        }), 400

    nome = dados.get("nome")
    email = dados.get("email")
    telefone = dados.get("telefone")
    senha = dados.get("senha")

    if not nome or not email or not telefone or not senha:
        return jsonify({
            "erro": "Nome, email, telefone e senha são obrigatórios"
        }), 400

    usuario_existente = Usuario.query.filter_by(email=email).first()

    if usuario_existente:
        return jsonify({
            "erro": "E-mail já cadastrado"
        }), 409

    senha_hash = generate_password_hash(senha)

    novo_usuario = Usuario(
        nome=nome,
        email=email,
        telefone=telefone,
        senha=senha_hash
    )

    db.session.add(novo_usuario)
    db.session.commit()

    return jsonify({
        "mensagem": "Usuário cadastrado com sucesso",
        "usuario": {
            "id": novo_usuario.id,
            "nome": novo_usuario.nome,
            "email": novo_usuario.email,
            "telefone": novo_usuario.telefone
        }
    }), 201

@usuarios_bp.route("/usuarios", methods=["GET"])
def listar_usuarios():
    usuarios = Usuario.query.all()

    resultado = []

    for usuario in usuarios:
        resultado.append({
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "telefone": usuario.telefone
        })

    return jsonify(resultado), 200