from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.consulta import Consulta
from models.disponibilidade import Disponibilidade
from models.pet import Pet
from models.veterinario import Veterinario


consultas_bp = Blueprint("consultas", __name__)

STATUS_PERMITIDOS = [
    "Agendada",
    "Remarcada",
    "Cancelada",
    "Realizada"
]

DIAS_SEMANA = [
    "segunda",
    "terca",
    "quarta",
    "quinta",
    "sexta",
    "sabado",
    "domingo"
]

DURACAO_PADRAO = 30
LIMITE_MOTIVO = 255

MSG_SEM_DISPONIBILIDADE = (
    "Veterinário não possui disponibilidade "
    "neste dia e horário"
)
MSG_CONFLITO_VET = (
    "Veterinário já possui consulta "
    "agendada neste horário"
)
MSG_CONFLITO_PET = (
    "Pet já possui consulta "
    "agendada neste horário"
)


# ----------------------------------------------------------
# Conversões e validações simples
# ----------------------------------------------------------

def inteiro_valido(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


def converter_data(texto):
    if not isinstance(texto, str) or not texto.strip():
        return None

    try:
        return date.fromisoformat(texto.strip())
    except (ValueError, TypeError):
        return None


def normalizar_hora(valor):
    if not isinstance(valor, str) or not valor.strip():
        return None

    try:
        return datetime.strptime(
            valor.strip(), "%H:%M"
        ).strftime("%H:%M")
    except (ValueError, TypeError):
        return None


def normalizar_status(valor):
    if not isinstance(valor, str) or not valor.strip():
        return None

    for status in STATUS_PERMITIDOS:
        if status.lower() == valor.strip().lower():
            return status

    return None


def validar_duracao(valor):
    """Retorna True se a duração é um inteiro permitido (30, 45 ou 60)."""
    return (
        inteiro_valido(valor)
        and valor in Consulta.DURACOES_PERMITIDAS
    )


def mensagem_duracao_invalida():
    permitidas = ", ".join(
        str(d) for d in Consulta.DURACOES_PERMITIDAS
    )
    return f"duracao_minutos inválida. Use: {permitidas}"


def validar_motivo(valor):
    """
    Retorna (motivo_limpo, erro).
    O motivo é opcional, mas se vier precisa ser texto
    com no máximo LIMITE_MOTIVO caracteres.
    """
    if valor is None:
        return None, None

    if not isinstance(valor, str):
        return None, "motivo deve ser um texto"

    limpo = valor.strip()

    if len(limpo) > LIMITE_MOTIVO:
        return None, (
            f"motivo deve ter no máximo {LIMITE_MOTIVO} caracteres"
        )

    return limpo, None


def hora_para_minutos(hora_str):
    horas, minutos = hora_str.split(":")
    return int(horas) * 60 + int(minutos)


def consulta_para_dict(consulta):
    return {
        "id": consulta.id,
        "pet_id": consulta.pet_id,
        "veterinario_id": consulta.veterinario_id,
        "data": (
            consulta.data.isoformat()
            if consulta.data else None
        ),
        "hora": consulta.hora,
        "duracao_minutos": consulta.duracao_minutos,
        "hora_fim": consulta.hora_fim,
        "motivo": consulta.motivo,
        "status": consulta.status
    }


def erro_banco(exc):
    """Desfaz a transação, registra o erro e devolve 500 em JSON."""
    db.session.rollback()
    current_app.logger.exception(
        "Erro de banco no módulo de consultas: %s", exc
    )
    return jsonify({
        "erro": "Erro interno ao acessar o banco de dados"
    }), 500


# ----------------------------------------------------------
# Regras de agenda (consideram o intervalo inteiro)
# ----------------------------------------------------------

def veterinario_disponivel(
    veterinario_id,
    data_consulta,
    hora_consulta,
    duracao_minutos=DURACAO_PADRAO
):
    """
    A consulta precisa começar e terminar dentro de UM mesmo
    período de disponibilidade do veterinário naquele dia.
    Consultas que passariam da meia-noite nunca cabem.
    """
    dia_semana = DIAS_SEMANA[data_consulta.weekday()]

    # Domingo é sempre dia de folga.
    if dia_semana == "domingo":
        return False

    inicio = hora_para_minutos(hora_consulta)
    fim = inicio + duracao_minutos

    if fim > 24 * 60:
        return False

    disponibilidades = Disponibilidade.query.filter_by(
        veterinario_id=veterinario_id,
        dia_semana=dia_semana
    ).all()

    for disponibilidade in disponibilidades:
        if (
            hora_para_minutos(disponibilidade.hora_inicio)
            <= inicio
            and fim
            <= hora_para_minutos(disponibilidade.hora_fim)
        ):
            return True

    return False


def _existe_sobreposicao(filtro_coluna, valor, data_obj,
                         hora_str, duracao_minutos, ignorar_id):
    inicio = hora_para_minutos(hora_str)
    fim = inicio + duracao_minutos

    query = Consulta.query.filter(
        filtro_coluna == valor,
        Consulta.data == data_obj,
        Consulta.status != "Cancelada"
    )

    if ignorar_id is not None:
        query = query.filter(Consulta.id != ignorar_id)

    for existente in query.all():
        ex_inicio = hora_para_minutos(existente.hora)
        ex_fim = ex_inicio + existente.duracao_minutos

        # Intervalos [inicio, fim) se sobrepõem quando
        # cada um começa antes de o outro terminar.
        if inicio < ex_fim and ex_inicio < fim:
            return True

    return False


def existe_conflito_veterinario(
    veterinario_id,
    data_obj,
    hora_str,
    duracao_minutos=DURACAO_PADRAO,
    ignorar_id=None
):
    return _existe_sobreposicao(
        Consulta.veterinario_id, veterinario_id,
        data_obj, hora_str, duracao_minutos, ignorar_id
    )


def existe_conflito_pet(
    pet_id,
    data_obj,
    hora_str,
    duracao_minutos=DURACAO_PADRAO,
    ignorar_id=None
):
    return _existe_sobreposicao(
        Consulta.pet_id, pet_id,
        data_obj, hora_str, duracao_minutos, ignorar_id
    )


def validar_agenda(
    veterinario_id,
    pet_id,
    data_obj,
    hora_str,
    duracao_minutos,
    ignorar_id=None
):
    """
    Aplica as três regras de agenda em ordem e devolve
    a mensagem do primeiro problema, ou None se estiver tudo certo.
    """
    if not veterinario_disponivel(
        veterinario_id, data_obj, hora_str, duracao_minutos
    ):
        return MSG_SEM_DISPONIBILIDADE

    if existe_conflito_veterinario(
        veterinario_id, data_obj, hora_str,
        duracao_minutos, ignorar_id
    ):
        return MSG_CONFLITO_VET

    if existe_conflito_pet(
        pet_id, data_obj, hora_str,
        duracao_minutos, ignorar_id
    ):
        return MSG_CONFLITO_PET

    return None


# ----------------------------------------------------------
# Rotas
# ----------------------------------------------------------

@consultas_bp.route("/consultas", methods=["POST"])
def cadastrar_consulta():
    dados = request.get_json(silent=True)

    if not dados or not isinstance(dados, dict):
        return jsonify({"erro": "Dados não enviados"}), 400

    pet_id = dados.get("pet_id")
    veterinario_id = dados.get("veterinario_id")
    data_str = dados.get("data")
    hora_str = dados.get("hora")

    if (
        pet_id is None
        or veterinario_id is None
        or not data_str
        or not hora_str
    ):
        return jsonify({
            "erro": (
                "pet_id, veterinario_id, data e hora "
                "são obrigatórios"
            )
        }), 400

    if (
        not inteiro_valido(pet_id)
        or not inteiro_valido(veterinario_id)
    ):
        return jsonify({
            "erro": (
                "pet_id e veterinario_id "
                "devem ser números inteiros"
            )
        }), 400

    duracao = dados.get("duracao_minutos", DURACAO_PADRAO)

    if not validar_duracao(duracao):
        return jsonify({"erro": mensagem_duracao_invalida()}), 400

    motivo, erro_motivo = validar_motivo(dados.get("motivo"))

    if erro_motivo:
        return jsonify({"erro": erro_motivo}), 400

    if not db.session.get(Pet, pet_id):
        return jsonify({"erro": "Pet não encontrado"}), 404

    if not db.session.get(Veterinario, veterinario_id):
        return jsonify({
            "erro": "Veterinário não encontrado"
        }), 404

    data_obj = converter_data(data_str)

    if data_obj is None:
        return jsonify({
            "erro": "Data inválida. Use o formato AAAA-MM-DD"
        }), 400

    hora_formatada = normalizar_hora(hora_str)

    if hora_formatada is None:
        return jsonify({
            "erro": "Hora inválida. Use o formato HH:MM"
        }), 400

    erro_agenda = validar_agenda(
        veterinario_id, pet_id, data_obj,
        hora_formatada, duracao
    )

    if erro_agenda:
        return jsonify({"erro": erro_agenda}), 409

    nova_consulta = Consulta(
        pet_id=pet_id,
        veterinario_id=veterinario_id,
        data=data_obj,
        hora=hora_formatada,
        duracao_minutos=duracao,
        motivo=motivo,
        status="Agendada"
    )

    try:
        db.session.add(nova_consulta)
        db.session.commit()
    except SQLAlchemyError as exc:
        return erro_banco(exc)

    return jsonify({
        "mensagem": "Consulta agendada com sucesso",
        "consulta": consulta_para_dict(nova_consulta)
    }), 201


@consultas_bp.route("/consultas", methods=["GET"])
def listar_consultas():
    pet_id = request.args.get("pet_id", type=int)
    veterinario_id = request.args.get(
        "veterinario_id", type=int
    )
    data_filtro = request.args.get("data")
    status_filtro = request.args.get("status")

    query = Consulta.query

    if pet_id is not None:
        query = query.filter_by(pet_id=pet_id)

    if veterinario_id is not None:
        query = query.filter_by(
            veterinario_id=veterinario_id
        )

    if data_filtro:
        data_obj = converter_data(data_filtro)

        if data_obj is None:
            return jsonify({
                "erro": "Data inválida. Use o formato AAAA-MM-DD"
            }), 400

        query = query.filter_by(data=data_obj)

    if status_filtro:
        query = query.filter(
            Consulta.status.ilike(status_filtro.strip())
        )

    consultas = query.order_by(
        Consulta.data, Consulta.hora, Consulta.id
    ).all()

    return jsonify([
        consulta_para_dict(c) for c in consultas
    ]), 200


@consultas_bp.route("/consultas/<int:id>", methods=["GET"])
def buscar_consulta(id):
    consulta = db.session.get(Consulta, id)

    if not consulta:
        return jsonify({
            "erro": "Consulta não encontrada"
        }), 404

    return jsonify(consulta_para_dict(consulta)), 200


@consultas_bp.route("/consultas/<int:id>", methods=["PUT"])
def atualizar_consulta(id):
    consulta = db.session.get(Consulta, id)

    if not consulta:
        return jsonify({
            "erro": "Consulta não encontrada"
        }), 404

    dados = request.get_json(silent=True)

    if not dados or not isinstance(dados, dict):
        return jsonify({"erro": "Dados não enviados"}), 400

    novo_pet_id = consulta.pet_id
    novo_vet_id = consulta.veterinario_id
    nova_data = consulta.data
    nova_hora = consulta.hora
    novo_status = consulta.status
    novo_motivo = consulta.motivo
    nova_duracao = consulta.duracao_minutos

    if "pet_id" in dados:
        if not inteiro_valido(dados["pet_id"]):
            return jsonify({
                "erro": "pet_id deve ser um número inteiro"
            }), 400

        if not db.session.get(Pet, dados["pet_id"]):
            return jsonify({"erro": "Pet não encontrado"}), 404

        novo_pet_id = dados["pet_id"]

    if "veterinario_id" in dados:
        if not inteiro_valido(dados["veterinario_id"]):
            return jsonify({
                "erro": (
                    "veterinario_id deve ser "
                    "um número inteiro"
                )
            }), 400

        if not db.session.get(
            Veterinario, dados["veterinario_id"]
        ):
            return jsonify({
                "erro": "Veterinário não encontrado"
            }), 404

        novo_vet_id = dados["veterinario_id"]

    if "data" in dados:
        data_convertida = converter_data(dados["data"])

        if data_convertida is None:
            return jsonify({
                "erro": "Data inválida. Use o formato AAAA-MM-DD"
            }), 400

        nova_data = data_convertida

    if "hora" in dados:
        hora_convertida = normalizar_hora(dados["hora"])

        if hora_convertida is None:
            return jsonify({
                "erro": "Hora inválida. Use o formato HH:MM"
            }), 400

        nova_hora = hora_convertida

    if "duracao_minutos" in dados:
        if not validar_duracao(dados["duracao_minutos"]):
            return jsonify({
                "erro": mensagem_duracao_invalida()
            }), 400

        nova_duracao = dados["duracao_minutos"]

    if "motivo" in dados:
        motivo_validado, erro_motivo = validar_motivo(
            dados["motivo"]
        )

        if erro_motivo:
            return jsonify({"erro": erro_motivo}), 400

        novo_motivo = motivo_validado

    if "status" in dados:
        status_validado = normalizar_status(dados["status"])

        if status_validado is None:
            return jsonify({
                "erro": (
                    "Status inválido. Use: "
                    f"{', '.join(STATUS_PERMITIDOS)}"
                )
            }), 400

        novo_status = status_validado

    if novo_status != "Cancelada":
        erro_agenda = validar_agenda(
            novo_vet_id, novo_pet_id, nova_data,
            nova_hora, nova_duracao, ignorar_id=id
        )

        if erro_agenda:
            return jsonify({"erro": erro_agenda}), 409

    consulta.pet_id = novo_pet_id
    consulta.veterinario_id = novo_vet_id
    consulta.data = nova_data
    consulta.hora = nova_hora
    consulta.duracao_minutos = nova_duracao
    consulta.motivo = novo_motivo
    consulta.status = novo_status

    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        return erro_banco(exc)

    return jsonify({
        "mensagem": "Consulta atualizada com sucesso",
        "consulta": consulta_para_dict(consulta)
    }), 200


@consultas_bp.route(
    "/consultas/<int:id>/remarcar",
    methods=["PUT", "PATCH"]
)
def remarcar_consulta(id):
    consulta = db.session.get(Consulta, id)

    if not consulta:
        return jsonify({
            "erro": "Consulta não encontrada"
        }), 404

    if consulta.status == "Cancelada":
        return jsonify({
            "erro": (
                "Não é possível remarcar "
                "uma consulta cancelada"
            )
        }), 400

    dados = request.get_json(silent=True)

    if not dados or not isinstance(dados, dict):
        return jsonify({"erro": "Dados não enviados"}), 400

    nova_data_str = dados.get("data")
    nova_hora_str = dados.get("hora")

    if not nova_data_str and not nova_hora_str:
        return jsonify({
            "erro": "Informe ao menos a data ou hora para remarcar"
        }), 400

    nova_data = consulta.data

    if nova_data_str is not None:
        data_convertida = converter_data(nova_data_str)

        if data_convertida is None:
            return jsonify({
                "erro": "Data inválida. Use o formato AAAA-MM-DD"
            }), 400

        nova_data = data_convertida

    nova_hora = consulta.hora

    if nova_hora_str is not None:
        hora_convertida = normalizar_hora(nova_hora_str)

        if hora_convertida is None:
            return jsonify({
                "erro": "Hora inválida. Use o formato HH:MM"
            }), 400

        nova_hora = hora_convertida

    # A duração é preservada e revalidada no novo horário.
    erro_agenda = validar_agenda(
        consulta.veterinario_id, consulta.pet_id,
        nova_data, nova_hora, consulta.duracao_minutos,
        ignorar_id=id
    )

    if erro_agenda:
        return jsonify({"erro": erro_agenda}), 409

    consulta.data = nova_data
    consulta.hora = nova_hora
    consulta.status = "Remarcada"

    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        return erro_banco(exc)

    return jsonify({
        "mensagem": "Consulta remarcada com sucesso",
        "consulta": consulta_para_dict(consulta)
    }), 200


@consultas_bp.route(
    "/consultas/<int:id>/cancelar",
    methods=["PUT", "PATCH", "POST"]
)
def cancelar_consulta(id):
    consulta = db.session.get(Consulta, id)

    if not consulta:
        return jsonify({
            "erro": "Consulta não encontrada"
        }), 404

    if consulta.status == "Cancelada":
        return jsonify({
            "erro": "Consulta já está cancelada"
        }), 400

    consulta.status = "Cancelada"

    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        return erro_banco(exc)

    return jsonify({
        "mensagem": "Consulta cancelada com sucesso",
        "consulta": consulta_para_dict(consulta)
    }), 200


@consultas_bp.route(
    "/consultas/<int:id>",
    methods=["DELETE"]
)
def excluir_consulta(id):
    consulta = db.session.get(Consulta, id)

    if not consulta:
        return jsonify({
            "erro": "Consulta não encontrada"
        }), 404

    try:
        db.session.delete(consulta)
        db.session.commit()
    except SQLAlchemyError as exc:
        return erro_banco(exc)

    return jsonify({
        "mensagem": "Consulta excluída com sucesso"
    }), 200