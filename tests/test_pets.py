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
    """Cadastra um tutor válido e devolve o id dele."""
    resposta = client.post("/usuarios", json={
        "nome": "Tutor Teste",
        "email": email,
        "telefone": "83999999999",
        "senha": SENHA,
    })
    assert resposta.status_code == 201
    return resposta.json["usuario"]["id"]


def login(client, email="tutor@teste.com"):
    """Faz login e devolve o cabeçalho com o token JWT."""
    resposta = client.post("/login", json={"email": email, "senha": SENHA})
    assert resposta.status_code == 200
    return {"Authorization": "Bearer " + resposta.json["access_token"]}


def criar_pet(client, usuario_id, **campos):
    """Cadastra um pet com dados padrão. Qualquer campo pode ser trocado."""
    dados = {
        "nome": "Rex",
        "especie": "Cachorro",
        "raca": "Golden Retriever",
        "sexo": "Macho",
        "data_nascimento": "2022-05-10",
        "usuario_id": usuario_id,
    }
    dados.update(campos)
    return client.post("/pets", json=dados)


# ---------- POST /pets ----------

def test_criar_pet_com_sucesso(client):
    tutor_id = criar_tutor(client)

    resposta = criar_pet(client, tutor_id)

    assert resposta.status_code == 201
    pet = resposta.json["pet"]
    assert pet["id"] is not None
    assert pet["nome"] == "Rex"
    assert pet["data_nascimento"] == "2022-05-10"
    assert pet["usuario_id"] == tutor_id


def test_criar_pet_sem_campos_opcionais(client):
    tutor_id = criar_tutor(client)

    resposta = client.post("/pets", json={
        "nome": "Mia",
        "especie": "Gato",
        "sexo": "Fêmea",
        "usuario_id": tutor_id,
    })

    assert resposta.status_code == 201
    assert resposta.json["pet"]["raca"] is None
    assert resposta.json["pet"]["data_nascimento"] is None


def test_criar_pet_sem_dados(client):
    assert client.post("/pets", json={}).status_code == 400


def test_criar_pet_sem_campos_obrigatorios(client):
    resposta = client.post("/pets", json={"nome": "Sem espécie"})

    assert resposta.status_code == 400
    assert "erro" in resposta.json


def test_criar_pet_com_tutor_inexistente(client):
    resposta = criar_pet(client, usuario_id=999)

    assert resposta.status_code == 404
    assert resposta.json["erro"] == "Tutor não encontrado"


def test_criar_pet_com_usuario_id_em_texto(client):
    assert criar_pet(client, usuario_id="abc").status_code == 400


def test_criar_pet_com_data_invalida(client):
    tutor_id = criar_tutor(client)

    resposta = criar_pet(client, tutor_id, data_nascimento="10/05/2022")

    assert resposta.status_code == 400


# ---------- GET /pets e GET /pets/<id> ----------

def test_listar_pets_e_filtrar_por_tutor(client):
    tutor_1 = criar_tutor(client, "tutor1@teste.com")
    tutor_2 = criar_tutor(client, "tutor2@teste.com")
    criar_pet(client, tutor_1, nome="Rex")
    criar_pet(client, tutor_1, nome="Thor")
    criar_pet(client, tutor_2, nome="Mia")

    todos = client.get("/pets")
    assert todos.status_code == 200
    assert len(todos.json) == 3

    do_tutor_1 = client.get(f"/pets?usuario_id={tutor_1}")
    assert do_tutor_1.status_code == 200
    assert len(do_tutor_1.json) == 2
    for pet in do_tutor_1.json:
        assert pet["usuario_id"] == tutor_1


def test_buscar_pet_por_id(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id).json["pet"]["id"]

    resposta = client.get(f"/pets/{pet_id}")

    assert resposta.status_code == 200
    assert resposta.json["nome"] == "Rex"


def test_buscar_pet_inexistente(client):
    resposta = client.get("/pets/999")

    assert resposta.status_code == 404
    assert resposta.json["erro"] == "Pet não encontrado"


# ---------- PUT /pets/<id> ----------

def test_atualizar_pet_parcialmente(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id).json["pet"]["id"]

    resposta = client.put(f"/pets/{pet_id}", json={
        "nome": "Rex Jr.",
        "data_nascimento": "2022-06-15",
    })

    assert resposta.status_code == 200
    pet = resposta.json["pet"]
    assert pet["nome"] == "Rex Jr."
    assert pet["data_nascimento"] == "2022-06-15"
    assert pet["raca"] == "Golden Retriever"  # não foi enviado, então não muda


def test_transferir_pet_para_outro_tutor(client):
    tutor_1 = criar_tutor(client, "tutor1@teste.com")
    tutor_2 = criar_tutor(client, "tutor2@teste.com")
    pet_id = criar_pet(client, tutor_1).json["pet"]["id"]

    resposta = client.put(f"/pets/{pet_id}", json={"usuario_id": tutor_2})

    assert resposta.status_code == 200
    assert resposta.json["pet"]["usuario_id"] == tutor_2


def test_atualizar_pet_com_dados_invalidos(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id).json["pet"]["id"]
    url = f"/pets/{pet_id}"

    assert client.put(url, json={}).status_code == 400
    assert client.put(url, json={"nome": ""}).status_code == 400
    assert client.put(url, json={"data_nascimento": "abc"}).status_code == 400
    assert client.put(url, json={"usuario_id": "abc"}).status_code == 400
    assert client.put(url, json={"usuario_id": 999}).status_code == 404

    # depois de tantas tentativas inválidas, o pet não pode ter mudado
    assert client.get(url).json["nome"] == "Rex"


def test_atualizar_pet_inexistente(client):
    assert client.put("/pets/999", json={"nome": "Thor"}).status_code == 404


# ---------- DELETE /pets/<id> ----------

def test_excluir_pet(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id).json["pet"]["id"]

    resposta = client.delete(f"/pets/{pet_id}")

    assert resposta.status_code == 200
    assert client.get(f"/pets/{pet_id}").status_code == 404


def test_excluir_pet_inexistente(client):
    assert client.delete("/pets/999").status_code == 404


# ---------- INTEGRAÇÃO COM USUÁRIOS ----------

def test_excluir_tutor_exclui_os_pets_dele(client):
    tutor_id = criar_tutor(client)
    pet_id = criar_pet(client, tutor_id).json["pet"]["id"]
    headers = login(client)

    resposta = client.delete(f"/usuarios/{tutor_id}", headers=headers)

    assert resposta.status_code == 200
    assert client.get(f"/pets/{pet_id}").status_code == 404