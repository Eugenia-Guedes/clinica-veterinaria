import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.disponibilidade import Disponibilidade


# Os testes abaixo complementam tests/test_veterinarios.py.
# A fixture "client" (e "app") vem de tests/conftest.py.

LIMITE_NOME = 100
LIMITE_ESPECIALIDADE = 60


# ---------- FUNÇÕES AUXILIARES ----------

def criar_veterinario(client):
    """Cadastra um veterinário e retorna seu ID."""
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": "Dra. Laura",
            "especialidade": "Clínica geral",
        },
    )

    assert resposta.status_code == 201, resposta.get_json()

    return resposta.json["veterinario"]["id"]


# ---------- CADASTRO: TAMANHO DOS CAMPOS ----------

def test_criar_veterinario_nome_acima_do_limite_retorna_400(client):
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": "a" * (LIMITE_NOME + 1),
            "especialidade": "Clínica geral",
        },
    )

    assert resposta.status_code == 400
    assert "nome" in resposta.json["erro"]


def test_criar_veterinario_especialidade_acima_do_limite_retorna_400(client):
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": "Dra. Laura",
            "especialidade": "a" * (LIMITE_ESPECIALIDADE + 1),
        },
    )

    assert resposta.status_code == 400
    assert "especialidade" in resposta.json["erro"]


def test_criar_veterinario_com_campos_no_limite_exato(client):
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": "a" * LIMITE_NOME,
            "especialidade": "b" * LIMITE_ESPECIALIDADE,
        },
    )

    assert resposta.status_code == 201


# ---------- CADASTRO: DADOS INVÁLIDOS ----------

@pytest.mark.parametrize("valor_invalido", [123, None, ["Dra. Laura"], True])
def test_criar_veterinario_nome_com_tipo_invalido_retorna_400(
    client, valor_invalido
):
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": valor_invalido,
            "especialidade": "Clínica geral",
        },
    )

    assert resposta.status_code == 400


@pytest.mark.parametrize("valor_invalido", [123, None, ["Cirurgia"], True])
def test_criar_veterinario_especialidade_com_tipo_invalido_retorna_400(
    client, valor_invalido
):
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": "Dra. Laura",
            "especialidade": valor_invalido,
        },
    )

    assert resposta.status_code == 400


def test_criar_veterinario_sem_corpo_json_retorna_400(client):
    resposta = client.post(
        "/veterinarios",
        data="isto nao e json",
        content_type="text/plain",
    )

    assert resposta.status_code == 400


def test_criar_veterinario_com_json_que_nao_e_objeto_retorna_400(client):
    resposta = client.post("/veterinarios", json=["Dra. Laura"])

    assert resposta.status_code == 400


def test_criar_veterinario_remove_espacos_das_pontas(client):
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": "  Dra. Laura  ",
            "especialidade": "  Clínica geral ",
        },
    )

    assert resposta.status_code == 201
    assert resposta.json["veterinario"]["nome"] == "Dra. Laura"
    assert resposta.json["veterinario"]["especialidade"] == "Clínica geral"


# ---------- ATUALIZAÇÃO: DADOS INVÁLIDOS ----------

def test_atualizar_nome_acima_do_limite_retorna_400(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={"nome": "a" * (LIMITE_NOME + 1)},
    )

    assert resposta.status_code == 400


def test_atualizar_com_tipo_invalido_retorna_400(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={"nome": 123},
    )

    assert resposta.status_code == 400


def test_atualizacao_invalida_preserva_os_dados(client):
    veterinario_id = criar_veterinario(client)

    client.put(
        f"/veterinarios/{veterinario_id}",
        json={
            "nome": "Dra. Ana",
            "especialidade": "a" * (LIMITE_ESPECIALIDADE + 1),
        },
    )

    resposta = client.get(f"/veterinarios/{veterinario_id}")

    assert resposta.json["nome"] == "Dra. Laura"
    assert resposta.json["especialidade"] == "Clínica geral"


# ---------- IDENTIFICADOR INVÁLIDO ----------

def test_buscar_id_nao_numerico_retorna_404(client):
    resposta = client.get("/veterinarios/abc")

    assert resposta.status_code == 404


# ---------- EXCLUSÃO E INTEGRIDADE ----------

def test_excluir_veterinario_somente_apos_remover_disponibilidade(client, app):
    veterinario_id = criar_veterinario(client)

    # A disponibilidade é criada direto no banco para que ela seja
    # a única causa do bloqueio, sem depender das regras de consultas.
    with app.app_context():
        disponibilidade = Disponibilidade(
            veterinario_id=veterinario_id,
            dia_semana="segunda",
            hora_inicio="08:00",
            hora_fim="12:00",
        )
        db.session.add(disponibilidade)
        db.session.commit()
        disponibilidade_id = disponibilidade.id

    bloqueada = client.delete(f"/veterinarios/{veterinario_id}")

    assert bloqueada.status_code == 409

    with app.app_context():
        db.session.delete(db.session.get(Disponibilidade, disponibilidade_id))
        db.session.commit()

    liberada = client.delete(f"/veterinarios/{veterinario_id}")

    assert liberada.status_code == 200


def test_excluir_com_conflito_de_integridade_retorna_409(client, monkeypatch):
    veterinario_id = criar_veterinario(client)

    def commit_com_conflito():
        raise IntegrityError("DELETE", {}, Exception("FOREIGN KEY failed"))

    # Simula a chave estrangeira barrando a exclusão no commit.
    monkeypatch.setattr(db.session, "commit", commit_com_conflito)

    resposta = client.delete(f"/veterinarios/{veterinario_id}")

    assert resposta.status_code == 409
