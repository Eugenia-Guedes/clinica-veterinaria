from extensions import db


class Disponibilidade(db.Model):
    __tablename__ = "disponibilidades"
    __table_args__ = (
        db.UniqueConstraint(
            "veterinario_id", "dia_semana",
            name="uq_disponibilidade_veterinario_dia"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # TODO: quando o veterinario.py chegar, trocar por
    # db.ForeignKey("<tabela_do_veterinario>.id") com o nome exato da tabela
    veterinario_id = db.Column(db.Integer, nullable=False)
    dia_semana = db.Column(db.String(20), nullable=False)
    hora_inicio = db.Column(db.String(5), nullable=False)
    hora_fim = db.Column(db.String(5), nullable=False)

    def __repr__(self):
        return f"<Disponibilidade {self.veterinario_id} - {self.dia_semana}>"
