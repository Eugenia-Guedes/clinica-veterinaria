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
    veterinario_id = db.Column(db.Integer, db.ForeignKey("veterinarios.id"), nullable=False)
    dia_semana = db.Column(db.String(20), nullable=False)
    hora_inicio = db.Column(db.String(5), nullable=False)
    hora_fim = db.Column(db.String(5), nullable=False)

    def __repr__(self):
        return f"<Disponibilidade {self.veterinario_id} - {self.dia_semana}>"
