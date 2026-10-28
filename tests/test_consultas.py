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


SENHA = "senhaSegura123"


def criar_tutor(client, email="tutor@teste.com"):
    """Cadastra um tutor e devolve seu id."""
    resposta = client.post("/usuarios", json={
        "nome": "Tutor Teste",
        "email": email,
        "telefone": "83999999999",
        "senha": SENHA,
    })
    assert resposta.status_code == 201
    return resposta.json["usuario"]["id"]


def criar_pet(client, usuario_id, nome="Rex", **campos):
    """Cadastra um pet e devolve seu id."""
    dados = {
        "nome": nome,
        "especie": "Cachorro",
        "raca": "Labrador",
        "sexo": "Macho",
        "data_nascimento": "2023-01-15",
        "usuario_id": usuario_id,
    }
    dados.update(campos)
    resposta = client.post("/pets", json=dados)
    assert resposta.status_code == 201
    return resposta.json["pet"]["id"]


def criar_veterinario(client, crmv="CRMV-PB 1234", nome="Dra. Laura", especialidade="Clínica Geral"):
    """Cadastra um veterinário e devolve seu id."""
    resposta = client.post("/veterinarios", json={
        "nome": nome,
        "crmv": crmv,
        "especialidade": especialidade,
    })
    assert resposta.status_code == 201
    return resposta.json["veterinario"]["id"]


def criar_consulta(client, pet_id, veterinario_id, **campos):
    """Cadastra uma consulta com dados padrão. Qualquer campo pode ser sobrescrito."""
    dados = {
        "pet_id": pet_id,
        "veterinario_id": veterinario_id,
        "data": "2026-11-10",
        "hora": "14:00",
        "motivo": "Consulta de rotina",
    }
    dados.update(campos)
    return client.post("/consultas", json=dados)


# ---------- POST /consultas (CRIAR) ----------

def test_criar_consulta_com_sucesso(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)

    resposta = criar_consulta(client, pet_id, vet_id)

    assert resposta.status_code == 201
    consulta = resposta.json["consulta"]
    assert consulta["id"] is not None
    assert consulta["pet_id"] == pet_id
    assert consulta["veterinario_id"] == vet_id
    assert consulta["data"] == "2026-11-10"
    assert consulta["hora"] == "14:00"
    assert consulta["motivo"] == "Consulta de rotina"
    assert consulta["status"] == "Agendada"


def test_criar_consulta_sem_motivo(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)

    resposta = client.post("/consultas", json={
        "pet_id": pet_id,
        "veterinario_id": vet_id,
        "data": "2026-11-10",
        "hora": "14:00",
    })

    assert resposta.status_code == 201
    assert resposta.json["consulta"]["motivo"] is None
    assert resposta.json["consulta"]["status"] == "Agendada"


def test_criar_consulta_normaliza_hora_sem_zero(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)

    resposta = criar_consulta(client, pet_id, vet_id, hora="9:30")

    assert resposta.status_code == 201
    assert resposta.json["consulta"]["hora"] == "09:30"


def test_criar_consulta_sem_dados_retorna_400(client):
    assert client.post("/consultas", json={}).status_code == 400


def test_criar_consulta_sem_campos_obrigatorios_retorna_400(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)

    resposta = client.post("/consultas", json={"pet_id": pet_id})
    assert resposta.status_code == 400
    assert "erro" in resposta.json


def test_criar_consulta_com_ids_invalidos_retorna_400(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)

    assert client.post("/consultas", json={
        "pet_id": "abc",
        "veterinario_id": 1,
        "data": "2026-11-10",
        "hora": "14:00"
    }).status_code == 400

    assert client.post("/consultas", json={
        "pet_id": pet_id,
        "veterinario_id": True,
        "data": "2026-11-10",
        "hora": "14:00"
    }).status_code == 400


def test_criar_consulta_com_pet_inexistente_retorna_404(client):
    vet_id = criar_veterinario(client)

    resposta = criar_consulta(client, pet_id=999, veterinario_id=vet_id)
    assert resposta.status_code == 404
    assert resposta.json["erro"] == "Pet não encontrado"


def test_criar_consulta_com_veterinario_inexistente_retorna_404(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)

    resposta = criar_consulta(client, pet_id=pet_id, veterinario_id=999)
    assert resposta.status_code == 404
    assert resposta.json["erro"] == "Veterinário não encontrado"


def test_criar_consulta_com_data_invalida_retorna_400(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)

    resposta = criar_consulta(client, pet_id, vet_id, data="10/11/2026")
    assert resposta.status_code == 400
    assert "Data inválida" in resposta.json["erro"]


def test_criar_consulta_com_hora_invalida_retorna_400(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)

    resposta = criar_consulta(client, pet_id, vet_id, hora="25:00")
    assert resposta.status_code == 400
    assert "Hora inválida" in resposta.json["erro"]


def test_conflito_horario_mesmo_veterinario_retorna_409(client):
    tutor_id = criar_tutor(client)
    pet1 = criar_pet(client, tutor_id, nome="Rex")
    pet2 = criar_pet(client, tutor_id, nome="Mia", especie="Gato")
    vet_id = criar_veterinario(client)

    r1 = criar_consulta(client, pet1, vet_id, data="2026-11-10", hora="14:00")
    assert r1.status_code == 201

    r2 = criar_consulta(client, pet2, vet_id, data="2026-11-10", hora="14:00")
    assert r2.status_code == 409
    assert "Veterinário já possui consulta agendada" in r2.json["erro"]


def test_conflito_horario_mesmo_pet_retorna_409(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet1 = criar_veterinario(client, crmv="CRMV-PB 1111", nome="Dra. Laura")
    vet2 = criar_veterinario(client, crmv="CRMV-PB 2222", nome="Dr. Carlos")

    r1 = criar_consulta(client, pet_id, vet1, data="2026-11-10", hora="14:00")
    assert r1.status_code == 201

    r2 = criar_consulta(client, pet_id, vet2, data="2026-11-10", hora="14:00")
    assert r2.status_code == 409
    assert "Pet já possui consulta agendada" in r2.json["erro"]


def test_permitir_mesmo_horario_para_veterinarios_distintos(client):
    tutor_id = criar_tutor(client)
    pet1 = criar_pet(client, tutor_id, nome="Rex")
    pet2 = criar_pet(client, tutor_id, nome="Mia", especie="Gato")
    vet1 = criar_veterinario(client, crmv="CRMV-PB 1111", nome="Dra. Laura")
    vet2 = criar_veterinario(client, crmv="CRMV-PB 2222", nome="Dr. Carlos")

    r1 = criar_consulta(client, pet1, vet1, data="2026-11-10", hora="14:00")
    r2 = criar_consulta(client, pet2, vet2, data="2026-11-10", hora="14:00")

    assert r1.status_code == 201
    assert r2.status_code == 201


# ---------- GET /consultas (CONSULTAR / LISTAR) ----------

def test_listar_consultas_e_filtros(client):
    tutor_id = criar_tutor(client)
    pet1 = criar_pet(client, tutor_id, nome="Rex")
    pet2 = criar_pet(client, tutor_id, nome="Mia", especie="Gato")
    vet1 = criar_veterinario(client, crmv="CRMV-PB 1111")
    vet2 = criar_veterinario(client, crmv="CRMV-PB 2222", nome="Dr. Carlos")

    criar_consulta(client, pet1, vet1, data="2026-11-10", hora="10:00")
    criar_consulta(client, pet1, vet2, data="2026-11-11", hora="11:00")
    criar_consulta(client, pet2, vet2, data="2026-11-12", hora="15:00")

    todas = client.get("/consultas")
    assert todas.status_code == 200
    assert len(todas.json) == 3

    do_pet1 = client.get(f"/consultas?pet_id={pet1}")
    assert do_pet1.status_code == 200
    assert len(do_pet1.json) == 2

    do_vet2 = client.get(f"/consultas?veterinario_id={vet2}")
    assert do_vet2.status_code == 200
    assert len(do_vet2.json) == 2

    por_data = client.get("/consultas?data=2026-11-10")
    assert por_data.status_code == 200
    assert len(por_data.json) == 1
    assert por_data.json[0]["pet_id"] == pet1


def test_buscar_consulta_por_id(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    consulta_id = criar_consulta(client, pet_id, vet_id).json["consulta"]["id"]

    resposta = client.get(f"/consultas/{consulta_id}")

    assert resposta.status_code == 200
    assert resposta.json["id"] == consulta_id
    assert resposta.json["pet_id"] == pet_id
    assert resposta.json["veterinario_id"] == vet_id


def test_buscar_consulta_inexistente_retorna_404(client):
    assert client.get("/consultas/999").status_code == 404


# ---------- REMARCAR CONSULTAS ----------

def test_remarcar_consulta_com_sucesso(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    consulta_id = criar_consulta(client, pet_id, vet_id, data="2026-11-10", hora="14:00").json["consulta"]["id"]

    resposta = client.patch(f"/consultas/{consulta_id}/remarcar", json={
        "data": "2026-11-12",
        "hora": "16:00",
    })

    assert resposta.status_code == 200
    consulta = resposta.json["consulta"]
    assert consulta["data"] == "2026-11-12"
    assert consulta["hora"] == "16:00"
    assert consulta["status"] == "Remarcada"


def test_remarcar_apenas_hora(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    consulta_id = criar_consulta(client, pet_id, vet_id, data="2026-11-10", hora="14:00").json["consulta"]["id"]

    resposta = client.put(f"/consultas/{consulta_id}/remarcar", json={"hora": "15:30"})

    assert resposta.status_code == 200
    consulta = resposta.json["consulta"]
    assert consulta["data"] == "2026-11-10"
    assert consulta["hora"] == "15:30"
    assert consulta["status"] == "Remarcada"


def test_remarcar_consulta_inexistente_retorna_404(client):
    resposta = client.patch("/consultas/999/remarcar", json={"hora": "15:00"})
    assert resposta.status_code == 404


def test_remarcar_sem_campos_retorna_400(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    consulta_id = criar_consulta(client, pet_id, vet_id).json["consulta"]["id"]

    assert client.patch(f"/consultas/{consulta_id}/remarcar", json={}).status_code == 400


def test_remarcar_para_horario_com_conflito_retorna_409(client):
    tutor_id = criar_tutor(client)
    pet1 = criar_pet(client, tutor_id, nome="Rex")
    pet2 = criar_pet(client, tutor_id, nome="Mia", especie="Gato")
    vet_id = criar_veterinario(client)

    c1 = criar_consulta(client, pet1, vet_id, data="2026-11-10", hora="14:00").json["consulta"]["id"]
    criar_consulta(client, pet2, vet_id, data="2026-11-10", hora="15:00")

    # Tenta remarcar c1 para as 15:00 onde já existe consulta com o mesmo vet
    resposta = client.patch(f"/consultas/{c1}/remarcar", json={"hora": "15:00"})
    assert resposta.status_code == 409


def test_remarcar_consulta_ja_cancelada_retorna_400(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    c_id = criar_consulta(client, pet_id, vet_id).json["consulta"]["id"]

    client.patch(f"/consultas/{c_id}/cancelar")

    resposta = client.patch(f"/consultas/{c_id}/remarcar", json={"hora": "17:00"})
    assert resposta.status_code == 400
    assert "Não é possível remarcar uma consulta cancelada" in resposta.json["erro"]


# ---------- CANCELAR CONSULTAS ----------

def test_cancelar_consulta_com_sucesso(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    c_id = criar_consulta(client, pet_id, vet_id).json["consulta"]["id"]

    resposta = client.patch(f"/consultas/{c_id}/cancelar")

    assert resposta.status_code == 200
    assert resposta.json["consulta"]["status"] == "Cancelada"

    # Confere no GET que o status está Cancelada
    busca = client.get(f"/consultas/{c_id}")
    assert busca.json["status"] == "Cancelada"


def test_cancelar_consulta_duas_vezes_retorna_400(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    c_id = criar_consulta(client, pet_id, vet_id).json["consulta"]["id"]

    assert client.patch(f"/consultas/{c_id}/cancelar").status_code == 200
    assert client.patch(f"/consultas/{c_id}/cancelar").status_code == 400


def test_cancelar_consulta_inexistente_retorna_404(client):
    assert client.patch("/consultas/999/cancelar").status_code == 404


def test_horario_de_consulta_cancelada_pode_ser_reutilizado(client):
    tutor_id = criar_tutor(client)
    pet1 = criar_pet(client, tutor_id, nome="Rex")
    pet2 = criar_pet(client, tutor_id, nome="Mia", especie="Gato")
    vet_id = criar_veterinario(client)

    c1 = criar_consulta(client, pet1, vet_id, data="2026-11-10", hora="14:00").json["consulta"]["id"]

    # Cancela c1
    client.patch(f"/consultas/{c1}/cancelar")

    # Agora pet2 pode agendar no mesmo dia e horário com o mesmo veterinário!
    r2 = criar_consulta(client, pet2, vet_id, data="2026-11-10", hora="14:00")
    assert r2.status_code == 201


# ---------- PUT /consultas/<id> (ATUALIZAR GERAL) ----------

def test_atualizar_consulta_geral(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    c_id = criar_consulta(client, pet_id, vet_id).json["consulta"]["id"]

    resposta = client.put(f"/consultas/{c_id}", json={
        "motivo": "Exame de sangue e check-up",
        "status": "Realizada"
    })

    assert resposta.status_code == 200
    assert resposta.json["consulta"]["motivo"] == "Exame de sangue e check-up"
    assert resposta.json["consulta"]["status"] == "Realizada"


def test_atualizar_com_status_invalido_retorna_400(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    c_id = criar_consulta(client, pet_id, vet_id).json["consulta"]["id"]

    resposta = client.put(f"/consultas/{c_id}", json={"status": "Invalido"})
    assert resposta.status_code == 400


# ---------- DELETE /consultas/<id> (EXCLUIR) ----------

def test_excluir_consulta(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    c_id = criar_consulta(client, pet_id, vet_id).json["consulta"]["id"]

    resposta = client.delete(f"/consultas/{c_id}")
    assert resposta.status_code == 200

    assert client.get(f"/consultas/{c_id}").status_code == 404


def test_excluir_consulta_inexistente_retorna_404(client):
    assert client.delete("/consultas/999").status_code == 404


# ---------- INTEGRAÇÃO EM CASCATA ----------

def test_excluir_pet_exclui_consultas_em_cascata(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id)
    vet_id = criar_veterinario(client)
    c_id = criar_consulta(client, pet_id, vet_id).json["consulta"]["id"]

    # Exclui o pet
    del_pet = client.delete(f"/pets/{pet_id}")
    assert del_pet.status_code == 200

    # Consulta deve ter sumido em cascata
    assert client.get(f"/consultas/{c_id}").status_code == 404
