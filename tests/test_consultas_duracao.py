"""
Testes das regras de agenda do módulo de consultas:
duração, conflito de intervalos, expediente, remarcação,
ordenação da listagem, validação do motivo e erro de banco.

Usa as fixtures `app` e `client` do tests/conftest.py e cria
os dados de apoio direto pelo ORM, sem passar pelas rotas.
"""

import pytest
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.disponibilidade import Disponibilidade
from models.pet import Pet
from models.usuario import Usuario
from models.veterinario import Veterinario


# 2026-11-10 é uma terça-feira; 2026-11-08 é domingo.
TERCA = "2026-11-10"
TERCA_SEGUINTE = "2026-11-17"
DOMINGO = "2026-11-08"


@pytest.fixture
def cenario(app):
    """
    Cria 1 tutor, 2 pets e 2 veterinários.
    Cada veterinário atende às terças, das 08:00 às 12:00.
    Devolve só os ids, para uso fora do contexto da aplicação.
    """
    with app.app_context():
        tutor = Usuario(
            nome="Tutor Teste",
            email="tutor@teste.com",
            telefone="83999999999",
            senha="hash-qualquer"
        )
        db.session.add(tutor)
        db.session.flush()

        pet1 = Pet(
            nome="Rex", especie="Cachorro",
            sexo="Macho", usuario_id=tutor.id
        )
        pet2 = Pet(
            nome="Mel", especie="Gato",
            sexo="Femea", usuario_id=tutor.id
        )
        vet1 = Veterinario(
            nome="Dra. Ana", especialidade="Clinica geral"
        )
        vet2 = Veterinario(
            nome="Dr. Bruno", especialidade="Cirurgia"
        )
        db.session.add_all([pet1, pet2, vet1, vet2])
        db.session.flush()

        for vet in (vet1, vet2):
            db.session.add(Disponibilidade(
                veterinario_id=vet.id,
                dia_semana="terca",
                hora_inicio="08:00",
                hora_fim="12:00"
            ))

        db.session.commit()

        return {
            "pet1": pet1.id,
            "pet2": pet2.id,
            "vet1": vet1.id,
            "vet2": vet2.id,
        }


def agendar(client, cenario, **campos):
    """POST /consultas com valores padrão que podem ser trocados."""
    corpo = {
        "pet_id": cenario["pet1"],
        "veterinario_id": cenario["vet1"],
        "data": TERCA,
        "hora": "09:00",
    }
    corpo.update(campos)
    return client.post("/consultas", json=corpo)


# ----------------------------------------------------------
# Duração
# ----------------------------------------------------------

def test_duracao_padrao_e_30_minutos(client, cenario):
    resposta = agendar(client, cenario)

    assert resposta.status_code == 201, resposta.get_json()

    consulta = resposta.get_json()["consulta"]
    assert consulta["duracao_minutos"] == 30
    assert consulta["hora_fim"] == "09:30"


@pytest.mark.parametrize("duracao, hora_fim_esperada", [
    (30, "09:30"),
    (45, "09:45"),
    (60, "10:00"),
])
def test_duracoes_permitidas_calculam_hora_fim(
    client, cenario, duracao, hora_fim_esperada
):
    resposta = agendar(client, cenario, duracao_minutos=duracao)

    assert resposta.status_code == 201, resposta.get_json()

    consulta = resposta.get_json()["consulta"]
    assert consulta["duracao_minutos"] == duracao
    assert consulta["hora_fim"] == hora_fim_esperada


@pytest.mark.parametrize("duracao_invalida", [
    20, 90, 0, -30, "30", 30.5, True, None
])
def test_duracao_invalida_retorna_400(
    client, cenario, duracao_invalida
):
    resposta = agendar(
        client, cenario, duracao_minutos=duracao_invalida
    )

    assert resposta.status_code == 400, resposta.get_json()
    assert "duracao_minutos" in resposta.get_json()["erro"]


def test_buscar_consulta_retorna_duracao_e_hora_fim(client, cenario):
    criada = agendar(
        client, cenario, duracao_minutos=45
    ).get_json()["consulta"]

    resposta = client.get(f"/consultas/{criada['id']}")

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["duracao_minutos"] == 45
    assert corpo["hora_fim"] == "09:45"


# ----------------------------------------------------------
# Conflito de intervalos
# ----------------------------------------------------------

def test_veterinario_nao_pode_ter_consultas_sobrepostas(
    client, cenario
):
    # 09:00 às 10:00
    assert agendar(
        client, cenario, duracao_minutos=60
    ).status_code == 201

    # 09:30 às 10:00, outro pet, mesmo veterinário
    resposta = agendar(
        client, cenario,
        pet_id=cenario["pet2"], hora="09:30"
    )

    assert resposta.status_code == 409
    assert "Veterinário já possui consulta" in (
        resposta.get_json()["erro"]
    )


def test_pet_nao_pode_ter_consultas_sobrepostas(client, cenario):
    # 09:00 às 10:00 com o veterinário 1
    assert agendar(
        client, cenario, duracao_minutos=60
    ).status_code == 201

    # 09:30 com o veterinário 2, mas o mesmo pet
    resposta = agendar(
        client, cenario,
        veterinario_id=cenario["vet2"], hora="09:30"
    )

    assert resposta.status_code == 409
    assert "Pet já possui consulta" in resposta.get_json()["erro"]


def test_consultas_em_sequencia_sao_permitidas(client, cenario):
    # 09:00 às 10:00 e depois 10:00 às 10:30
    assert agendar(
        client, cenario, duracao_minutos=60
    ).status_code == 201

    resposta = agendar(client, cenario, hora="10:00")

    assert resposta.status_code == 201, resposta.get_json()


def test_consulta_cancelada_libera_o_horario(client, cenario):
    criada = agendar(client, cenario).get_json()["consulta"]

    cancelamento = client.post(
        f"/consultas/{criada['id']}/cancelar"
    )
    assert cancelamento.status_code == 200

    resposta = agendar(client, cenario)

    assert resposta.status_code == 201, resposta.get_json()


# ----------------------------------------------------------
# Expediente e dias sem atendimento
# ----------------------------------------------------------

def test_consulta_que_termina_depois_do_expediente_e_rejeitada(
    client, cenario
):
    # Expediente até 12:00; 11:30 + 60 min termina às 12:30.
    resposta = agendar(
        client, cenario, hora="11:30", duracao_minutos=60
    )

    assert resposta.status_code == 409
    assert "disponibilidade" in resposta.get_json()["erro"]


def test_consulta_que_termina_exatamente_no_fim_do_expediente(
    client, cenario
):
    # 11:00 + 60 min termina às 12:00, o limite do expediente.
    resposta = agendar(
        client, cenario, hora="11:00", duracao_minutos=60
    )

    assert resposta.status_code == 201, resposta.get_json()


def test_consulta_antes_do_inicio_do_expediente_e_rejeitada(
    client, cenario
):
    resposta = agendar(client, cenario, hora="07:30")

    assert resposta.status_code == 409


def test_consulta_no_domingo_e_rejeitada(client, cenario):
    resposta = agendar(client, cenario, data=DOMINGO)

    assert resposta.status_code == 409


# ----------------------------------------------------------
# Atualização (PUT)
# ----------------------------------------------------------

def test_atualizar_duracao_recalcula_hora_fim(client, cenario):
    criada = agendar(client, cenario).get_json()["consulta"]

    resposta = client.put(
        f"/consultas/{criada['id']}",
        json={"duracao_minutos": 60}
    )

    assert resposta.status_code == 200, resposta.get_json()

    consulta = resposta.get_json()["consulta"]
    assert consulta["duracao_minutos"] == 60
    assert consulta["hora_fim"] == "10:00"


def test_atualizar_duracao_que_invade_outra_consulta_e_rejeitado(
    client, cenario
):
    criada = agendar(client, cenario).get_json()["consulta"]

    # Outra consulta às 09:30, com outro pet.
    assert agendar(
        client, cenario,
        pet_id=cenario["pet2"], hora="09:30"
    ).status_code == 201

    resposta = client.put(
        f"/consultas/{criada['id']}",
        json={"duracao_minutos": 45}
    )

    assert resposta.status_code == 409

    # A duração original foi preservada.
    consulta = client.get(f"/consultas/{criada['id']}").get_json()
    assert consulta["duracao_minutos"] == 30


def test_atualizar_com_duracao_invalida_retorna_400(client, cenario):
    criada = agendar(client, cenario).get_json()["consulta"]

    resposta = client.put(
        f"/consultas/{criada['id']}",
        json={"duracao_minutos": 25}
    )

    assert resposta.status_code == 400


def test_atualizar_sem_enviar_duracao_preserva_a_duracao(
    client, cenario
):
    criada = agendar(
        client, cenario, duracao_minutos=45
    ).get_json()["consulta"]

    resposta = client.put(
        f"/consultas/{criada['id']}",
        json={"motivo": "Retorno"}
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["consulta"]["duracao_minutos"] == 45


# ----------------------------------------------------------
# Remarcação
# ----------------------------------------------------------

def test_remarcar_preserva_a_duracao(client, cenario):
    criada = agendar(
        client, cenario, duracao_minutos=45, hora="09:00"
    ).get_json()["consulta"]

    resposta = client.put(
        f"/consultas/{criada['id']}/remarcar",
        json={"hora": "10:00"}
    )

    assert resposta.status_code == 200, resposta.get_json()

    consulta = resposta.get_json()["consulta"]
    assert consulta["status"] == "Remarcada"
    assert consulta["duracao_minutos"] == 45
    assert consulta["hora_fim"] == "10:45"


def test_remarcar_para_horario_que_termina_fora_do_expediente(
    client, cenario
):
    criada = agendar(
        client, cenario, duracao_minutos=45
    ).get_json()["consulta"]

    # 11:30 + 45 min termina às 12:15, depois do expediente.
    resposta = client.put(
        f"/consultas/{criada['id']}/remarcar",
        json={"hora": "11:30"}
    )

    assert resposta.status_code == 409

    # A consulta continua no horário original.
    consulta = client.get(f"/consultas/{criada['id']}").get_json()
    assert consulta["hora"] == "09:00"
    assert consulta["status"] == "Agendada"


def test_remarcar_para_horario_que_sobrepoe_outra_consulta(
    client, cenario
):
    criada = agendar(client, cenario).get_json()["consulta"]

    # Outra consulta das 10:00 às 11:00, com outro pet.
    assert agendar(
        client, cenario,
        pet_id=cenario["pet2"], hora="10:00",
        duracao_minutos=60
    ).status_code == 201

    resposta = client.put(
        f"/consultas/{criada['id']}/remarcar",
        json={"hora": "10:30"}
    )

    assert resposta.status_code == 409


# ----------------------------------------------------------
# Listagem
# ----------------------------------------------------------

def test_listagem_vem_ordenada_por_data_e_hora(client, cenario):
    agendar(client, cenario, hora="10:00")
    agendar(
        client, cenario,
        pet_id=cenario["pet2"], hora="09:00"
    )

    resposta = client.get("/consultas")

    assert resposta.status_code == 200
    horas = [c["hora"] for c in resposta.get_json()]
    assert horas == ["09:00", "10:00"]


def test_filtro_de_data_invalida_retorna_400(client, cenario):
    resposta = client.get("/consultas?data=31-12-2026")

    assert resposta.status_code == 400


def test_filtro_por_data_retorna_so_a_data_pedida(client, cenario):
    # As duas datas são terças, então o expediente vale para ambas.
    agendar(client, cenario, data=TERCA)
    agendar(client, cenario, data=TERCA_SEGUINTE)

    resposta = client.get(f"/consultas?data={TERCA_SEGUINTE}")

    assert resposta.status_code == 200
    datas = {c["data"] for c in resposta.get_json()}
    assert datas == {TERCA_SEGUINTE}


# ----------------------------------------------------------
# Motivo
# ----------------------------------------------------------

@pytest.mark.parametrize("motivo_invalido", [123, ["a"], {"a": 1}, True])
def test_motivo_que_nao_e_texto_retorna_400(
    client, cenario, motivo_invalido
):
    resposta = agendar(client, cenario, motivo=motivo_invalido)

    assert resposta.status_code == 400
    assert "motivo" in resposta.get_json()["erro"]


def test_motivo_acima_do_limite_retorna_400(client, cenario):
    resposta = agendar(client, cenario, motivo="a" * 256)

    assert resposta.status_code == 400


def test_motivo_no_limite_exato_e_aceito(client, cenario):
    resposta = agendar(client, cenario, motivo="a" * 255)

    assert resposta.status_code == 201, resposta.get_json()


def test_motivo_tem_os_espacos_das_pontas_removidos(client, cenario):
    resposta = agendar(client, cenario, motivo="  Vacina  ")

    assert resposta.status_code == 201
    assert resposta.get_json()["consulta"]["motivo"] == "Vacina"


# ----------------------------------------------------------
# Corpo da requisição e erro de banco
# ----------------------------------------------------------

def test_corpo_que_nao_e_json_retorna_400(client, cenario):
    resposta = client.post(
        "/consultas",
        data="isto não é json",
        content_type="text/plain"
    )

    assert resposta.status_code == 400


def test_json_que_nao_e_objeto_retorna_400(client, cenario):
    resposta = client.post("/consultas", json=[1, 2, 3])

    assert resposta.status_code == 400


def test_falha_no_commit_retorna_500_em_json(
    client, cenario, monkeypatch
):
    def commit_com_falha():
        raise SQLAlchemyError("falha simulada")

    monkeypatch.setattr(db.session, "commit", commit_com_falha)

    resposta = agendar(client, cenario)

    assert resposta.status_code == 500
    assert "erro" in resposta.get_json()