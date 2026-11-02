import pytest

from app import create_app
from extensions import db


# ==========================================================
# PREPARACAO DOS TESTES
# ==========================================================

@pytest.fixture
def client():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "chave-segura-exclusiva-para-testes-uniesp-2026",
    })

    with app.test_client() as cliente:
        yield cliente

    with app.app_context():
        db.session.remove()
        db.drop_all()


# ==========================================================
# FUNCOES AUXILIARES
# ==========================================================

def criar_veterinario(client):
    resposta = client.post("/veterinarios", json={
        "nome": "Dra. Laura",
        "especialidade": "Clinica geral",
    })

    assert resposta.status_code == 201

    return resposta.json["veterinario"]["id"]


def criar_tutor(client):
    resposta = client.post("/usuarios", json={
        "nome": "Tutor Teste",
        "email": "tutor@teste.com",
        "telefone": "83999999999",
        "senha": "senhaSegura123",
    })

    assert resposta.status_code == 201

    return resposta.json["usuario"]["id"]


def criar_pet(client, usuario_id):
    resposta = client.post("/pets", json={
        "nome": "Rex",
        "especie": "Cachorro",
        "raca": "Labrador",
        "sexo": "Macho",
        "data_nascimento": "2023-01-15",
        "usuario_id": usuario_id,
    })

    assert resposta.status_code == 201

    return resposta.json["pet"]["id"]


def criar_consulta(client, pet_id, veterinario_id):
    return client.post("/consultas", json={
        "pet_id": pet_id,
        "veterinario_id": veterinario_id,
        "data": "2026-11-10",
        "hora": "14:00",
        "motivo": "Consulta de rotina",
    })


def criar_disponibilidade(client, veterinario_id):
    return client.post("/disponibilidade", json={
        "veterinario_id": veterinario_id,
        "dia_semana": "segunda",
        "hora_inicio": "08:00",
        "hora_fim": "12:00",
    })


# ==========================================================
# POST - CADASTRAR VETERINARIO
# ==========================================================

def test_criar_veterinario_com_sucesso(client):
    resposta = client.post("/veterinarios", json={
        "nome": "Dra. Laura",
        "especialidade": "Clinica geral",
    })

    assert resposta.status_code == 201

    veterinario = resposta.json["veterinario"]

    assert veterinario["id"] is not None
    assert veterinario["nome"] == "Dra. Laura"
    assert veterinario["especialidade"] == "Clinica geral"
    assert "crmv" not in veterinario


def test_criar_veterinario_sem_dados_retorna_400(client):
    resposta = client.post("/veterinarios", json={})

    assert resposta.status_code == 400


def test_criar_veterinario_sem_nome_retorna_400(client):
    resposta = client.post("/veterinarios", json={
        "especialidade": "Clinica geral",
    })

    assert resposta.status_code == 400


def test_criar_veterinario_sem_especialidade_retorna_400(client):
    resposta = client.post("/veterinarios", json={
        "nome": "Dra. Laura",
    })

    assert resposta.status_code == 400


def test_criar_veterinario_com_campos_vazios_retorna_400(client):
    resposta = client.post("/veterinarios", json={
        "nome": "   ",
        "especialidade": "Clinica geral",
    })

    assert resposta.status_code == 400


def test_criar_veterinario_com_crmv_retorna_400(client):
    resposta = client.post("/veterinarios", json={
        "nome": "Dra. Laura",
        "especialidade": "Clinica geral",
        "crmv": "CRMV-PB 1234",
    })

    assert resposta.status_code == 400


# ==========================================================
# GET - LISTAR VETERINARIOS
# ==========================================================

def test_listar_veterinarios(client):
    criar_veterinario(client)

    resposta = client.get("/veterinarios")

    assert resposta.status_code == 200
    assert len(resposta.json) == 1
    assert resposta.json[0]["nome"] == "Dra. Laura"
    assert "crmv" not in resposta.json[0]


def test_listar_veterinarios_sem_cadastros(client):
    resposta = client.get("/veterinarios")

    assert resposta.status_code == 200
    assert resposta.json == []


# ==========================================================
# GET - BUSCAR POR ID
# ==========================================================

def test_buscar_veterinario_por_id(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.get(
        f"/veterinarios/{veterinario_id}"
    )

    assert resposta.status_code == 200
    assert resposta.json["id"] == veterinario_id
    assert resposta.json["nome"] == "Dra. Laura"


def test_buscar_veterinario_inexistente_retorna_404(client):
    resposta = client.get("/veterinarios/999")

    assert resposta.status_code == 404


# ==========================================================
# PUT - ATUALIZAR
# ==========================================================

def test_atualizar_veterinario(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={
            "nome": "Dra. Ana",
            "especialidade": "Cirurgia",
        }
    )

    assert resposta.status_code == 200
    assert resposta.json["veterinario"]["nome"] == "Dra. Ana"
    assert resposta.json["veterinario"]["especialidade"] == "Cirurgia"


def test_atualizar_apenas_nome(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={
            "nome": "Dra. Ana",
        }
    )

    assert resposta.status_code == 200
    assert resposta.json["veterinario"]["nome"] == "Dra. Ana"
    assert resposta.json["veterinario"]["especialidade"] == "Clinica geral"


def test_atualizar_veterinario_inexistente_retorna_404(client):
    resposta = client.put(
        "/veterinarios/999",
        json={"nome": "Dra. Ana"}
    )

    assert resposta.status_code == 404


def test_atualizar_sem_campos_retorna_400(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={}
    )

    assert resposta.status_code == 400


def test_atualizar_com_crmv_retorna_400(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={"crmv": "CRMV-PB 1234"}
    )

    assert resposta.status_code == 400


# ==========================================================
# DELETE - EXCLUIR
# ==========================================================

def test_excluir_veterinario_sem_vinculos(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.delete(
        f"/veterinarios/{veterinario_id}"
    )

    assert resposta.status_code == 200

    busca = client.get(
        f"/veterinarios/{veterinario_id}"
    )

    assert busca.status_code == 404


def test_excluir_veterinario_inexistente_retorna_404(client):
    resposta = client.delete("/veterinarios/999")

    assert resposta.status_code == 404


def test_impedir_exclusao_de_veterinario_com_consulta(client):
    veterinario_id = criar_veterinario(client)

    usuario_id = criar_tutor(client)
    pet_id = criar_pet(client, usuario_id)

    consulta = criar_consulta(
        client,
        pet_id,
        veterinario_id
    )

    assert consulta.status_code == 201

    resposta = client.delete(
        f"/veterinarios/{veterinario_id}"
    )

    assert resposta.status_code == 409


def test_impedir_exclusao_de_veterinario_com_disponibilidade(client):
    veterinario_id = criar_veterinario(client)

    disponibilidade = criar_disponibilidade(
        client,
        veterinario_id
    )

    assert disponibilidade.status_code == 201

    resposta = client.delete(
        f"/veterinarios/{veterinario_id}"
    )

    assert resposta.status_code == 409