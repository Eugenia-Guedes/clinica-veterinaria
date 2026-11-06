"""
Testes da migração 003 (coluna duracao_minutos em consultas).

Usam só sqlite3 e a pasta temporária do pytest: o banco real
(instance/clinica.db) nunca é aberto.
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest


CAMINHO_MIGRACAO = (
    Path(__file__).resolve().parent.parent
    / "migrations"
    / "003_adicionar_duracao_consultas.py"
)


def carregar_migracao():
    # O nome do arquivo começa com número, então não dá para
    # importá-lo com "import"; carregamos pelo caminho.
    spec = importlib.util.spec_from_file_location(
        "migracao_003", CAMINHO_MIGRACAO
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def listar_colunas(caminho):
    conexao = sqlite3.connect(caminho)
    try:
        return {
            linha[1]
            for linha in conexao.execute(
                "PRAGMA table_info(consultas)"
            )
        }
    finally:
        conexao.close()


def consultar(caminho, sql):
    conexao = sqlite3.connect(caminho)
    try:
        return conexao.execute(sql).fetchall()
    finally:
        conexao.close()


def listar_backups(pasta):
    return list(pasta.glob("clinica_backup_antes_duracao_*.db"))


@pytest.fixture
def banco_antigo(tmp_path):
    """Banco no formato anterior à migração, com 2 consultas."""
    caminho = tmp_path / "clinica.db"
    conexao = sqlite3.connect(caminho)
    conexao.executescript("""
        CREATE TABLE pets (id INTEGER PRIMARY KEY, nome TEXT);
        CREATE TABLE veterinarios (
            id INTEGER PRIMARY KEY,
            nome TEXT,
            especialidade TEXT
        );
        CREATE TABLE consultas (
            id INTEGER PRIMARY KEY,
            pet_id INTEGER NOT NULL REFERENCES pets(id),
            veterinario_id INTEGER NOT NULL
                REFERENCES veterinarios(id),
            data DATE NOT NULL,
            hora VARCHAR(5) NOT NULL,
            motivo VARCHAR(255),
            status VARCHAR(20) NOT NULL
        );
        INSERT INTO pets VALUES (1, 'Rex');
        INSERT INTO veterinarios VALUES (1, 'Dra. Ana', 'Clinica');
        INSERT INTO consultas VALUES
            (1, 1, 1, '2026-11-10', '09:00', 'Vacina', 'Agendada');
        INSERT INTO consultas VALUES
            (2, 1, 1, '2026-11-10', '10:00', NULL, 'Cancelada');
    """)
    conexao.commit()
    conexao.close()
    return caminho


def test_adiciona_coluna_e_preserva_os_dados(banco_antigo):
    carregar_migracao().migrar(banco_antigo)

    assert "duracao_minutos" in listar_colunas(banco_antigo)

    linhas = consultar(
        banco_antigo,
        "SELECT id, hora, motivo, status, duracao_minutos "
        "FROM consultas ORDER BY id"
    )
    assert linhas == [
        (1, "09:00", "Vacina", "Agendada", 30),
        (2, "10:00", None, "Cancelada", 30),
    ]


def test_cria_backup_do_banco_antigo_antes_de_alterar(
    banco_antigo
):
    carregar_migracao().migrar(banco_antigo)

    backups = listar_backups(banco_antigo.parent)
    assert len(backups) == 1

    # O backup guarda o banco como estava: sem a coluna nova,
    # mas com as duas consultas.
    assert "duracao_minutos" not in listar_colunas(backups[0])
    assert consultar(
        backups[0], "SELECT COUNT(*) FROM consultas"
    ) == [(2,)]


def test_rodar_duas_vezes_nao_altera_nem_cria_outro_backup(
    banco_antigo
):
    migracao = carregar_migracao()

    migracao.migrar(banco_antigo)
    migracao.migrar(banco_antigo)

    assert len(listar_backups(banco_antigo.parent)) == 1
    assert consultar(
        banco_antigo, "SELECT COUNT(*) FROM consultas"
    ) == [(2,)]


def test_banco_inexistente_levanta_erro(tmp_path):
    with pytest.raises(FileNotFoundError):
        carregar_migracao().migrar(tmp_path / "nao_existe.db")


def test_estrutura_inesperada_aborta_sem_alterar_nada(
    banco_antigo
):
    conexao = sqlite3.connect(banco_antigo)
    conexao.execute("ALTER TABLE consultas ADD COLUMN extra TEXT")
    conexao.commit()
    conexao.close()

    with pytest.raises(RuntimeError):
        carregar_migracao().migrar(banco_antigo)

    assert "duracao_minutos" not in listar_colunas(banco_antigo)
    assert listar_backups(banco_antigo.parent) == []