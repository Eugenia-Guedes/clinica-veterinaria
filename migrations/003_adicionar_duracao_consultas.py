
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
BANCO_PADRAO = BASE_DIR / "instance" / "clinica.db"

DURACAO_PADRAO = 30


def verificar_integridade(conexao):
    resultado = conexao.execute(
        "PRAGMA integrity_check"
    ).fetchone()

    return resultado[0] == "ok"


def criar_backup(banco):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    backup = banco.with_name(
        f"{banco.stem}_backup_antes_duracao_{timestamp}{banco.suffix}"
    )

    origem = sqlite3.connect(banco)
    destino = sqlite3.connect(backup)

    try:
        origem.backup(destino)
    finally:
        destino.close()
        origem.close()

    return backup


def migrar(caminho_banco):
    banco = caminho_banco.resolve()

    if not banco.is_file():
        raise FileNotFoundError(
            f"Banco de dados não encontrado: {banco}"
        )

    conexao = sqlite3.connect(banco)

    try:
        if not verificar_integridade(conexao):
            raise RuntimeError(
                "O banco apresenta problemas de integridade."
            )

        colunas = {
            coluna[1]
            for coluna in conexao.execute(
                "PRAGMA table_info(consultas)"
            )
        }

        if not colunas:
            raise RuntimeError(
                "Tabela consultas não encontrada."
            )

        if "duracao_minutos" in colunas:
            print(
                "A coluna duracao_minutos já existe. "
                "Nenhuma alteração realizada."
            )
            return

        colunas_esperadas = {
            "id",
            "pet_id",
            "veterinario_id",
            "data",
            "hora",
            "motivo",
            "status",
        }

        if colunas != colunas_esperadas:
            raise RuntimeError(
                f"Estrutura inesperada na tabela consultas: {colunas}"
            )

        erros_fk = conexao.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if erros_fk:
            raise RuntimeError(
                f"O banco apresenta problemas de relacionamento: {erros_fk}"
            )

        quantidade_original = conexao.execute(
            "SELECT COUNT(*) FROM consultas"
        ).fetchone()[0]

    finally:
        conexao.close()

    backup = criar_backup(banco)
    print(f"Backup criado: {backup}")

    conexao = sqlite3.connect(banco)

    try:
        conexao.execute("BEGIN IMMEDIATE")

        colunas_atuais = {
            coluna[1]
            for coluna in conexao.execute(
                "PRAGMA table_info(consultas)"
            )
        }

        if "duracao_minutos" in colunas_atuais:
            raise RuntimeError(
                "A coluna já existe. Migração cancelada."
            )

        conexao.execute("""
            ALTER TABLE consultas
            ADD COLUMN duracao_minutos INTEGER NOT NULL DEFAULT 30
        """)

        quantidade_nova = conexao.execute(
            "SELECT COUNT(*) FROM consultas"
        ).fetchone()[0]

        if quantidade_original != quantidade_nova:
            raise RuntimeError(
                "A quantidade de consultas não foi preservada."
            )

        duracoes_invalidas = conexao.execute("""
            SELECT COUNT(*)
            FROM consultas
            WHERE duracao_minutos != 30
        """).fetchone()[0]

        if duracoes_invalidas:
            raise RuntimeError(
                "Foram encontrados valores inesperados de duração."
            )

        erros_fk = conexao.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if erros_fk:
            raise RuntimeError(
                f"Problemas de relacionamento: {erros_fk}"
            )

        if not verificar_integridade(conexao):
            raise RuntimeError(
                "Falha na verificação de integridade."
            )

        conexao.commit()

        print("\nMIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("Consultas preservadas:", quantidade_nova)
        print("Duração padrão:", DURACAO_PADRAO, "minutos")
        print("Integridade: ok")

    except Exception:
        if conexao.in_transaction:
            conexao.rollback()
        raise

    finally:
        conexao.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Adiciona duração às consultas."
    )

    parser.add_argument(
        "--banco",
        type=Path,
        default=BANCO_PADRAO,
        help="Caminho do banco SQLite."
    )

    argumentos = parser.parse_args()
    migrar(argumentos.banco)
