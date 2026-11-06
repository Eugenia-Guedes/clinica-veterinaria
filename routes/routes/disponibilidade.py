
import unicodedata
from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.disponibilidade import Disponibilidade
from models.veterinario import Veterinario
from routes.consultas import (
    DURACAO_PADRAO,
    validar_duracao,
    veterinario_disponivel,
    existe_conflito_veterinario,
)

disponibilidade_bp = Blueprint("disponibilidade", __name__)

DIAS_SEMANA = (
    "segunda",
    "terca",
    "quarta",
    "quinta",
    "sexta",
    "sabado",
    "domingo",
)

DIA_DOMINGO = "domingo"


def disponibilidade_para_dict(disponibilidade):
    """Converte uma disponibilidade em dicionário para resposta JSON."""
    return {
        "id": disponibilidade.id,
        "veterinario_id": disponibilidade.veterinario_id,
        "dia_semana": disponibilidade.dia_semana,
        "hora_inicio": disponibilidade.hora_inicio,
        "hora_fim": disponibilidade.hora_fim,
    }


def inteiro_valido(valor):
    """Aceita inteiros, mas rejeita valores booleanos."""
    return isinstance(valor, int) and not isinstance(valor, bool)


def normalizar_dia(valor):
    """Normaliza o nome do dia, removendo acentos e espaços."""
    if not isinstance(valor, str):
        return None

    texto = unicodedata.normalize("NFD", valor.strip().lower())
    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    return texto if texto in DIAS_SEMANA else None


def normalizar_hora(valor):
    """Valida e normaliza um horário para o formato HH:MM."""
    try:
        return datetime.strptime(valor, "%H:%M").strftime("%H:%M")
    except (ValueError, TypeError):
        return None


def validar_horarios(hora_inicio, hora_fim):
    """Verifica se os horários são válidos e se o início precede o fim."""
    inicio = normalizar_hora(hora_inicio)
    fim = normalizar_hora(hora_fim)

    return inicio is not None and fim is not None and inicio < fim


def veterinario_existe(veterinario_id):
    """Verifica se o veterinário está cadastrado."""
    return db.session.get(Veterinario, veterinario_id) is not None


def existe_sobreposicao(
    veterinario_id,
    dia_semana,
    hora_inicio,
    hora_fim,
    ignorar_id=None,
):
    """
    Verifica se existe outro período que se sobrepõe ao informado.

    Períodos consecutivos são permitidos:
    08:00–12:00 e 12:00–16:00.
    """
    consulta = Disponibilidade.query.filter(
        Disponibilidade.veterinario_id == veterinario_id,
        Disponibilidade.dia_semana == dia_semana,
        Disponibilidade.hora_inicio < hora_fim,
        Disponibilidade.hora_fim > hora_inicio,
    )

    if ignorar_id is not None:
        consulta = consulta.filter(Disponibilidade.id != ignorar_id)

    return consulta.first() is not None


def validar_dados_disponibilidade(
    veterinario_id,
    dia_semana,
    hora_inicio,
    hora_fim,
    ignorar_id=None,
):
    """
    Valida os dados de uma disponibilidade.

    Retorna uma mensagem de erro ou None quando os dados são válidos.
    """
    if not inteiro_valido(veterinario_id):
        return "veterinario_id deve ser um número inteiro", 400

    dia_normalizado = normalizar_dia(dia_semana)

    if dia_normalizado is None:
        return "Dia da semana inválido", 400

    if dia_normalizado == DIA_DOMINGO:
        return "Não é permitido cadastrar disponibilidade aos domingos", 400

    inicio = normalizar_hora(hora_inicio)
    fim = normalizar_hora(hora_fim)

    if inicio is None or fim is None or inicio >= fim:
        return "Horários inválidos. Use HH:MM e informe o início antes do fim", 400

    if not veterinario_existe(veterinario_id):
        return "Veterinário não encontrado", 404

    if existe_sobreposicao(
        veterinario_id,
        dia_normalizado,
        inicio,
        fim,
        ignorar_id,
    ):
        return "O horário informado se sobrepõe a outra disponibilidade", 409

    return None, None


def salvar_alteracao():
    """Confirma a transação ou desfaz alterações em caso de falha."""
    try:
        db.session.commit()
        return True
    except SQLAlchemyError:
        db.session.rollback()
        return False


@disponibilidade_bp.route("/disponibilidade", methods=["POST"])
def cadastrar_disponibilidade():
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return jsonify({"erro": "Envie um objeto JSON válido"}), 400

    campos_obrigatorios = (
        "veterinario_id",
        "dia_semana",
        "hora_inicio",
        "hora_fim",
    )

    if any(campo not in dados for campo in campos_obrigatorios):
        return jsonify({
            "erro": "veterinario_id, dia_semana, hora_inicio e hora_fim são obrigatórios"
        }), 400

    erro, status = validar_dados_disponibilidade(
        dados["veterinario_id"],
        dados["dia_semana"],
        dados["hora_inicio"],
        dados["hora_fim"],
    )

    if erro:
        return jsonify({"erro": erro}), status

    nova_disponibilidade = Disponibilidade(
        veterinario_id=dados["veterinario_id"],
        dia_semana=normalizar_dia(dados["dia_semana"]),
        hora_inicio=normalizar_hora(dados["hora_inicio"]),
        hora_fim=normalizar_hora(dados["hora_fim"]),
    )

    db.session.add(nova_disponibilidade)

    if not salvar_alteracao():
        return jsonify({"erro": "Não foi possível cadastrar a disponibilidade"}), 500

    return jsonify({
        "mensagem": "Disponibilidade cadastrada com sucesso",
        "disponibilidade": disponibilidade_para_dict(nova_disponibilidade),
    }), 201


@disponibilidade_bp.route("/disponibilidade", methods=["GET"])
def listar_disponibilidades():
    veterinario_id = request.args.get("veterinario_id", type=int)

    consulta = Disponibilidade.query

    if veterinario_id is not None:
        consulta = consulta.filter_by(veterinario_id=veterinario_id)

    disponibilidades = consulta.order_by(
        Disponibilidade.veterinario_id,
        Disponibilidade.dia_semana,
        Disponibilidade.hora_inicio,
    ).all()

    return jsonify([
        disponibilidade_para_dict(item)
        for item in disponibilidades
    ]), 200


@disponibilidade_bp.route("/disponibilidade/<int:id>", methods=["GET"])
def buscar_disponibilidade(id):
    disponibilidade = db.session.get(Disponibilidade, id)

    if disponibilidade is None:
        return jsonify({"erro": "Disponibilidade não encontrada"}), 404

    return jsonify(disponibilidade_para_dict(disponibilidade)), 200


@disponibilidade_bp.route("/disponibilidade/<int:id>", methods=["PUT"])
def atualizar_disponibilidade(id):
    disponibilidade = db.session.get(Disponibilidade, id)

    if disponibilidade is None:
        return jsonify({"erro": "Disponibilidade não encontrada"}), 404

    dados = request.get_json(silent=True)

    if not isinstance(dados, dict) or not dados:
        return jsonify({"erro": "Envie um objeto JSON válido com os dados da atualização"}), 400

    veterinario_id = dados.get(
        "veterinario_id",
        disponibilidade.veterinario_id,
    )
    dia_semana = dados.get(
        "dia_semana",
        disponibilidade.dia_semana,
    )
    hora_inicio = dados.get(
        "hora_inicio",
        disponibilidade.hora_inicio,
    )
    hora_fim = dados.get(
        "hora_fim",
        disponibilidade.hora_fim,
    )

    erro, status = validar_dados_disponibilidade(
        veterinario_id,
        dia_semana,
        hora_inicio,
        hora_fim,
        ignorar_id=id,
    )

    if erro:
        return jsonify({"erro": erro}), status

    disponibilidade.veterinario_id = veterinario_id
    disponibilidade.dia_semana = normalizar_dia(dia_semana)
    disponibilidade.hora_inicio = normalizar_hora(hora_inicio)
    disponibilidade.hora_fim = normalizar_hora(hora_fim)

    if not salvar_alteracao():
        return jsonify({"erro": "Não foi possível atualizar a disponibilidade"}), 500

    return jsonify({
        "mensagem": "Disponibilidade atualizada com sucesso",
        "disponibilidade": disponibilidade_para_dict(disponibilidade),
    }), 200


@disponibilidade_bp.route("/disponibilidade/<int:id>", methods=["DELETE"])
def excluir_disponibilidade(id):
    disponibilidade = db.session.get(Disponibilidade, id)

    if disponibilidade is None:
        return jsonify({"erro": "Disponibilidade não encontrada"}), 404

    db.session.delete(disponibilidade)

    if not salvar_alteracao():
        return jsonify({"erro": "Não foi possível excluir a disponibilidade"}), 500

    return jsonify({
        "mensagem": "Disponibilidade excluída com sucesso"
    }), 200



@disponibilidade_bp.route("/disponibilidade/verificar", methods=["GET"])
def verificar_disponibilidade():
    veterinario_id = request.args.get("veterinario_id", type=int)
    data = request.args.get("data")
    hora = request.args.get("hora")

    if veterinario_id is None or not data or not hora:
        return jsonify({
            "erro": "veterinario_id, data e hora são obrigatórios"
        }), 400

    if veterinario_id <= 0:
        return jsonify({"erro": "veterinario_id deve ser positivo"}), 400

    try:
        data_consulta = datetime.strptime(data, "%Y-%m-%d")
        hora_consulta = datetime.strptime(hora, "%H:%M")
    except (ValueError, TypeError):
        return jsonify({
            "erro": "Data deve estar no formato AAAA-MM-DD e hora no formato HH:MM"
        }), 400

    # Duracao padrao de 30 minutos
    duracao_texto = request.args.get("duracao_minutos")

    if duracao_texto is None:
        duracao = DURACAO_PADRAO
    else:
        try:
            duracao = int(duracao_texto)
        except ValueError:
            return jsonify({
                "erro": "Duração inválida. Use 30, 45 ou 60 minutos"
            }), 400

    if not validar_duracao(duracao):
        return jsonify({
            "erro": "Duração inválida. Use 30, 45 ou 60 minutos"
        }), 400

    data_obj = data_consulta.date()
    hora_str = hora_consulta.strftime("%H:%M")

    # Verifica se toda a consulta cabe no expediente
    if not veterinario_disponivel(
        veterinario_id,
        data_obj,
        hora_str,
        duracao
    ):
        return jsonify({
            "disponivel": False,
            "mensagem": "Consulta fora do expediente disponível"
        }), 200

    # Verifica conflito com consultas existentes
    if existe_conflito_veterinario(
        veterinario_id,
        data_obj,
        hora_str,
        duracao
    ):
        return jsonify({
            "disponivel": False,
            "mensagem": "Veterinário já possui consulta neste horário"
        }), 200

    return jsonify({
        "disponivel": True,
        "mensagem": "Horário disponível"
    }), 200
