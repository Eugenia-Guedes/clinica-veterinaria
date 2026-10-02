from extensions import db


class Veterinario(db.Model):
    __tablename__ = "veterinarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    crmv = db.Column(db.String(20), unique=True, nullable=False)
    especialidade = db.Column(db.String(60), nullable=False)

    def __repr__(self):
        return f"<Veterinario {self.nome}>"