from extensions import db


class Pet(db.Model):
    __tablename__ = "pets"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    especie = db.Column(db.String(50), nullable=False)
    raca = db.Column(db.String(100))
    sexo = db.Column(db.String(20), nullable=False)
    data_nascimento = db.Column(db.Date)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    tutor = db.relationship(
        "Usuario",
        backref=db.backref("pets", cascade="all, delete-orphan")
    )

    def __repr__(self):
        return f"<Pet {self.nome}>"