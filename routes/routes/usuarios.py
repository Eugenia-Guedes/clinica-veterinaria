from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
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

@usuarios_bp.route("/usuarios/<int:id>", methods=["GET"])
def buscar_usuario(id):
    usuario = db.session.get(Usuario, id)

    if not usuario:
        return jsonify({
            "erro": "Usuário não encontrado"
        }), 404

    return jsonify({
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "telefone": usuario.telefone
    }), 200

@usuarios_bp.route("/usuarios/<int:id>", methods=["PUT"])
def atualizar_usuario(id):
    usuario = db.session.get(Usuario, id)

    if not usuario:
        return jsonify({
            "erro": "Usuário não encontrado"
        }), 404

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Dados não enviados"
        }), 400

    if "nome" in dados:
        usuario.nome = dados["nome"]

    if "email" in dados:
        usuario.email = dados["email"]

    if "telefone" in dados:
        usuario.telefone = dados["telefone"]

    if "senha" in dados:
        usuario.senha = generate_password_hash(dados["senha"])

    db.session.commit()

    return jsonify({
        "mensagem": "Usuário atualizado com sucesso",
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "telefone": usuario.telefone
        }
    }), 200

@usuarios_bp.route("/usuarios/<int:id>", methods=["DELETE"])
def excluir_usuario(id):
    usuario = db.session.get(Usuario, id)

    if not usuario:
        return jsonify({
            "erro": "Usuário não encontrado"
        }), 404

    db.session.delete(usuario)
    db.session.commit()

    return jsonify({
        "mensagem": "Usuário excluído com sucesso"
    }), 200

@usuarios_bp.route("/login", methods=["POST"])
def login():
    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Dados não enviados"
        }), 400

    email = dados.get("email")
    senha = dados.get("senha")

    if not email or not senha:
        return jsonify({
            "erro": "E-mail e senha são obrigatórios"
        }), 400

    usuario = Usuario.query.filter_by(email=email).first()

    if not usuario:
        return jsonify({
            "erro": "E-mail ou senha inválidos"
        }), 401

    if not check_password_hash(usuario.senha, senha):
        return jsonify({
            "erro": "E-mail ou senha inválidos"
        }), 401

    return jsonify({
        "mensagem": "Login realizado com sucesso",
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email
        }
    }), 200