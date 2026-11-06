
from datetime import datetime, timedelta

from extensions import db


class Consulta(db.Model):
    __tablename__ = "consultas"

    DURACOES_PERMITIDAS = (30, 45, 60)

    id = db.Column(db.Integer, primary_key=True)

    pet_id = db.Column(
        db.Integer,
        db.ForeignKey("pets.id"),
        nullable=False
    )

    veterinario_id = db.Column(
        db.Integer,
        db.ForeignKey("veterinarios.id"),
        nullable=False
    )

    data = db.Column(db.Date, nullable=False)
    hora = db.Column(db.String(5), nullable=False)
    motivo = db.Column(db.String(255), nullable=True)

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Agendada"
    )

    duracao_minutos = db.Column(
        db.Integer,
        nullable=False,
        default=30,
        server_default="30"
    )

    pet = db.relationship(
        "Pet",
        backref=db.backref(
            "consultas",
            cascade="all, delete-orphan"
        )
    )

    veterinario = db.relationship(
        "Veterinario",
        backref=db.backref("consultas")
    )

    @property
    def hora_fim(self):
        inicio = datetime.strptime(self.hora, "%H:%M")
        fim = inicio + timedelta(minutes=self.duracao_minutos)

        return fim.strftime("%H:%M")

    def __repr__(self):
        return (
            f"<Consulta {self.id} - "
            f"Pet {self.pet_id} - "
            f"Vet {self.veterinario_id} - "
            f"{self.data} {self.hora} - "
            f"{self.duracao_minutos} min>"
        )
