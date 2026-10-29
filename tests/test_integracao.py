import pytest

from app import create_app
from extensions import db


@pytest.fixture
def client():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "chave-segura-exclusiva-para-testes-integracao-2026",
    })

    with app.test_client() as client:
        yield client

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_fluxo_usuario_login_pet(client):
    # 1. Cadastrar um usuário
    resposta_usuario = client.post("/usuarios", json={
        "nome": "Maria Silva",
        "email": "maria.integracao@teste.com",
        "telefone": "83999999999",
        "senha": "SenhaSegura123",
    })

    assert resposta_usuario.status_code == 201

    usuario_id = resposta_usuario.json["usuario"]["id"]

    # 2. Realizar login
    resposta_login = client.post("/login", json={
        "email": "maria.integracao@teste.com",
        "senha": "SenhaSegura123",
    })

    assert resposta_login.status_code == 200

    token = resposta_login.json["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # 3. Consultar o usuário autenticado
    resposta_perfil = client.get(
        f"/usuarios/{usuario_id}",
        headers=headers,
    )

    assert resposta_perfil.status_code == 200
    assert resposta_perfil.json["id"] == usuario_id

    # 4. Cadastrar um pet vinculado ao usuário
    resposta_pet = client.post("/pets", json={
        "nome": "Rex",
        "especie": "Cachorro",
        "raca": "Labrador",
        "sexo": "M",
        "data_nascimento": "2023-05-10",
        "usuario_id": usuario_id,
    })

    assert resposta_pet.status_code == 201

    pet_id = resposta_pet.json["pet"]["id"]

    # 5. Consultar o pet cadastrado
    resposta_busca = client.get(f"/pets/{pet_id}")

    assert resposta_busca.status_code == 200
    assert resposta_busca.json["nome"] == "Rex"
    assert resposta_busca.json["usuario_id"] == usuario_id

    # 6. Listar os pets do usuário
    resposta_lista = client.get(
        "/pets",
        query_string={"usuario_id": usuario_id},
    )

    assert resposta_lista.status_code == 200
    assert any(
        pet["id"] == pet_id
        for pet in resposta_lista.json
    )

def test_fluxo_completo_agendamento_consulta(client):

     # 1. Cadastrar usuário
    resposta_usuario = client.post("/usuarios", json={
            "nome": "João Silva",
            "email": "joao.integracao@teste.com",
            "telefone": "83988888888",
            "senha": "SenhaSegura123"
        })

    assert resposta_usuario.status_code == 201
    usuario_id = resposta_usuario.json["usuario"]["id"]

    # 2. Cadastrar pet
    resposta_pet = client.post("/pets", json={
        "nome": "Thor",
        "especie": "Cachorro",
        "raca": "Golden Retriever",
        "sexo": "M",
        "usuario_id": usuario_id
    })

    assert resposta_pet.status_code == 201
    pet_id = resposta_pet.json["pet"]["id"]

    # 3. Cadastrar veterinário
    resposta_veterinario = client.post("/veterinarios", json={
        "nome": "Dra. Ana Costa",
        "crmv": "PB-12345",
        "especialidade": "Clínica Geral"
    })

    assert resposta_veterinario.status_code == 201
    veterinario_id = resposta_veterinario.json["veterinario"]["id"]

    # 4. Cadastrar disponibilidade
    resposta_disponibilidade = client.post("/disponibilidade", json={
        "veterinario_id": veterinario_id,
        "dia_semana": "segunda",
        "hora_inicio": "08:00",
        "hora_fim": "12:00"
    })

    assert resposta_disponibilidade.status_code == 201

    # 5. Verificar disponibilidade
    resposta_verificacao = client.get(
        "/disponibilidade/verificar",
        query_string={
            "veterinario_id": veterinario_id,
            "data": "2026-11-02",
            "hora": "09:00"
        }
    )

    assert resposta_verificacao.status_code == 200
    assert resposta_verificacao.json["disponivel"] is True

    # 6. Agendar consulta
    dados_consulta = {
        "pet_id": pet_id,
        "veterinario_id": veterinario_id,
        "data": "2026-11-02",
        "hora": "09:00",
        "motivo": "Consulta de rotina"
    }

    resposta_consulta = client.post(
        "/consultas",
        json=dados_consulta
    )

    assert resposta_consulta.status_code == 201

    consulta_id = resposta_consulta.json["consulta"]["id"]

    assert resposta_consulta.json["consulta"]["status"] == "Agendada"

    # 7. Verificar conflito de horário
    resposta_conflito = client.post(
        "/consultas",
        json=dados_consulta
    )

    assert resposta_conflito.status_code == 409

    # 8. Consultar agendamento
    resposta_busca = client.get(
        f"/consultas/{consulta_id}"
    )

    assert resposta_busca.status_code == 200
    assert resposta_busca.json["pet_id"] == pet_id
    assert resposta_busca.json["veterinario_id"] == veterinario_id

    # 9. Remarcar consulta
    resposta_remarcacao = client.put(
        f"/consultas/{consulta_id}/remarcar",
        json={
            "data": "2026-11-02",
            "hora": "10:00"
        }
    )

    assert resposta_remarcacao.status_code == 200
    assert resposta_remarcacao.json["consulta"]["status"] == "Remarcada"
    assert resposta_remarcacao.json["consulta"]["hora"] == "10:00"

    # 10. Cancelar consulta
    resposta_cancelamento = client.put(
        f"/consultas/{consulta_id}/cancelar"
    )

    assert resposta_cancelamento.status_code == 200
    assert resposta_cancelamento.json["consulta"]["status"] == "Cancelada"

    # 11. Verificar situação final
    resposta_final = client.get(
        f"/consultas/{consulta_id}"
    )

    assert resposta_final.status_code == 200
    assert resposta_final.json["status"] == "Cancelada"