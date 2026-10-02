from datetime import date

from flask import Blueprint, request, jsonify
from extensions import db
from models.pet import Pet
from models.usuario import Usuario


pets_bp = Blueprint("pets", __name__)


def converter_data(texto):
    """Converte o texto 'AAAA-MM-DD' em uma data. Se vier vazio, retorna None."""
    if not texto:
        return None
    return date.fromisoformat(texto)


def pet_para_dict(pet):
    """Transforma um objeto Pet em um dicionário para virar JSON."""
    return {
        "id": pet.id,
        "nome": pet.nome,
        "especie": pet.especie,
        "raca": pet.raca,
        "sexo": pet.sexo,
        "data_nascimento": pet.data_nascimento.isoformat() if pet.data_nascimento else None,
        "usuario_id": pet.usuario_id
    }


@pets_bp.route("/pets", methods=["POST"])
def cadastrar_pet():
    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Dados não enviados"
        }), 400

    nome = dados.get("nome")
    especie = dados.get("especie")
    raca = dados.get("raca")
    sexo = dados.get("sexo")
    usuario_id = dados.get("usuario_id")

    if not nome or not especie or not sexo or usuario_id is None:
        return jsonify({
            "erro": "Nome, espécie, sexo e usuario_id são obrigatórios"
        }), 400

    if not isinstance(usuario_id, int):
        return jsonify({
            "erro": "usuario_id deve ser um número inteiro"
        }), 400

    tutor = db.session.get(Usuario, usuario_id)

    if not tutor:
        return jsonify({
            "erro": "Tutor não encontrado"
        }), 404

    try:
        data_nascimento = converter_data(dados.get("data_nascimento"))
    except (ValueError, TypeError):
        return jsonify({
            "erro": "Data de nascimento inválida. Use o formato AAAA-MM-DD"
        }), 400

    novo_pet = Pet(
        nome=nome,
        especie=especie,
        raca=raca,
        sexo=sexo,
        data_nascimento=data_nascimento,
        usuario_id=usuario_id
    )

    db.session.add(novo_pet)
    db.session.commit()

    return jsonify({
        "mensagem": "Pet cadastrado com sucesso",
        "pet": pet_para_dict(novo_pet)
    }), 201


@pets_bp.route("/pets", methods=["GET"])
def listar_pets():
    usuario_id = request.args.get("usuario_id", type=int)

    if usuario_id is not None:
        pets = Pet.query.filter_by(usuario_id=usuario_id).all()
    else:
        pets = Pet.query.all()

    resultado = []

    for pet in pets:
        resultado.append(pet_para_dict(pet))

    return jsonify(resultado), 200


@pets_bp.route("/pets/<int:id>", methods=["GET"])
def buscar_pet(id):
    pet = db.session.get(Pet, id)

    if not pet:
        return jsonify({
            "erro": "Pet não encontrado"
        }), 404

    return jsonify(pet_para_dict(pet)), 200


@pets_bp.route("/pets/<int:id>", methods=["PUT"])
def atualizar_pet(id):
    pet = db.session.get(Pet, id)

    if not pet:
        return jsonify({
            "erro": "Pet não encontrado"
        }), 404

    dados = request.get_json()

    if not dados:
        return jsonify({
            "erro": "Dados não enviados"
        }), 400

    if "nome" in dados:
        if not dados["nome"]:
            return jsonify({"erro": "O nome não pode ficar vazio"}), 400
        pet.nome = dados["nome"]

    if "especie" in dados:
        if not dados["especie"]:
            return jsonify({"erro": "A espécie não pode ficar vazia"}), 400
        pet.especie = dados["especie"]

    if "sexo" in dados:
        if not dados["sexo"]:
            return jsonify({"erro": "O sexo não pode ficar vazio"}), 400
        pet.sexo = dados["sexo"]

    if "raca" in dados:
        pet.raca = dados["raca"]

    if "data_nascimento" in dados:
        try:
            pet.data_nascimento = converter_data(dados["data_nascimento"])
        except (ValueError, TypeError):
            return jsonify({
                "erro": "Data de nascimento inválida. Use o formato AAAA-MM-DD"
            }), 400

    if "usuario_id" in dados:
        novo_usuario_id = dados["usuario_id"]

        if not isinstance(novo_usuario_id, int):
            return jsonify({
                "erro": "usuario_id deve ser um número inteiro"
            }), 400

        if not db.session.get(Usuario, novo_usuario_id):
            return jsonify({
                "erro": "Tutor não encontrado"
            }), 404

        pet.usuario_id = novo_usuario_id

    db.session.commit()

    return jsonify({
        "mensagem": "Pet atualizado com sucesso",
        "pet": pet_para_dict(pet)
    }), 200


@pets_bp.route("/pets/<int:id>", methods=["DELETE"])
def excluir_pet(id):
    pet = db.session.get(Pet, id)

    if not pet:
        return jsonify({
            "erro": "Pet não encontrado"
        }), 404

    db.session.delete(pet)
    db.session.commit()

    return jsonify({
        "mensagem": "Pet excluído com sucesso"
    }), 200