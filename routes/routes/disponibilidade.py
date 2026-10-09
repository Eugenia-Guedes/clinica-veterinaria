import unicodedata
from datetime import datetime

from flask import Blueprint, request, jsonify
from extensions import db
from models.disponibilidade import Disponibilidade


disponibilidade_bp = Blueprint("disponibilidade", __name__)

# Ordem igual ao datetime.weekday(): segunda = 0 ... domingo = 6
DIAS_SEMANA = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]


def disponibilidade_para_dict(disponibilidade):
    """Transforma um objeto Disponibilidade em um dicionário para virar JSON."""
    return {
        "id": disponibilidade.id,
        "veterinario_id": disponibilidade.veterinario_id,
        "dia_semana": disponibilidade.dia_semana,
        "hora_inicio": disponibilidade.hora_inicio,
        "hora_fim": disponibilidade.hora_fim
    }


def inteiro_valido(valor):
    """True só para inteiros de verdade (True/False também são int no Python)."""
    return isinstance(valor, int) and not isinstance(valor, bool)


def normalizar_dia(valor):
    """Aceita 'Segunda', 'terça', 'SABADO'... e devolve 'segunda', 'terca', 'sabado'.
    Se não for um dia válido, devolve None."""
    if not isinstance(valor, str):
        return None

    texto = unicodedata.normalize("NFD", valor.strip().lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")

    return texto if texto in DIAS_SEMANA else None


def normalizar_hora(valor):
    """Converte '8:00' ou '08:00' em '08:00'. Se for inválida, devolve None."""
    try:
        return datetime.strptime(valor, "%H:%M").strftime("%H:%M")
    except (ValueError, TypeError):
        return None


def validar_horarios(hora_inicio, hora_fim):
    inicio = normalizar_hora(hora_inicio)
    fim = normalizar_hora(hora_fim)

    if inicio is None or fim is None:
        return False

    return inicio < fim


def ja_existe(veterinario_id, dia_semana, ignorar_id=None):
    """Verifica se o veterinário já tem disponibilidade cadastrada nesse dia."""
    consulta = Disponibilidade.query.filter_by(
        veterinario_id=veterinario_id,
        dia_semana=dia_semana
    )

    if ignorar_id is not None:
        consulta = consulta.filter(Disponibilidade.id != ignorar_id)

    return consulta.first() is not None


@disponibilidade_bp.route("/disponibilidade", methods=["POST"])
def cadastrar_disponibilidade():
    dados = request.get_json()

    if not dados:
        return jsonify({"erro": "Dados não enviados"}), 400

    veterinario_id = dados.get("veterinario_id")
    dia_semana = dados.get("dia_semana")
    hora_inicio = dados.get("hora_inicio")
    hora_fim = dados.get("hora_fim")

    if veterinario_id is None or not dia_semana or not hora_inicio or not hora_fim:
        return jsonify({
            "erro": "veterinario_id, dia_semana, hora_inicio e hora_fim são obrigatórios"
        }), 400

    if not inteiro_valido(veterinario_id):
        return jsonify({"erro": "veterinario_id deve ser um número inteiro"}), 400

    dia_normalizado = normalizar_dia(dia_semana)

    if dia_normalizado is None:
        return jsonify({
            "erro": "Dia da semana inválido. Use: segunda, terca, quarta, quinta, sexta, sabado ou domingo"
        }), 400

    if not validar_horarios(hora_inicio, hora_fim):
        return jsonify({
            "erro": "Horários inválidos. Use HH:MM e informe o início antes do fim"
        }), 400

    if ja_existe(veterinario_id, dia_normalizado):
        return jsonify({
            "erro": "Já existe disponibilidade para esse veterinário nesse dia"
        }), 409

    nova = Disponibilidade(
        veterinario_id=veterinario_id,
        dia_semana=dia_normalizado,
        hora_inicio=normalizar_hora(hora_inicio),
        hora_fim=normalizar_hora(hora_fim)
    )

    db.session.add(nova)
    db.session.commit()

    return jsonify({
        "mensagem": "Disponibilidade cadastrada com sucesso",
        "disponibilidade": disponibilidade_para_dict(nova)
    }), 201


@disponibilidade_bp.route("/disponibilidade", methods=["GET"])
def listar_disponibilidades():
    veterinario_id = request.args.get("veterinario_id", type=int)

    if veterinario_id is not None:
        disponibilidades = Disponibilidade.query.filter_by(
            veterinario_id=veterinario_id
        ).all()
    else:
        disponibilidades = Disponibilidade.query.all()

    resultado = []

    for item in disponibilidades:
        resultado.append(disponibilidade_para_dict(item))

    return jsonify(resultado), 200


@disponibilidade_bp.route("/disponibilidade/<int:id>", methods=["GET"])
def buscar_disponibilidade(id):
    disponibilidade = db.session.get(Disponibilidade, id)

    if not disponibilidade:
        return jsonify({"erro": "Disponibilidade não encontrada"}), 404

    return jsonify(disponibilidade_para_dict(disponibilidade)), 200


@disponibilidade_bp.route("/disponibilidade/<int:id>", methods=["PUT"])
def atualizar_disponibilidade(id):
    disponibilidade = db.session.get(Disponibilidade, id)

    if not disponibilidade:
        return jsonify({"erro": "Disponibilidade não encontrada"}), 404

    dados = request.get_json()

    if not dados:
        return jsonify({"erro": "Dados não enviados"}), 400

    # Começa com os valores atuais e troca só o que veio no JSON.
    # Nada é gravado no objeto antes de validar tudo.
    veterinario_id = disponibilidade.veterinario_id
    dia_semana = disponibilidade.dia_semana
    hora_inicio = disponibilidade.hora_inicio
    hora_fim = disponibilidade.hora_fim

    if "veterinario_id" in dados:
        if not inteiro_valido(dados["veterinario_id"]):
            return jsonify({"erro": "veterinario_id deve ser um número inteiro"}), 400
        veterinario_id = dados["veterinario_id"]

    if "dia_semana" in dados:
        dia_semana = normalizar_dia(dados["dia_semana"])

        if dia_semana is None:
            return jsonify({
                "erro": "Dia da semana inválido. Use: segunda, terca, quarta, quinta, sexta, sabado ou domingo"
            }), 400

    if "hora_inicio" in dados:
        hora_inicio = dados["hora_inicio"]

    if "hora_fim" in dados:
        hora_fim = dados["hora_fim"]

    if not validar_horarios(hora_inicio, hora_fim):
        return jsonify({
            "erro": "Horários inválidos. Use HH:MM e informe o início antes do fim"
        }), 400

    if ja_existe(veterinario_id, dia_semana, ignorar_id=id):
        return jsonify({
            "erro": "Já existe disponibilidade para esse veterinário nesse dia"
        }), 409

    disponibilidade.veterinario_id = veterinario_id
    disponibilidade.dia_semana = dia_semana
    disponibilidade.hora_inicio = normalizar_hora(hora_inicio)
    disponibilidade.hora_fim = normalizar_hora(hora_fim)

    db.session.commit()

    return jsonify({
        "mensagem": "Disponibilidade atualizada com sucesso",
        "disponibilidade": disponibilidade_para_dict(disponibilidade)
    }), 200


@disponibilidade_bp.route("/disponibilidade/<int:id>", methods=["DELETE"])
def excluir_disponibilidade(id):
    disponibilidade = db.session.get(Disponibilidade, id)

    if not disponibilidade:
        return jsonify({"erro": "Disponibilidade não encontrada"}), 404

    db.session.delete(disponibilidade)
    db.session.commit()

    return jsonify({"mensagem": "Disponibilidade excluída com sucesso"}), 200


@disponibilidade_bp.route("/disponibilidade/verificar", methods=["GET"])
def verificar_disponibilidade():
    veterinario_id = request.args.get("veterinario_id", type=int)
    data = request.args.get("data")
    hora = request.args.get("hora")

    if veterinario_id is None or not data or not hora:
        return jsonify({
            "erro": "veterinario_id, data e hora são obrigatórios"
        }), 400

    try:
        data_consulta = datetime.strptime(data, "%Y-%m-%d")
        hora_consulta = datetime.strptime(hora, "%H:%M")
    except ValueError:
        return jsonify({
            "erro": "Data deve estar no formato AAAA-MM-DD e hora no formato HH:MM"
        }), 400

    dia_semana = DIAS_SEMANA[data_consulta.weekday()]

    disponibilidades = Disponibilidade.query.filter_by(
        veterinario_id=veterinario_id,
        dia_semana=dia_semana
    ).all()

    for item in disponibilidades:
        inicio = datetime.strptime(item.hora_inicio, "%H:%M")
        fim = datetime.strptime(item.hora_fim, "%H:%M")

        if inicio <= hora_consulta < fim:
            return jsonify({
                "disponivel": True,
                "mensagem": "Horário disponível"
            }), 200

    return jsonify({
        "disponivel": False,
        "mensagem": "Horário não disponível"
    }), 200
