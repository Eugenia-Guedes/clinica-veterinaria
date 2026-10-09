import re
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from extensions import db
from models.usuario import Usuario

usuarios_bp = Blueprint('usuarios', __name__)
EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


def corpo_json():
    if not request.is_json:
        return None
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else None


def validar(dados, obrigatorios=False):
    campos = ('nome', 'email', 'telefone', 'senha')
    if obrigatorios and any(c not in dados for c in campos):
        return 'Nome, email, telefone e senha são obrigatórios'
    for campo in campos:
        if campo in dados and (not isinstance(dados[campo], str) or not dados[campo].strip()):
            return f'{campo} deve ser um texto não vazio'
    if 'email' in dados and not EMAIL_RE.fullmatch(dados['email'].strip()):
        return 'E-mail inválido'
    if 'senha' in dados and len(dados['senha']) < 8:
        return 'A senha deve ter pelo menos 8 caracteres'
    if 'nome' in dados and len(dados['nome'].strip()) > 100:
        return 'Nome muito longo'
    if 'email' in dados and len(dados['email'].strip()) > 120:
        return 'E-mail muito longo'
    if 'telefone' in dados and len(dados['telefone'].strip()) > 20:
        return 'Telefone muito longo'
    return None


def email_normalizado(valor):
    return valor.strip().lower()


def usuario_atual():
    return db.session.get(Usuario, int(get_jwt_identity()))


@usuarios_bp.post('/usuarios')
def cadastrar_usuario():
    dados = corpo_json()
    if dados is None:
        return jsonify(erro='Envie um objeto JSON válido'), 400
    erro = validar(dados, obrigatorios=True)
    if erro:
        return jsonify(erro=erro), 400
    email = email_normalizado(dados['email'])
    if db.session.query(Usuario).filter_by(email=email).first():
        return jsonify(erro='E-mail já cadastrado'), 409
    usuario = Usuario(nome=dados['nome'].strip(), email=email,
                      telefone=dados['telefone'].strip(),
                      senha=generate_password_hash(dados['senha']))
    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(erro='E-mail já cadastrado'), 409
    return jsonify(mensagem='Usuário cadastrado com sucesso', usuario=usuario.publico()), 201


@usuarios_bp.post('/login')
def login():
    dados = corpo_json()
    if dados is None or not isinstance(dados.get('email'), str) or not isinstance(dados.get('senha'), str):
        return jsonify(erro='E-mail e senha são obrigatórios'), 400
    usuario = db.session.query(Usuario).filter_by(email=email_normalizado(dados['email'])).first()
    if not usuario or not check_password_hash(usuario.senha, dados['senha']):
        return jsonify(erro='E-mail ou senha inválidos'), 401
    token = create_access_token(identity=str(usuario.id))
    return jsonify(mensagem='Login realizado com sucesso', access_token=token, usuario=usuario.publico()), 200


@usuarios_bp.get('/usuarios')
@jwt_required()
def listar_usuarios():
    if usuario_atual() is None:
        return jsonify(erro='Usuário não encontrado'), 404
    # Demonstração acadêmica: em produção, restringir a administradores.
    usuarios = db.session.query(Usuario).order_by(Usuario.id).all()
    return jsonify([u.publico() for u in usuarios]), 200


@usuarios_bp.get('/usuarios/<int:id>')
@jwt_required()
def buscar_usuario(id):
    atual = usuario_atual()
    if atual is None:
        return jsonify(erro='Usuário não encontrado'), 404
    if atual.id != id:
        return jsonify(erro='Acesso negado'), 403
    return jsonify(atual.publico()), 200


@usuarios_bp.put('/usuarios/<int:id>')
@jwt_required()
def atualizar_usuario(id):
    usuario = usuario_atual()
    if usuario is None:
        return jsonify(erro='Usuário não encontrado'), 404
    if usuario.id != id:
        return jsonify(erro='Acesso negado'), 403
    dados = corpo_json()
    if dados is None:
        return jsonify(erro='Envie um objeto JSON válido'), 400
    erro = validar(dados)
    if erro:
        return jsonify(erro=erro), 400
    if not any(c in dados for c in ('nome', 'email', 'telefone', 'senha')):
        return jsonify(erro='Nenhum campo válido para atualizar'), 400
    if 'email' in dados:
        email = email_normalizado(dados['email'])
        outro = db.session.query(Usuario).filter_by(email=email).first()
        if outro and outro.id != usuario.id:
            return jsonify(erro='E-mail já cadastrado'), 409
        usuario.email = email
    if 'nome' in dados:
        usuario.nome = dados['nome'].strip()
    if 'telefone' in dados:
        usuario.telefone = dados['telefone'].strip()
    if 'senha' in dados:
        usuario.senha = generate_password_hash(dados['senha'])
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(erro='E-mail já cadastrado'), 409
    return jsonify(mensagem='Usuário atualizado com sucesso', usuario=usuario.publico()), 200


@usuarios_bp.delete('/usuarios/<int:id>')
@jwt_required()
def excluir_usuario(id):
    usuario = usuario_atual()
    if usuario is None:
        return jsonify(erro='Usuário não encontrado'), 404
    if usuario.id != id:
        return jsonify(erro='Acesso negado'), 403
    # Quando pets forem implementados, combinar exclusão de tutor com pets vinculados.
    db.session.delete(usuario)
    db.session.commit()
    return jsonify(mensagem='Usuário excluído com sucesso'), 200
