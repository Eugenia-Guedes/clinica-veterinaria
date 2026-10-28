from datetime import date, datetime
from flask import Blueprint, jsonify, request
from extensions import db
from models.consulta import Consulta
from models.pet import Pet
from models.veterinario import Veterinario

consultas_bp = Blueprint("consultas", __name__)

STATUS_PERMITIDOS = ["Agendada", "Remarcada", "Cancelada", "Realizada"]


def inteiro_valido(valor):
    """True apenas para inteiros válidos (exclui bool)."""
    return isinstance(valor, int) and not isinstance(valor, bool)


def converter_data(texto):
    """Converte o texto 'AAAA-MM-DD' em um objeto date. Retorna None se vazio ou inválido."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    try:
        return date.fromisoformat(texto.strip())
    except (ValueError, TypeError):
        return None


def normalizar_hora(valor):
    """Converte '8:00' ou '08:00' em '08:00'. Se for inválida, devolve None."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    try:
        return datetime.strptime(valor.strip(), "%H:%M").strftime("%H:%M")
    except (ValueError, TypeError):
        return None


def normalizar_status(valor):
    """Normaliza status garantindo formato padronizado e valida contra permitidos."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    capitalizado = valor.strip().capitalize()
    for status in STATUS_PERMITIDOS:
        if status.lower() == capitalizado.lower():
            return status
    return None


def consulta_para_dict(consulta):
    """Transforma um objeto Consulta em dicionário para virar JSON."""
    return {
        "id": consulta.id,
        "pet_id": consulta.pet_id,
        "veterinario_id": consulta.veterinario_id,
        "data": consulta.data.isoformat() if consulta.data else None,
        "hora": consulta.hora,
        "motivo": consulta.motivo,
        "status": consulta.status,
    }


def existe_conflito_veterinario(veterinario_id, data_obj, hora_str, ignorar_id=None):
    """Verifica se o veterinário já tem consulta ativa no horário."""
    query = Consulta.query.filter(
        Consulta.veterinario_id == veterinario_id,
        Consulta.data == data_obj,
        Consulta.hora == hora_str,
        Consulta.status != "Cancelada",
    )
    if ignorar_id is not None:
        query = query.filter(Consulta.id != ignorar_id)
    return query.first() is not None


def existe_conflito_pet(pet_id, data_obj, hora_str, ignorar_id=None):
    """Verifica se o pet já tem consulta ativa no horário."""
    query = Consulta.query.filter(
        Consulta.pet_id == pet_id,
        Consulta.data == data_obj,
        Consulta.hora == hora_str,
        Consulta.status != "Cancelada",
    )
    if ignorar_id is not None:
        query = query.filter(Consulta.id != ignorar_id)
    return query.first() is not None


@consultas_bp.route("/consultas", methods=["POST"])
def cadastrar_consulta():
    dados = request.get_json()

    if not dados:
        return jsonify({"erro": "Dados não enviados"}), 400

    pet_id = dados.get("pet_id")
    veterinario_id = dados.get("veterinario_id")
    data_str = dados.get("data")
    hora_str = dados.get("hora")
    motivo = dados.get("motivo")

    if pet_id is None or veterinario_id is None or not data_str or not hora_str:
        return jsonify({
            "erro": "pet_id, veterinario_id, data e hora são obrigatórios"
        }), 400

    if not inteiro_valido(pet_id) or not inteiro_valido(veterinario_id):
        return jsonify({
            "erro": "pet_id e veterinario_id devem ser números inteiros"
        }), 400

    pet = db.session.get(Pet, pet_id)
    if not pet:
        return jsonify({"erro": "Pet não encontrado"}), 404

    veterinario = db.session.get(Veterinario, veterinario_id)
    if not veterinario:
        return jsonify({"erro": "Veterinário não encontrado"}), 404

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

    if existe_conflito_veterinario(veterinario_id, data_obj, hora_formatada):
        return jsonify({
            "erro": "Veterinário já possui consulta agendada neste horário"
        }), 409

    if existe_conflito_pet(pet_id, data_obj, hora_formatada):
        return jsonify({
            "erro": "Pet já possui consulta agendada neste horário"
        }), 409

    nova_consulta = Consulta(
        pet_id=pet_id,
        veterinario_id=veterinario_id,
        data=data_obj,
        hora=hora_formatada,
        motivo=motivo.strip() if isinstance(motivo, str) else motivo,
        status="Agendada",
    )

    db.session.add(nova_consulta)
    db.session.commit()

    return jsonify({
        "mensagem": "Consulta agendada com sucesso",
        "consulta": consulta_para_dict(nova_consulta),
    }), 201


@consultas_bp.route("/consultas", methods=["GET"])
def listar_consultas():
    pet_id = request.args.get("pet_id", type=int)
    veterinario_id = request.args.get("veterinario_id", type=int)
    data_filtro = request.args.get("data")
    status_filtro = request.args.get("status")

    query = Consulta.query

    if pet_id is not None:
        query = query.filter_by(pet_id=pet_id)

    if veterinario_id is not None:
        query = query.filter_by(veterinario_id=veterinario_id)

    if data_filtro:
        data_obj = converter_data(data_filtro)
        if data_obj:
            query = query.filter_by(data=data_obj)

    if status_filtro:
        query = query.filter(Consulta.status.ilike(status_filtro.strip()))

    consultas = query.all()

    resultado = [consulta_para_dict(c) for c in consultas]
    return jsonify(resultado), 200


@consultas_bp.route("/consultas/<int:id>", methods=["GET"])
def buscar_consulta(id):
    consulta = db.session.get(Consulta, id)

    if not consulta:
        return jsonify({"erro": "Consulta não encontrada"}), 404

    return jsonify(consulta_para_dict(consulta)), 200


@consultas_bp.route("/consultas/<int:id>", methods=["PUT"])
def atualizar_consulta(id):
    consulta = db.session.get(Consulta, id)

    if not consulta:
        return jsonify({"erro": "Consulta não encontrada"}), 404

    dados = request.get_json()

    if not dados:
        return jsonify({"erro": "Dados não enviados"}), 400

    novo_pet_id = consulta.pet_id
    novo_vet_id = consulta.veterinario_id
    nova_data = consulta.data
    nova_hora = consulta.hora
    novo_status = consulta.status
    novo_motivo = consulta.motivo

    if "pet_id" in dados:
        if not inteiro_valido(dados["pet_id"]):
            return jsonify({"erro": "pet_id deve ser um número inteiro"}), 400
        if not db.session.get(Pet, dados["pet_id"]):
            return jsonify({"erro": "Pet não encontrado"}), 404
        novo_pet_id = dados["pet_id"]

    if "veterinario_id" in dados:
        if not inteiro_valido(dados["veterinario_id"]):
            return jsonify({"erro": "veterinario_id deve ser um número inteiro"}), 400
        if not db.session.get(Veterinario, dados["veterinario_id"]):
            return jsonify({"erro": "Veterinário não encontrado"}), 404
        novo_vet_id = dados["veterinario_id"]

    if "data" in dados:
        data_convertida = converter_data(dados["data"])
        if data_convertida is None:
            return jsonify({"erro": "Data inválida. Use o formato AAAA-MM-DD"}), 400
        nova_data = data_convertida

    if "hora" in dados:
        hora_convertida = normalizar_hora(dados["hora"])
        if hora_convertida is None:
            return jsonify({"erro": "Hora inválida. Use o formato HH:MM"}), 400
        nova_hora = hora_convertida

    if "motivo" in dados:
        novo_motivo = dados["motivo"].strip() if isinstance(dados["motivo"], str) else dados["motivo"]

    if "status" in dados:
        status_validado = normalizar_status(dados["status"])
        if status_validado is None:
            return jsonify({
                "erro": f"Status inválido. Use: {', '.join(STATUS_PERMITIDOS)}"
            }), 400
        novo_status = status_validado

    # Se a consulta continuar ativa, verificar conflitos no novo horário/profissionais
    if novo_status != "Cancelada":
        if existe_conflito_veterinario(novo_vet_id, nova_data, nova_hora, ignorar_id=id):
            return jsonify({"erro": "Veterinário já possui consulta agendada neste horário"}), 409
        if existe_conflito_pet(novo_pet_id, nova_data, nova_hora, ignorar_id=id):
            return jsonify({"erro": "Pet já possui consulta agendada neste horário"}), 409

    consulta.pet_id = novo_pet_id
    consulta.veterinario_id = novo_vet_id
    consulta.data = nova_data
    consulta.hora = nova_hora
    consulta.motivo = novo_motivo
    consulta.status = novo_status

    db.session.commit()

    return jsonify({
        "mensagem": "Consulta atualizada com sucesso",
        "consulta": consulta_para_dict(consulta),
    }), 200


@consultas_bp.route("/consultas/<int:id>/remarcar", methods=["PUT", "PATCH"])
def remarcar_consulta(id):
    consulta = db.session.get(Consulta, id)

    if not consulta:
        return jsonify({"erro": "Consulta não encontrada"}), 404

    if consulta.status == "Cancelada":
        return jsonify({"erro": "Não é possível remarcar uma consulta cancelada"}), 400

    dados = request.get_json()

    if not dados:
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
            return jsonify({"erro": "Data inválida. Use o formato AAAA-MM-DD"}), 400
        nova_data = data_convertida

    nova_hora = consulta.hora
    if nova_hora_str is not None:
        hora_convertida = normalizar_hora(nova_hora_str)
        if hora_convertida is None:
            return jsonify({"erro": "Hora inválida. Use o formato HH:MM"}), 400
        nova_hora = hora_convertida

    if existe_conflito_veterinario(consulta.veterinario_id, nova_data, nova_hora, ignorar_id=id):
        return jsonify({"erro": "Veterinário já possui consulta agendada neste horário"}), 409

    if existe_conflito_pet(consulta.pet_id, nova_data, nova_hora, ignorar_id=id):
        return jsonify({"erro": "Pet já possui consulta agendada neste horário"}), 409

    consulta.data = nova_data
    consulta.hora = nova_hora
    consulta.status = "Remarcada"

    db.session.commit()

    return jsonify({
        "mensagem": "Consulta remarcada com sucesso",
        "consulta": consulta_para_dict(consulta),
    }), 200


@consultas_bp.route("/consultas/<int:id>/cancelar", methods=["PUT", "PATCH", "POST"])
def cancelar_consulta(id):
    consulta = db.session.get(Consulta, id)

    if not consulta:
        return jsonify({"erro": "Consulta não encontrada"}), 404

    if consulta.status == "Cancelada":
        return jsonify({"erro": "Consulta já está cancelada"}), 400

    consulta.status = "Cancelada"
    db.session.commit()

    return jsonify({
        "mensagem": "Consulta cancelada com sucesso",
        "consulta": consulta_para_dict(consulta),
    }), 200


@consultas_bp.route("/consultas/<int:id>", methods=["DELETE"])
def excluir_consulta(id):
    consulta = db.session.get(Consulta, id)

    if not consulta:
        return jsonify({"erro": "Consulta não encontrada"}), 404

    db.session.delete(consulta)
    db.session.commit()

    return jsonify({"mensagem": "Consulta excluída com sucesso"}), 200
