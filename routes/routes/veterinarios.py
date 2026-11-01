from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models.veterinario import Veterinario
from models.consulta import Consulta
from models.disponibilidade import Disponibilidade


veterinarios_bp = Blueprint("veterinarios", __name__)


def validar_campos(dados, campos_obrigatorios=False):
    if not isinstance(dados, dict) or not dados:
        return "Envie os dados em formato JSON."

    campos = ("nome", "crmv", "especialidade")

    for campo in campos:
        valor = dados.get(campo)

        if campos_obrigatorios and (not isinstance(valor, str) or not valor.strip()):
            return f"O campo {campo} é obrigatório."

        if campo in dados:
            if not isinstance(valor, str) or not valor.strip():
                return f"O campo {campo} deve ser um texto válido."
            dados[campo] = valor.strip()

    return None


def serializar_veterinario(veterinario):
    return {
        "id": veterinario.id,
        "nome": veterinario.nome,
        "crmv": veterinario.crmv,
        "especialidade": veterinario.especialidade
    }


@veterinarios_bp.route("/veterinarios", methods=["POST"])
def cadastrar_veterinario():
    dados = request.get_json(silent=True)
    erro = validar_campos(dados, campos_obrigatorios=True)

    if erro:
        return jsonify({"erro": erro}), 400

    existente = Veterinario.query.filter_by(crmv=dados["crmv"]).first()

    if existente:
        return jsonify({"erro": "CRMV já cadastrado."}), 409

    novo_veterinario = Veterinario(
        nome=dados["nome"],
        crmv=dados["crmv"],
        especialidade=dados["especialidade"]
    )

    try:
        db.session.add(novo_veterinario)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"erro": "CRMV já cadastrado."}), 409
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"erro": "Não foi possível cadastrar o veterinário."}), 500

    return jsonify({
        "mensagem": "Veterinário cadastrado com sucesso.",
        "veterinario": serializar_veterinario(novo_veterinario)
    }), 201


@veterinarios_bp.route("/veterinarios", methods=["GET"])
def listar_veterinarios():
    try:
        veterinarios = Veterinario.query.order_by(Veterinario.id).all()
        return jsonify([
            serializar_veterinario(veterinario)
            for veterinario in veterinarios
        ]), 200
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"erro": "Não foi possível listar os veterinários."}), 500


@veterinarios_bp.route("/veterinarios/<int:id>", methods=["GET"])
def buscar_veterinario(id):
    try:
        veterinario = db.session.get(Veterinario, id)

        if not veterinario:
            return jsonify({"erro": "Veterinário não encontrado."}), 404

        return jsonify(serializar_veterinario(veterinario)), 200
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"erro": "Não foi possível buscar o veterinário."}), 500


@veterinarios_bp.route("/veterinarios/<int:id>", methods=["PUT"])
def atualizar_veterinario(id):
    veterinario = db.session.get(Veterinario, id)

    if not veterinario:
        return jsonify({"erro": "Veterinário não encontrado."}), 404

    dados = request.get_json(silent=True)
    erro = validar_campos(dados)

    if erro:
        return jsonify({"erro": erro}), 400

    if not any(campo in dados for campo in ("nome", "crmv", "especialidade")):
        return jsonify({"erro": "Informe ao menos um campo para atualizar."}), 400

    if "crmv" in dados:
        existente = Veterinario.query.filter(
            Veterinario.crmv == dados["crmv"],
            Veterinario.id != id
        ).first()

        if existente:
            return jsonify({"erro": "CRMV já cadastrado."}), 409

    for campo in ("nome", "crmv", "especialidade"):
        if campo in dados:
            setattr(veterinario, campo, dados[campo])

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"erro": "CRMV já cadastrado."}), 409
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"erro": "Não foi possível atualizar o veterinário."}), 500

    return jsonify({
        "mensagem": "Veterinário atualizado com sucesso.",
        "veterinario": serializar_veterinario(veterinario)
    }), 200


@veterinarios_bp.route("/veterinarios/<int:id>", methods=["DELETE"])
def excluir_veterinario(id):
    veterinario = db.session.get(Veterinario, id)

    if not veterinario:
        return jsonify({"erro": "Veterinário não encontrado."}), 404

    try:
        consulta_existente = Consulta.query.filter_by(
            veterinario_id=id
        ).first()

        if consulta_existente:
            return jsonify({
                "erro": "Não é possível excluir este veterinário porque existem consultas vinculadas."
            }), 409

        disponibilidade_existente = Disponibilidade.query.filter_by(
            veterinario_id=id
        ).first()

        if disponibilidade_existente:
            return jsonify({
                "erro": "Não é possível excluir este veterinário porque existem disponibilidades vinculadas."
            }), 409

        db.session.delete(veterinario)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"erro": "Não foi possível excluir o veterinário."}), 500

    return jsonify({
        "mensagem": "Veterinário excluído com sucesso."
    }), 200
