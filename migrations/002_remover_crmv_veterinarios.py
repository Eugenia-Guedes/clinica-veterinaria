import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
BANCO_PADRAO = BASE_DIR / "instance" / "clinica.db"

COLUNAS_ANTIGAS = {
    "id",
    "nome",
    "crmv",
    "especialidade",
}

COLUNAS_NOVAS = {
    "id",
    "nome",
    "especialidade",
}


def obter_colunas(conexao):
    return {
        coluna[1]
        for coluna in conexao.execute(
            "PRAGMA table_info(veterinarios)"
        )
    }


def verificar_integridade(conexao):
    resultado = conexao.execute(
        "PRAGMA integrity_check"
    ).fetchone()

    return resultado[0] == "ok"


def criar_backup(banco):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    backup = banco.with_name(
        f"{banco.stem}_backup_antes_remover_crmv_{timestamp}{banco.suffix}"
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

    # Primeira verificação: estrutura e integridade.
    conexao = sqlite3.connect(banco)

    try:
        if not verificar_integridade(conexao):
            raise RuntimeError(
                "O banco apresenta problemas de integridade."
            )

        colunas = obter_colunas(conexao)

        if not colunas:
            raise RuntimeError(
                "Tabela veterinarios não encontrada."
            )

        if colunas == COLUNAS_NOVAS:
            print(
                "O banco já não possui CRMV. "
                "Nenhuma alteração foi realizada."
            )
            return

        if colunas != COLUNAS_ANTIGAS:
            raise RuntimeError(
                f"Estrutura inesperada na tabela veterinarios: {colunas}"
            )

        tabela_temporaria = conexao.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name = 'veterinarios_nova'
        """).fetchone()

        if tabela_temporaria:
            raise RuntimeError(
                "A tabela temporária veterinarios_nova já existe. "
                "Migração cancelada."
            )

        objetos_adicionais = conexao.execute("""
            SELECT type, name
            FROM sqlite_master
            WHERE tbl_name = 'veterinarios'
            AND type IN ('index', 'trigger')
            AND sql IS NOT NULL
        """).fetchall()

        if objetos_adicionais:
            raise RuntimeError(
                "Foram encontrados índices ou gatilhos adicionais. "
                f"Migração cancelada para preservar a estrutura: "
                f"{objetos_adicionais}"
            )

        erros = conexao.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if erros:
            raise RuntimeError(
                f"O banco já apresenta problemas de relacionamento: {erros}"
            )

        quantidade_original = conexao.execute(
            "SELECT COUNT(*) FROM veterinarios"
        ).fetchone()[0]

    finally:
        conexao.close()

    # Segunda etapa: criar e validar backup automático.
    backup = criar_backup(banco)

    backup_conexao = sqlite3.connect(backup)

    try:
        if not verificar_integridade(backup_conexao):
            raise RuntimeError(
                "O backup apresentou problemas de integridade."
            )

        if obter_colunas(backup_conexao) != COLUNAS_ANTIGAS:
            raise RuntimeError(
                "A estrutura do backup não corresponde à esperada."
            )

        quantidade_backup = backup_conexao.execute(
            "SELECT COUNT(*) FROM veterinarios"
        ).fetchone()[0]

        if quantidade_backup != quantidade_original:
            raise RuntimeError(
                "A quantidade de registros do backup não corresponde "
                "à original."
            )

    finally:
        backup_conexao.close()

    print(f"Backup criado com sucesso: {backup}")

    # Terceira etapa: reconstruir a tabela dentro de uma transação.
    conexao = sqlite3.connect(banco)

    try:
        # Deve ser executado antes de iniciar a transação.
        conexao.execute("PRAGMA foreign_keys = OFF")

        if conexao.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0] != 0:
            raise RuntimeError(
                "Não foi possível desativar as chaves estrangeiras."
            )

        conexao.execute("BEGIN IMMEDIATE")

        # Confere novamente a estrutura antes da alteração.
        if obter_colunas(conexao) != COLUNAS_ANTIGAS:
            raise RuntimeError(
                "A estrutura do banco mudou. Migração cancelada."
            )

        conexao.execute("""
            CREATE TABLE veterinarios_nova (
                id INTEGER NOT NULL,
                nome VARCHAR(100) NOT NULL,
                especialidade VARCHAR(60) NOT NULL,
                PRIMARY KEY (id)
            )
        """)

        conexao.execute("""
            INSERT INTO veterinarios_nova (
                id,
                nome,
                especialidade
            )
            SELECT
                id,
                nome,
                especialidade
            FROM veterinarios
        """)

        quantidade_nova = conexao.execute(
            "SELECT COUNT(*) FROM veterinarios_nova"
        ).fetchone()[0]

        if quantidade_original != quantidade_nova:
            raise RuntimeError(
                "A quantidade de veterinários não foi preservada."
            )

        conexao.execute(
            "DROP TABLE veterinarios"
        )

        conexao.execute("""
            ALTER TABLE veterinarios_nova
            RENAME TO veterinarios
        """)

        # Verifica se os relacionamentos continuam válidos.
        erros = conexao.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if erros:
            raise RuntimeError(
                f"Problemas de relacionamento encontrados: {erros}"
            )

        # Verifica a integridade física do banco.
        if not verificar_integridade(conexao):
            raise RuntimeError(
                "Falha na verificação de integridade após a migração."
            )

        conexao.commit()

        print("\nMIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("Veterinários preservados:", quantidade_nova)
        print("Colunas finais:", obter_colunas(conexao))
        print("Integridade:", conexao.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0])
        print("Chaves estrangeiras:", conexao.execute(
            "PRAGMA foreign_key_check"
        ).fetchall())

    except Exception:
        if conexao.in_transaction:
            conexao.rollback()

        raise

    finally:
        conexao.execute("PRAGMA foreign_keys = ON")
        conexao.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migração para remover o CRMV dos veterinários."
    )

    parser.add_argument(
        "--banco",
        type=Path,
        default=BANCO_PADRAO,
        help="Caminho do banco SQLite. Por padrão: instance/clinica.db"
    )

    argumentos = parser.parse_args()

    migrar(argumentos.banco)