
from pathlib import Path
from copy import deepcopy

import yaml


PASTA_DOCS = Path(__file__).resolve().parent / "docs"

MODULOS = {
    "usuarios.yaml": "Usuarios",
    "pets.yaml": "Pets",
    "veterinarios.yaml": "Veterinarios",
    "disponibilidade.yaml": "Disponibilidade",
    "consultas.yaml": "Consultas",
}


def carregar_yaml(nome_arquivo):
    caminho = PASTA_DOCS / nome_arquivo

    with caminho.open(encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def atualizar_referencias(objeto, referencias):
    if isinstance(objeto, dict):
        for chave, valor in objeto.items():
            if chave == "$ref" and isinstance(valor, str):
                objeto[chave] = referencias.get(valor, valor)
            else:
                atualizar_referencias(valor, referencias)

    elif isinstance(objeto, list):
        for item in objeto:
            atualizar_referencias(item, referencias)


def gerar_openapi():
    documento = carregar_yaml("openapi.yaml")

    documento.setdefault("paths", {})
    documento.setdefault("components", {})
    documento.setdefault("tags", [])

    for nome_arquivo, prefixo in MODULOS.items():
        modulo = deepcopy(carregar_yaml(nome_arquivo))

        referencias = {}
        componentes = modulo.get("components", {})

        # Identifica os componentes de cada modulo.
        for categoria, itens in componentes.items():
            for nome in itens:
                if categoria == "securitySchemes":
                    novo_nome = nome
                else:
                    novo_nome = f"{prefixo}_{nome}"

                referencia_original = (
                    f"#/components/{categoria}/{nome}"
                )

                nova_referencia = (
                    f"#/components/{categoria}/{novo_nome}"
                )

                referencias[referencia_original] = nova_referencia

        # Atualiza as referencias internas.
        atualizar_referencias(modulo, referencias)

        # Integra os componentes.
        for categoria, itens in componentes.items():
            destino = documento["components"].setdefault(
                categoria, {}
            )

            for nome, conteudo in itens.items():
                if categoria == "securitySchemes":
                    novo_nome = nome
                else:
                    novo_nome = f"{prefixo}_{nome}"

                if novo_nome in destino:
                    raise ValueError(
                        f"Componente duplicado: {novo_nome}"
                    )

                destino[novo_nome] = conteudo

        # Integra os endpoints.
        for caminho, operacoes in modulo.get("paths", {}).items():
            if caminho in documento["paths"]:
                raise ValueError(
                    f"Caminho duplicado: {caminho}"
                )

            documento["paths"][caminho] = operacoes

        # Integra as categorias do Swagger.
        tags_existentes = {
            tag["name"] for tag in documento["tags"]
        }

        for tag in modulo.get("tags", []):
            if tag["name"] not in tags_existentes:
                documento["tags"].append(tag)
                tags_existentes.add(tag["name"])

    return documento
