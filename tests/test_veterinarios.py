
# ---------- FUNÇÕES AUXILIARES ----------

def criar_veterinario(
    client,
    nome="Dra. Laura",
    especialidade="Clínica geral",
):
    """Cadastra um veterinário e retorna seu ID."""
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": nome,
            "especialidade": especialidade,
        },
    )

    assert resposta.status_code == 201, resposta.get_json()

    return resposta.json["veterinario"]["id"]


def criar_tutor(client):
    """Cadastra um tutor e retorna seu ID."""
    resposta = client.post(
        "/usuarios",
        json={
            "nome": "Tutor Teste",
            "email": "tutor@teste.com",
            "telefone": "83999999999",
            "senha": "senhaSegura123",
        },
    )

    assert resposta.status_code == 201, resposta.get_json()

    return resposta.json["usuario"]["id"]


def criar_pet(client, usuario_id):
    """Cadastra um pet vinculado ao tutor e retorna seu ID."""
    resposta = client.post(
        "/pets",
        json={
            "nome": "Rex",
            "especie": "Cachorro",
            "raca": "Labrador",
            "sexo": "Macho",
            "data_nascimento": "2023-01-15",
            "usuario_id": usuario_id,
        },
    )

    assert resposta.status_code == 201, resposta.get_json()

    return resposta.json["pet"]["id"]


def criar_consulta(client, pet_id, veterinario_id):
    """Cadastra uma consulta vinculada ao pet e ao veterinário."""
    return client.post(
        "/consultas",
        json={
            "pet_id": pet_id,
            "veterinario_id": veterinario_id,
            "data": "2026-11-10",
            "hora": "14:00",
            "motivo": "Consulta de rotina",
        },
    )


def criar_disponibilidade(client, veterinario_id):
    """Cadastra uma disponibilidade para o veterinário."""
    return client.post(
        "/disponibilidade",
        json={
            "veterinario_id": veterinario_id,
            "dia_semana": "terca",
            "hora_inicio": "08:00",
            "hora_fim": "18:00",
        },
    )


# ---------- CADASTRAR VETERINÁRIO ----------

def test_criar_veterinario_com_sucesso(client):
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": "Dra. Laura",
            "especialidade": "Clínica geral",
        },
    )

    assert resposta.status_code == 201

    veterinario = resposta.json["veterinario"]

    assert veterinario["id"] is not None
    assert veterinario["nome"] == "Dra. Laura"
    assert veterinario["especialidade"] == "Clínica geral"
    assert "crmv" not in veterinario


def test_criar_veterinario_sem_dados_retorna_400(client):
    resposta = client.post("/veterinarios", json={})

    assert resposta.status_code == 400


def test_criar_veterinario_sem_nome_retorna_400(client):
    resposta = client.post(
        "/veterinarios",
        json={
            "especialidade": "Clínica geral",
        },
    )

    assert resposta.status_code == 400


def test_criar_veterinario_sem_especialidade_retorna_400(client):
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": "Dra. Laura",
        },
    )

    assert resposta.status_code == 400


def test_criar_veterinario_com_campos_vazios_retorna_400(client):
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": "   ",
            "especialidade": "Clínica geral",
        },
    )

    assert resposta.status_code == 400


def test_criar_veterinario_com_crmv_retorna_400(client):
    resposta = client.post(
        "/veterinarios",
        json={
            "nome": "Dra. Laura",
            "especialidade": "Clínica geral",
            "crmv": "CRMV-PB 1234",
        },
    )

    assert resposta.status_code == 400


# ---------- LISTAR VETERINÁRIOS ----------

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


# ---------- BUSCAR VETERINÁRIO POR ID ----------

def test_buscar_veterinario_por_id(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.get(f"/veterinarios/{veterinario_id}")

    assert resposta.status_code == 200
    assert resposta.json["id"] == veterinario_id
    assert resposta.json["nome"] == "Dra. Laura"


def test_buscar_veterinario_inexistente_retorna_404(client):
    resposta = client.get("/veterinarios/999")

    assert resposta.status_code == 404


# ---------- ATUALIZAR VETERINÁRIO ----------

def test_atualizar_veterinario(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={
            "nome": "Dra. Ana",
            "especialidade": "Cirurgia",
        },
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
        },
    )

    assert resposta.status_code == 200
    assert resposta.json["veterinario"]["nome"] == "Dra. Ana"
    assert resposta.json["veterinario"]["especialidade"] == "Clínica geral"


def test_atualizar_veterinario_inexistente_retorna_404(client):
    resposta = client.put(
        "/veterinarios/999",
        json={
            "nome": "Dra. Ana",
        },
    )

    assert resposta.status_code == 404


def test_atualizar_sem_campos_retorna_400(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={},
    )

    assert resposta.status_code == 400


def test_atualizar_com_crmv_retorna_400(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={
            "crmv": "CRMV-PB 1234",
        },
    )

    assert resposta.status_code == 400


def test_atualizar_com_nome_vazio_retorna_400(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={
            "nome": "   ",
        },
    )

    assert resposta.status_code == 400


def test_atualizar_com_especialidade_vazia_retorna_400(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.put(
        f"/veterinarios/{veterinario_id}",
        json={
            "especialidade": "   ",
        },
    )

    assert resposta.status_code == 400


# ---------- EXCLUIR VETERINÁRIO ----------

def test_excluir_veterinario_sem_vinculos(client):
    veterinario_id = criar_veterinario(client)

    resposta = client.delete(f"/veterinarios/{veterinario_id}")

    assert resposta.status_code == 200

    busca = client.get(f"/veterinarios/{veterinario_id}")

    assert busca.status_code == 404


def test_excluir_veterinario_inexistente_retorna_404(client):
    resposta = client.delete("/veterinarios/999")

    assert resposta.status_code == 404


def test_impedir_exclusao_de_veterinario_com_consulta(client):
    veterinario_id = criar_veterinario(client)

    disponibilidade = criar_disponibilidade(client, veterinario_id)
    assert disponibilidade.status_code == 201, disponibilidade.get_json()

    usuario_id = criar_tutor(client)
    pet_id = criar_pet(client, usuario_id)

    consulta = criar_consulta(
        client,
        pet_id,
        veterinario_id,
    )

    assert consulta.status_code == 201, consulta.get_json()

    resposta = client.delete(f"/veterinarios/{veterinario_id}")

    assert resposta.status_code == 409


def test_impedir_exclusao_de_veterinario_com_disponibilidade(client):
    veterinario_id = criar_veterinario(client)

    disponibilidade = criar_disponibilidade(
        client,
        veterinario_id,
    )

    assert disponibilidade.status_code == 201, disponibilidade.get_json()

    resposta = client.delete(f"/veterinarios/{veterinario_id}")

    assert resposta.status_code == 409
