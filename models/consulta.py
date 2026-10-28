from extensions import db


class Consulta(db.Model):
    __tablename__ = "consultas"

    id = db.Column(db.Integer, primary_key=True)
    pet_id = db.Column(db.Integer, db.ForeignKey("pets.id"), nullable=False)
    veterinario_id = db.Column(db.Integer, db.ForeignKey("veterinarios.id"), nullable=False)
    data = db.Column(db.Date, nullable=False)
    hora = db.Column(db.String(5), nullable=False)
    motivo = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Agendada")

    pet = db.relationship(
        "Pet",
        backref=db.backref("consultas", cascade="all, delete-orphan")
    )
    veterinario = db.relationship(
        "Veterinario",
        backref=db.backref("consultas", cascade="all, delete-orphan")
    )

    def __repr__(self):
        return f"<Consulta {self.id} - Pet {self.pet_id} - Vet {self.veterinario_id} - {self.data} {self.hora}>"
