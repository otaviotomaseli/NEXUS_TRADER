# Módulo de modelos do banco de dados (SQLAlchemy)
# Define as tabelas do sistema Nexus Trader: usuários, configurações e transações.

# datetime e timezone para registrar timestamps de criação, login e consentimento LGPD
from datetime import datetime, timezone

# UserMixin fornece os métodos de autenticação (is_authenticated, get_id) exigidos pelo Flask-Login, sem implementá-los manualmente
from flask_login import UserMixin
# Instância SQLAlchemy global (declarada em app/__init__.py), usada como base db.Model em todos os modelos
from app import db


class User(UserMixin, db.Model):
    """
    Modelo da tabela 'user'.
    Armazena dados de autenticação, perfil e conformidade LGPD de cada usuário.
    """
    # Identificador único do usuário (chave primária auto-incremento)
    id = db.Column(db.Integer, primary_key=True)
    # Nome de usuário único e obrigatório para login
    username = db.Column(db.String(150), unique=True, nullable=False)
    # Hash da senha (nunca armazenada em texto puro)
    password = db.Column(db.String(150), nullable=False)
    # Caminho ou URL do avatar do usuário (opcional)
    avatar = db.Column(db.String(255), nullable=True, default=None)
    # Data/hora do cadastro do usuário no sistema
    data_cadastro = db.Column(db.DateTime, nullable=True, default=None)
    # Data/hora do último login registrado
    data_ultimo_login = db.Column(db.DateTime, nullable=True, default=None)
    # Indica se o usuário consentiu com a política LGPD
    lgpd_consentimento = db.Column(db.Boolean, default=False)
    # Data/hora em que o consentimento LGPD foi dado
    lgpd_consentimento_data = db.Column(db.DateTime, nullable=True, default=None)
    # Marca se os dados do usuário foram excluídos conforme direito LGPD
    lgpd_dados_excluidos = db.Column(db.Boolean, default=False)


class Configuracao(db.Model):
    """
    Modelo da tabela 'configuracao'.
    Armazena as preferências fiscais e alíquotas personalizadas de cada usuário.
    """
    # Identificador único da configuração (chave primária auto-incremento)
    id = db.Column(db.Integer, primary_key=True)
    # Chave estrangeira vinculando cada configuração ao seu respectivo usuário (relação 1:1)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Limite de isenção mensal para vendas na B3 (padrão: R$ 20.000,00)
    isencao_br = db.Column(db.Float, default=20000.0)
    # Alíquota de imposto para Swing Trade B3 (padrão: 15%)
    taxa_swing_br = db.Column(db.Float, default=0.15)
    # Alíquota de imposto para Day Trade B3 (padrão: 20%)
    taxa_day_br = db.Column(db.Float, default=0.20)
    # Alíquota de imposto para FIIs (padrão: 20%)
    taxa_fii_br = db.Column(db.Float, default=0.20)
    # Alíquota de imposto para ativos no exterior (padrão: 15%)
    taxa_exterior = db.Column(db.Float, default=0.15)
    # Limite de isenção mensal para vendas de criptomoedas (padrão: R$ 35.000,00)
    isencao_cripto = db.Column(db.Float, default=35000.0)
    # Alíquota de imposto para criptomoedas (padrão: 15%)
    taxa_cripto = db.Column(db.Float, default=0.15)


class Transacao(db.Model):
    """
    Modelo da tabela 'transacao'.
    Registra operações de compra/venda de ativos nacionais (B3).
    Utilizada para apuração de Imposto de Renda na fonte.
    """
    # Identificador único da transação nacional (chave primária auto-incremento)
    id = db.Column(db.Integer, primary_key=True)
    # Chave estrangeira associando a transação ao usuário que realizou a operação
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Tipo do ativo: 'acao', 'fii', etc.
    tipo_ativo = db.Column(db.String(50), nullable=False)
    # Código/ticker do ativo (ex: PETR4, MXRF11)
    codigo = db.Column(db.String(20), nullable=False)
    # Tipo da transação: 'compra' ou 'venda'
    tipo_transacao = db.Column(db.String(20), nullable=False)
    # Quantidade de ativos negociada
    quantidade = db.Column(db.Integer, nullable=False)
    # Valor total da operação em R$
    valor_total = db.Column(db.Float, nullable=False)
    # Data da operação (formato string)
    data = db.Column(db.String(10), nullable=False)
    # Lucro ou prejuízo da operação (preenchido no fechamento)
    lucro_perda = db.Column(db.Float, default=0.0)
    # Imposto devido calculado para esta operação
    imposto = db.Column(db.Float, default=0.0)
    # Código DARF gerado ou '-' caso isento
    darf = db.Column(db.String(50), default='-')
    # Nome da corretora / banco utilizado
    banco = db.Column(db.String(50), default='Não Informado')


class TransacaoExterior(db.Model):
    """
    Modelo da tabela 'transacao_exterior'.
    Registra operações de compra/venda de ativos internacionais (stocks, REITs).
    Segue a mesma estrutura da Transacao nacional, porém com apuração separada.
    """
    # Identificador único da transação internacional (chave primária auto-incremento)
    id = db.Column(db.Integer, primary_key=True)
    # Chave estrangeira associando a transação exterior ao usuário dono da operação
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Tipo do ativo: 'stock', 'reit', etc.
    tipo_ativo = db.Column(db.String(50), nullable=False)
    # Ticker do ativo no exterior (ex: AAPL, O)
    codigo = db.Column(db.String(20), nullable=False)
    tipo_transacao = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    # Valor total em US$ (dólar americano)
    valor_total = db.Column(db.Float, nullable=False)
    data = db.Column(db.String(10), nullable=False)
    lucro_perda = db.Column(db.Float, default=0.0)
    imposto = db.Column(db.Float, default=0.0)
    darf = db.Column(db.String(50), default='-')
    banco = db.Column(db.String(50), default='Não Informado')


class TransacaoCripto(db.Model):
    """
    Modelo da tabela 'transacao_cripto'.
    Registra operações de compra/venda de criptomoedas.
    A quantidade é Float (diferente dos demais) devido às frações de criptomoedas.
    """
    # Identificador único da transação de criptomoeda (chave primária auto-incremento)
    id = db.Column(db.Integer, primary_key=True)
    # Chave estrangeira associando a transação de cripto ao usuário dono da operação
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tipo_ativo = db.Column(db.String(50), nullable=False)
    # Símbolo da criptomoeda (ex: BTC, ETH)
    codigo = db.Column(db.String(20), nullable=False)
    tipo_transacao = db.Column(db.String(20), nullable=False)
    # Quantidade (Float) suporta frações como 0.005 BTC
    quantidade = db.Column(db.Float, nullable=False)
    valor_total = db.Column(db.Float, nullable=False)
    data = db.Column(db.String(10), nullable=False)
    lucro_perda = db.Column(db.Float, default=0.0)
    imposto = db.Column(db.Float, default=0.0)
    darf = db.Column(db.String(50), default='-')
    banco = db.Column(db.String(50), default='Não Informado')
