from datetime import datetime, timezone

from flask_login import UserMixin
from app import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    avatar = db.Column(db.String(255), nullable=True, default=None)
    data_cadastro = db.Column(db.DateTime, nullable=True, default=None)
    data_ultimo_login = db.Column(db.DateTime, nullable=True, default=None)
    lgpd_consentimento = db.Column(db.Boolean, default=False)
    lgpd_consentimento_data = db.Column(db.DateTime, nullable=True, default=None)
    lgpd_dados_excluidos = db.Column(db.Boolean, default=False)


class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    isencao_br = db.Column(db.Float, default=20000.0)
    taxa_swing_br = db.Column(db.Float, default=0.15)
    taxa_day_br = db.Column(db.Float, default=0.20)
    taxa_fii_br = db.Column(db.Float, default=0.20)
    taxa_exterior = db.Column(db.Float, default=0.15)
    isencao_cripto = db.Column(db.Float, default=35000.0)
    taxa_cripto = db.Column(db.Float, default=0.15)


class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tipo_ativo = db.Column(db.String(50), nullable=False)
    codigo = db.Column(db.String(20), nullable=False)
    tipo_transacao = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    data = db.Column(db.String(10), nullable=False)
    lucro_perda = db.Column(db.Float, default=0.0)
    imposto = db.Column(db.Float, default=0.0)
    darf = db.Column(db.String(50), default='-')
    banco = db.Column(db.String(50), default='Não Informado')


class TransacaoExterior(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tipo_ativo = db.Column(db.String(50), nullable=False)
    codigo = db.Column(db.String(20), nullable=False)
    tipo_transacao = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    data = db.Column(db.String(10), nullable=False)
    lucro_perda = db.Column(db.Float, default=0.0)
    imposto = db.Column(db.Float, default=0.0)
    darf = db.Column(db.String(50), default='-')
    banco = db.Column(db.String(50), default='Não Informado')


class TransacaoCripto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tipo_ativo = db.Column(db.String(50), nullable=False)
    codigo = db.Column(db.String(20), nullable=False)
    tipo_transacao = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    data = db.Column(db.String(10), nullable=False)
    lucro_perda = db.Column(db.Float, default=0.0)
    imposto = db.Column(db.Float, default=0.0)
    darf = db.Column(db.String(50), default='-')
    banco = db.Column(db.String(50), default='Não Informado')
