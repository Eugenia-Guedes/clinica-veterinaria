import pytest

from app import create_app
from extensions import db


# ---------- PREPARAÇÃO ----------

@pytest.fixture
def client():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "chave-segura-exclusiva-para-testes-uniesp-2026",
    })
    with app.test_client() as client:
        yield client
    with app.app_context():
        db.session.remove()
        db.drop_all()


def criar_veterinario(client, crmv="CRMV-PB 1234"):
    """Cadastra um veterinário válido e devolve o id dele."""
    resposta = client.post("/veterinarios", json={
        "nome": "Dra. Laura",
        "crmv": crmv,
        "especialidade": "Clínica geral",
    })
    assert resposta.status_code == 201
    return resposta.json["veterinario"]["id"]


def criar_disponibilidade(client, veterinario_id, **campos):
    """Cadastra uma disponibilidade com dados padrão. Qualquer campo pode ser trocado."""
    dados = {
        "veterinario_id": veterinario_id,
        "dia_semana": "segunda",
        "hora_inicio": "08:00",
        "hora_fim": "12:00",
    }
    dados.update(campos)
    return client.post("/disponibilidade", json=dados)


# ---------- POST /disponibilidade ----------

def test_criar_disponibilidade_com_sucesso(client):
    vet_id = criar_veterinario(client)

    resposta = criar_disponibilidade(client, vet_id)

    assert resposta.status_code == 201
    item = resposta.json["disponibilidade"]
    assert item["id"] is not None
    assert item["veterinario_id"] == vet_id
    assert item["dia_semana"] == "segunda"
    assert item["hora_inicio"] == "08:00"
    assert item["hora_fim"] == "12:00"


def test_criar_normaliza_dia_com_acento_e_hora_sem_zero(client):
    vet_id = criar_veterinario(client)

    resposta = criar_disponibilidade(
        client, vet_id, dia_semana="Terça", hora_inicio="8:00", hora_fim="12:00"
    )

    assert resposta.status_code == 201
    assert resposta.json["disponibilidade"]["dia_semana"] == "terca"
    assert resposta.json["disponibilidade"]["hora_inicio"] == "08:00"


def test_criar_sem_dados_retorna_400(client):
    resposta = client.post("/disponibilidade", json={})

    assert resposta.status_code == 400


def test_criar_com_campo_obrigatorio_faltando_retorna_400(client):
    vet_id = criar_veterinario(client)

    resposta = client.post("/disponibilidade", json={
        "veterinario_id": vet_id,
        "dia_semana": "segunda",
        "hora_inicio": "08:00",
    })

    assert resposta.status_code == 400


def test_criar_com_veterinario_id_em_texto_retorna_400(client):
    resposta = criar_disponibilidade(client, "Laura")

    assert resposta.status_code == 400


def test_criar_com_dia_invalido_retorna_400(client):
    vet_id = criar_veterinario(client)

    resposta = criar_disponibilidade(client, vet_id, dia_semana="feriado")

    assert resposta.status_code == 400


def test_criar_com_hora_invalida_retorna_400(client):
    vet_id = criar_veterinario(client)

    resposta = criar_disponibilidade(client, vet_id, hora_inicio="25:00")

    assert resposta.status_code == 400


def test_criar_com_inicio_depois_do_fim_retorna_400(client):
    vet_id = criar_veterinario(client)

    resposta = criar_disponibilidade(
        client, vet_id, hora_inicio="14:00", hora_fim="10:00"
    )

    assert resposta.status_code == 400


def test_criar_para_veterinario_inexistente_retorna_404(client):
    resposta = criar_disponibilidade(client, 999)

    assert resposta.status_code == 404


def test_criar_duplicada_no_mesmo_dia_retorna_409(client):
    vet_id = criar_veterinario(client)
    criar_disponibilidade(client, vet_id)

    resposta = criar_disponibilidade(client, vet_id)

    assert resposta.status_code == 409


def test_mesmo_dia_para_veterinarios_diferentes_e_permitido(client):
    vet1 = criar_veterinario(client, crmv="CRMV-PB 1111")
    vet2 = criar_veterinario(client, crmv="CRMV-PB 2222")

    assert criar_disponibilidade(client, vet1).status_code == 201
    assert criar_disponibilidade(client, vet2).status_code == 201


# ---------- GET /disponibilidade ----------

def test_listar_disponibilidades(client):
    vet_id = criar_veterinario(client)
    criar_disponibilidade(client, vet_id, dia_semana="segunda")
    criar_disponibilidade(client, vet_id, dia_semana="terca")

    resposta = client.get("/disponibilidade")

    assert resposta.status_code == 200
    assert len(resposta.json) == 2


def test_listar_filtrando_por_veterinario(client):
    vet1 = criar_veterinario(client, crmv="CRMV-PB 1111")
    vet2 = criar_veterinario(client, crmv="CRMV-PB 2222")
    criar_disponibilidade(client, vet1)
    criar_disponibilidade(client, vet2)

    resposta = client.get(f"/disponibilidade?veterinario_id={vet1}")

    assert resposta.status_code == 200
    assert len(resposta.json) == 1
    assert resposta.json[0]["veterinario_id"] == vet1


def test_buscar_por_id(client):
    vet_id = criar_veterinario(client)
    id_ = criar_disponibilidade(client, vet_id).json["disponibilidade"]["id"]

    resposta = client.get(f"/disponibilidade/{id_}")

    assert resposta.status_code == 200
    assert resposta.json["id"] == id_


def test_buscar_id_inexistente_retorna_404(client):
    resposta = client.get("/disponibilidade/999")

    assert resposta.status_code == 404


# ---------- PUT /disponibilidade/<id> ----------

def test_atualizar_horario(client):
    vet_id = criar_veterinario(client)
    id_ = criar_disponibilidade(client, vet_id).json["disponibilidade"]["id"]

    resposta = client.put(f"/disponibilidade/{id_}", json={"hora_fim": "18:00"})

    assert resposta.status_code == 200
    assert resposta.json["disponibilidade"]["hora_fim"] == "18:00"
    assert resposta.json["disponibilidade"]["hora_inicio"] == "08:00"


def test_atualizar_com_horario_invalido_retorna_400(client):
    vet_id = criar_veterinario(client)
    id_ = criar_disponibilidade(client, vet_id).json["disponibilidade"]["id"]

    resposta = client.put(f"/disponibilidade/{id_}", json={"hora_fim": "07:00"})

    assert resposta.status_code == 400


def test_atualizar_para_dia_ja_ocupado_retorna_409(client):
    vet_id = criar_veterinario(client)
    criar_disponibilidade(client, vet_id, dia_semana="segunda")
    id_terca = criar_disponibilidade(
        client, vet_id, dia_semana="terca"
    ).json["disponibilidade"]["id"]

    resposta = client.put(
        f"/disponibilidade/{id_terca}", json={"dia_semana": "segunda"}
    )

    assert resposta.status_code == 409


def test_atualizar_para_veterinario_inexistente_retorna_404(client):
    vet_id = criar_veterinario(client)
    id_ = criar_disponibilidade(client, vet_id).json["disponibilidade"]["id"]

    resposta = client.put(f"/disponibilidade/{id_}", json={"veterinario_id": 999})

    assert resposta.status_code == 404


def test_atualizar_id_inexistente_retorna_404(client):
    resposta = client.put("/disponibilidade/999", json={"hora_fim": "18:00"})

    assert resposta.status_code == 404


# ---------- DELETE /disponibilidade/<id> ----------

def test_excluir_disponibilidade(client):
    vet_id = criar_veterinario(client)
    id_ = criar_disponibilidade(client, vet_id).json["disponibilidade"]["id"]

    resposta = client.delete(f"/disponibilidade/{id_}")

    assert resposta.status_code == 200
    assert client.get(f"/disponibilidade/{id_}").status_code == 404


def test_excluir_id_inexistente_retorna_404(client):
    resposta = client.delete("/disponibilidade/999")

    assert resposta.status_code == 404


# ---------- GET /disponibilidade/verificar ----------
# 2026-10-26 cai numa segunda-feira.

def test_verificar_horario_disponivel(client):
    vet_id = criar_veterinario(client)
    criar_disponibilidade(client, vet_id, dia_semana="segunda")

    resposta = client.get(
        f"/disponibilidade/verificar?veterinario_id={vet_id}"
        "&data=2026-10-26&hora=09:00"
    )

    assert resposta.status_code == 200
    assert resposta.json["disponivel"] is True


def test_verificar_horario_fora_do_expediente(client):
    vet_id = criar_veterinario(client)
    criar_disponibilidade(client, vet_id, dia_semana="segunda")

    resposta = client.get(
        f"/disponibilidade/verificar?veterinario_id={vet_id}"
        "&data=2026-10-26&hora=15:00"
    )

    assert resposta.status_code == 200
    assert resposta.json["disponivel"] is False


def test_verificar_hora_final_nao_conta_como_disponivel(client):
    vet_id = criar_veterinario(client)
    criar_disponibilidade(client, vet_id, dia_semana="segunda")

    resposta = client.get(
        f"/disponibilidade/verificar?veterinario_id={vet_id}"
        "&data=2026-10-26&hora=12:00"
    )

    assert resposta.json["disponivel"] is False


def test_verificar_dia_sem_disponibilidade(client):
    vet_id = criar_veterinario(client)
    criar_disponibilidade(client, vet_id, dia_semana="segunda")

    resposta = client.get(
        f"/disponibilidade/verificar?veterinario_id={vet_id}"
        "&data=2026-10-27&hora=09:00"
    )

    assert resposta.status_code == 200
    assert resposta.json["disponivel"] is False


def test_verificar_sem_parametros_retorna_400(client):
    resposta = client.get("/disponibilidade/verificar")

    assert resposta.status_code == 400


def test_verificar_com_formato_invalido_retorna_400(client):
    resposta = client.get(
        "/disponibilidade/verificar?veterinario_id=1&data=26/10/2026&hora=09:00"
    )

    assert resposta.status_code == 400
