from flask import Blueprint, request, jsonify
from extensions import db
from models.veterinario import Veterinario


veterinarios_bp = Blueprint("veterinarios", __name__)


@veterinarios_bp.route("/veterinarios", methods=["POST"])
def cadastrar_veterinario():
    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Dados não enviados"
        }), 400

    nome = dados.get("nome")
    crmv = dados.get("crmv")
    especialidade = dados.get("especialidade")

    if not nome or not crmv or not especialidade:
        return jsonify({
            "erro": "Nome, crmv e especialidade são obrigatórios"
        }), 400

    veterinario_existente = Veterinario.query.filter_by(crmv=crmv).first()

    if veterinario_existente:
        return jsonify({
            "erro": "CRMV já cadastrado"
        }), 409

    novo_veterinario = Veterinario(
        nome=nome,
        crmv=crmv,
        especialidade=especialidade
    )

    db.session.add(novo_veterinario)
    db.session.commit()

    return jsonify({
        "mensagem": "Veterinário cadastrado com sucesso",
        "veterinario": {
            "id": novo_veterinario.id,
            "nome": novo_veterinario.nome,
            "crmv": novo_veterinario.crmv,
            "especialidade": novo_veterinario.especialidade
        }
    }), 201


@veterinarios_bp.route("/veterinarios", methods=["GET"])
def listar_veterinarios():
    veterinarios = Veterinario.query.all()

    resultado = []

    for veterinario in veterinarios:
        resultado.append({
            "id": veterinario.id,
            "nome": veterinario.nome,
            "crmv": veterinario.crmv,
            "especialidade": veterinario.especialidade
        })

    return jsonify(resultado), 200


@veterinarios_bp.route("/veterinarios/<int:id>", methods=["GET"])
def buscar_veterinario(id):
    veterinario = db.session.get(Veterinario, id)

    if not veterinario:
        return jsonify({
            "erro": "Veterinário não encontrado"
        }), 404

    return jsonify({
        "id": veterinario.id,
        "nome": veterinario.nome,
        "crmv": veterinario.crmv,
        "especialidade": veterinario.especialidade
    }), 200


@veterinarios_bp.route("/veterinarios/<int:id>", methods=["PUT"])
def atualizar_veterinario(id):
    veterinario = db.session.get(Veterinario, id)

    if not veterinario:
        return jsonify({
            "erro": "Veterinário não encontrado"
        }), 404

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Dados não enviados"
        }), 400

    if "nome" in dados:
        veterinario.nome = dados["nome"]

    if "crmv" in dados:
        veterinario.crmv = dados["crmv"]

    if "especialidade" in dados:
        veterinario.especialidade = dados["especialidade"]

    db.session.commit()

    return jsonify({
        "mensagem": "Veterinário atualizado com sucesso",
        "veterinario": {
            "id": veterinario.id,
            "nome": veterinario.nome,
            "crmv": veterinario.crmv,
            "especialidade": veterinario.especialidade
        }
    }), 200


@veterinarios_bp.route("/veterinarios/<int:id>", methods=["DELETE"])
def excluir_veterinario(id):
    veterinario = db.session.get(Veterinario, id)

    if not veterinario:
        return jsonify({
            "erro": "Veterinário não encontrado"
        }), 404

    db.session.delete(veterinario)
    db.session.commit()

    return jsonify({
        "mensagem": "Veterinário excluído com sucesso"
    }), 200