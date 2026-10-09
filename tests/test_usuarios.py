import pytest
from app import create_app
from extensions import db

@pytest.fixture
def client():
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', "JWT_SECRET_KEY": "chave-segura-exclusiva-para-testes-uniesp-2026"})
    with app.test_client() as client:
        yield client
    with app.app_context():
        db.session.remove()
        db.drop_all()

def cadastro(client, email='maria@teste.com'):
    return client.post('/usuarios', json={'nome': 'Maria', 'email': email, 'telefone': '83999999999', 'senha': 'senhaSegura123'})

def auth(client):
    resposta = client.post('/login', json={'email': 'maria@teste.com', 'senha': 'senhaSegura123'})
    return {'Authorization': 'Bearer ' + resposta.json['access_token']}

def test_cadastro_login_e_permissoes(client):
    r = cadastro(client)
    assert r.status_code == 201
    assert 'senha' not in r.json['usuario']
    assert cadastro(client).status_code == 409
    assert client.post('/login', json={'email': 'maria@teste.com', 'senha': 'errada'}).status_code == 401
    assert client.get('/usuarios').status_code == 401
    headers = auth(client)
    assert client.get('/usuarios', headers=headers).status_code == 200
    id = r.json['usuario']['id']
    assert client.get(f'/usuarios/{id}', headers=headers).status_code == 200
    assert client.put(f'/usuarios/{id}', headers=headers, json={'nome': 'Maria Nova'}).json['usuario']['nome'] == 'Maria Nova'
    assert client.delete(f'/usuarios/{id}', headers=headers).status_code == 200

def test_validacoes(client):
    assert client.post('/usuarios', json={'nome': 'Sem dados'}).status_code == 400
    assert client.post('/usuarios', json={'nome': 'Maria', 'email': 'errado', 'telefone': '123', 'senha': 'senhaSegura123'}).status_code == 400
    r = cadastro(client)
    headers = auth(client)
    assert client.put(f"/usuarios/{r.json['usuario']['id']}", headers=headers, json={'senha': '123'}).status_code == 400
    assert client.get('/usuarios/999', headers=headers).status_code == 403
