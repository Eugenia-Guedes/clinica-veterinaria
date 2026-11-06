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

def test_nao_permitir_consulta_fora_do_expediente(client):

    # 1. Cadastrar usuário
    resposta_usuario = client.post("/usuarios", json={
        "nome": "Carlos Silva",
        "email": "carlos.agendamento@teste.com",
        "telefone": "83999999999",
        "senha": "SenhaSegura123"
    })

    assert resposta_usuario.status_code == 201
    usuario_id = resposta_usuario.json["usuario"]["id"]

    # 2. Cadastrar pet
    resposta_pet = client.post("/pets", json={
        "nome": "Bob",
        "especie": "Cachorro",
        "sexo": "M",
        "usuario_id": usuario_id
    })

    assert resposta_pet.status_code == 201
    pet_id = resposta_pet.json["pet"]["id"]

    # 3. Cadastrar veterinário
    resposta_veterinario = client.post("/veterinarios", json={
        "nome": "Dr. Pedro",
        "especialidade": "Clínica Geral"
    })

    assert resposta_veterinario.status_code == 201
    veterinario_id = resposta_veterinario.json["veterinario"]["id"]

    # 4. Cadastrar expediente das 08h às 12h
    resposta_disponibilidade = client.post(
        "/disponibilidade",
        json={
            "veterinario_id": veterinario_id,
            "dia_semana": "segunda",
            "hora_inicio": "08:00",
            "hora_fim": "12:00"
        }
    )

    assert resposta_disponibilidade.status_code == 201

    # 5. Verificar disponibilidade às 15h
    resposta_verificacao = client.get(
        "/disponibilidade/verificar",
        query_string={
            "veterinario_id": veterinario_id,
            "data": "2026-11-02",
            "hora": "15:00"
        }
    )

    assert resposta_verificacao.status_code == 200
    assert resposta_verificacao.json["disponivel"] is False

    # 6. Tentar agendar consulta fora do expediente
    resposta_consulta = client.post("/consultas", json={
        "pet_id": pet_id,
        "veterinario_id": veterinario_id,
        "data": "2026-11-02",
        "hora": "15:00",
        "motivo": "Consulta de rotina"
    })

    # O sistema deveria recusar o agendamento
    assert resposta_consulta.status_code in (400, 409), (
        "Falha: o sistema permitiu agendar uma consulta "
        "fora do expediente do veterinário. "
        f"Status recebido: {resposta_consulta.status_code}"
    )

    
def test_disponibilidade_considera_consultas_agendadas(client):
    # Cadastrar tutor
    resposta = client.post("/usuarios", json={
        "nome": "Maria Silva",
        "email": "maria.disponibilidade@teste.com",
        "telefone": "83999999999",
        "senha": "Senha12345"
    })
    assert resposta.status_code == 201
    usuario_id = resposta.json["usuario"]["id"]

    # Cadastrar pet
    resposta = client.post("/pets", json={
        "nome": "Rex",
        "especie": "Cachorro",
        "sexo": "Macho",
        "usuario_id": usuario_id
    })
    assert resposta.status_code == 201
    pet_id = resposta.json["pet"]["id"]

    # Cadastrar veterinario
    resposta = client.post("/veterinarios", json={
        "nome": "Dr. Carlos",
        "especialidade": "Clinica Geral"
    })
    assert resposta.status_code == 201
    veterinario_id = resposta.json["veterinario"]["id"]

    # Cadastrar expediente na segunda-feira
    resposta = client.post("/disponibilidade", json={
        "veterinario_id": veterinario_id,
        "dia_semana": "segunda",
        "hora_inicio": "08:00",
        "hora_fim": "12:00"
    })
    assert resposta.status_code == 201

    # Agendar consulta das 09:00 as 09:30
    resposta = client.post("/consultas", json={
        "pet_id": pet_id,
        "veterinario_id": veterinario_id,
        "data": "2026-11-02",
        "hora": "09:00",
        "duracao_minutos": 30,
        "motivo": "Consulta de rotina"
    })
    assert resposta.status_code == 201, resposta.get_json()

    # Verificar horario dentro da consulta existente
    resposta = client.get(
        "/disponibilidade/verificar",
        query_string={
            "veterinario_id": veterinario_id,
            "data": "2026-11-02",
            "hora": "09:15"
        }
    )

    assert resposta.status_code == 200

    assert resposta.json["disponivel"] is False, (
        "Falha: a API informou que o horario esta disponivel, "
        "mas o veterinario ja possui uma consulta agendada "
        "das 09:00 as 09:30."
    )


def test_disponibilidade_respeita_duracao_consulta(client):
    # Cadastrar veterinario
    resposta = client.post("/veterinarios", json={
        "nome": "Dra. Ana",
        "especialidade": "Clinica Geral"
    })
    assert resposta.status_code == 201
    veterinario_id = resposta.json["veterinario"]["id"]

    # Expediente de segunda-feira: 08:00 as 12:00
    resposta = client.post("/disponibilidade", json={
        "veterinario_id": veterinario_id,
        "dia_semana": "segunda",
        "hora_inicio": "08:00",
        "hora_fim": "12:00"
    })
    assert resposta.status_code == 201

    # Horarios e duracoes que queremos verificar
    cenarios = [
        ("11:30", 30, True),
        ("11:30", 45, False),
        ("11:15", 45, True),
        ("11:15", 60, False),
        ("11:00", 60, True),
        ("11:00", 20, None),
    ]

    for hora, duracao, esperado in cenarios:
        resposta = client.get(
            "/disponibilidade/verificar",
            query_string={
                "veterinario_id": veterinario_id,
                "data": "2026-11-02",
                "hora": hora,
                "duracao_minutos": duracao
            }
        )

        if esperado is None:
            assert resposta.status_code == 400
        else:
            assert resposta.status_code == 200
            assert resposta.json["disponivel"] is esperado, (
                f"Falha no horario {hora}, "
                f"duracao {duracao} minutos: "
                f"{resposta.json}"
            )

            
def test_disponibilidade_conflito_duracoes_diferentes(client):
    # Cadastrar tutor
    resposta = client.post("/usuarios", json={
        "nome": "Joao Silva",
        "email": "joao.duracoes@teste.com",
        "telefone": "83999999999",
        "senha": "Senha12345"
    })
    assert resposta.status_code == 201
    usuario_id = resposta.json["usuario"]["id"]

    # Cadastrar pet
    resposta = client.post("/pets", json={
        "nome": "Rex",
        "especie": "Cachorro",
        "sexo": "Macho",
        "usuario_id": usuario_id
    })
    assert resposta.status_code == 201
    pet_id = resposta.json["pet"]["id"]

    # Cadastrar veterinario
    resposta = client.post("/veterinarios", json={
        "nome": "Dr. Pedro",
        "especialidade": "Clinica Geral"
    })
    assert resposta.status_code == 201
    veterinario_id = resposta.json["veterinario"]["id"]

    # Expediente das 08:00 as 12:00
    resposta = client.post("/disponibilidade", json={
        "veterinario_id": veterinario_id,
        "dia_semana": "segunda",
        "hora_inicio": "08:00",
        "hora_fim": "12:00"
    })
    assert resposta.status_code == 201

    # Consulta existente das 10:00 as 10:30
    resposta = client.post("/consultas", json={
        "pet_id": pet_id,
        "veterinario_id": veterinario_id,
        "data": "2026-11-02",
        "hora": "10:00",
        "duracao_minutos": 30,
        "motivo": "Consulta de rotina"
    })
    assert resposta.status_code == 201, resposta.get_json()

    # Testar sobreposicoes e horarios livres
    cenarios = [
        ("09:45", 60, False),  # Sobrepoe a consulta existente
        ("09:30", 30, True),   # Termina exatamente as 10:00
        ("10:15", 45, False),  # Comeca durante a consulta
        ("10:30", 60, True),   # Comeca quando a anterior termina
    ]

    for hora, duracao, esperado in cenarios:
        resposta = client.get(
            "/disponibilidade/verificar",
            query_string={
                "veterinario_id": veterinario_id,
                "data": "2026-11-02",
                "hora": hora,
                "duracao_minutos": duracao
            }
        )

        assert resposta.status_code == 200
        assert resposta.json["disponivel"] is esperado, (
            f"Falha em {hora}, duracao {duracao}: "
            f"{resposta.json}"
        )


    
