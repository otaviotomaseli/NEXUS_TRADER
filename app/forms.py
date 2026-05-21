# Módulo de formulários WTForms
# Define todos os formulários web utilizados nas views do Nexus Trader.

# FlaskForm — classe base para formulários Flask-WTF com proteção CSRF embutida
from flask_wtf import FlaskForm
# Tipos de campo WTForms: texto, senha, decimal, inteiro, dropdown, data, oculto e botão de envio
from wtforms import (
    StringField, PasswordField, FloatField, IntegerField,
    SelectField, DateField, HiddenField, SubmitField,
)
# Validadores: DataRequired (obrigatório), NumberRange (faixa numérica), Optional (pode ficar em branco)
from wtforms.validators import DataRequired, NumberRange, Optional


class LoginForm(FlaskForm):
    """
    Formulário de autenticação.
    Coleta usuário e senha para login no sistema.
    """
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    # Botão que envia as credenciais para autenticação no sistema
    submit = SubmitField('Acessar')


class CompraForm(FlaskForm):
    """
    Formulário de registro de compra de ativos nacionais (B3).
    Usado tanto para ações quanto para FIIs.
    """
    # Data em que a compra foi executada na B3
    data = DateField('Data', validators=[DataRequired()])
    # Tipo de ativo: ação ou FII — determina a alíquota de imposto aplicável no momento da venda
    tipo = SelectField('Tipo', choices=[
        ('acao', 'Ações (B3)'),
        ('fii', 'Fundo Imobiliário (FII)'),
    ], validators=[DataRequired()])
    # Código/ticker do ativo negociado (ex: PETR4, MXRF11)
    codigo = StringField('Ticker', validators=[DataRequired()])
    # Corretora responsável pela operação
    banco = StringField('Corretora', validators=[DataRequired()])
    # Quantidade de ativos comprados (mínimo 1, pois compras fracionadas não são suportadas para BR)
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    # Valor total pago na operação em reais (R$)
    valor_total = FloatField('Total (R$)', validators=[DataRequired(), NumberRange(min=0.01)])
    # Botão que persiste a compra no banco de dados e atualiza o portfolio
    submit = SubmitField('Registrar')


class VendaBRForm(FlaskForm):
    """
    Formulário de venda de ativos nacionais (B3).
    Utiliza campos ocultos para código e tipo do ativo,
    preenchidos dinamicamente pela interface.
    """
    # Código do ativo — campo oculto preenchido automaticamente pela interface ao selecionar o ativo no portfolio
    codigo = HiddenField(validators=[DataRequired()])
    # Tipo do ativo (acao/fii) — campo oculto herdado do contexto da venda na interface
    tipo_ativo = HiddenField(validators=[DataRequired()])
    data = DateField('Data da Venda', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    # Valor recebido com a venda (em reais)
    valor_venda = FloatField('Valor Recebido (R$)', validators=[DataRequired(), NumberRange(min=0.01)])
    # Classificação da operação: swing trade (15% de imposto) ou day trade (20% de imposto)
    operacao = SelectField('Tipo', choices=[
        ('swing_trade', 'Swing Trade'),
        ('day_trade', 'Day Trade'),
    ], validators=[DataRequired()])
    # Botão que dispara o cálculo de imposto devido e registra a venda
    submit = SubmitField('Vender')


class CompraUSForm(FlaskForm):
    """
    Formulário de registro de compra de ativos internacionais.
    Suporta stocks (ações) e REITs (fundos imobiliários americanos).
    """
    data = DateField('Data', validators=[DataRequired()])
    # Tipo de ativo no exterior: stock (ação americana) ou REIT (fundo imobiliário americano) — alíquotas diferentes se aplicam
    tipo = SelectField('Tipo', choices=[
        ('stock', 'Stock (Ações)'),
        ('reit', 'REIT (Fundos)'),
    ], validators=[DataRequired()])
    # Ticker do ativo na bolsa americana (ex: AAPL para Apple, O para Realty Income)
    codigo = StringField('Ticker', validators=[DataRequired()])
    # Corretora internacional utilizada para a compra
    banco = StringField('Corretora', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    # Valor total pago em dólares americanos (US$) — conversão cambial é feita separadamente
    valor_total = FloatField('Total Pago (US$)', validators=[DataRequired(), NumberRange(min=0.01)])
    # Botão que registra a aquisição internacional no portfolio do usuário
    submit = SubmitField('Registrar')


class VendaUSForm(FlaskForm):
    """
    Formulário de venda de ativos internacionais.
    O código e tipo do ativo são preenchidos automaticamente.
    """
    codigo = HiddenField(validators=[DataRequired()])
    tipo_ativo = HiddenField(validators=[DataRequired()])
    data = DateField('Data da Venda', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    # Valor recebido em dólares americanos (US$) — conversão cambial tratada no backend para apuração em R$
    valor_venda = FloatField('Valor Recebido (US$)', validators=[DataRequired(), NumberRange(min=0.01)])
    # Botão que registra a venda internacional e calcula o imposto devido no exterior
    submit = SubmitField('Vender')


class CompraCriptoForm(FlaskForm):
    """
    Formulário de registro de compra de criptomoedas.
    A quantidade aceita valores fracionados com alta precisão.
    """
    data = DateField('Data da Compra', validators=[DataRequired()])
    # Tipo fixo como 'cripto' — pode ser expandido para diferentes blockchains no futuro
    tipo = SelectField('Tipo', choices=[('cripto', 'Criptomoeda')])
    # Símbolo da criptomoeda (ex: BTC, ETH, SOL)
    codigo = StringField('Símbolo', validators=[DataRequired()])
    # Exchange ou wallet utilizada na operação
    banco = StringField('Exchange / Wallet', validators=[DataRequired()])
    # Quantidade fracionada (suporta até 8 casas decimais para frações de criptomoedas como 0.005 BTC)
    quantidade = FloatField('Quantidade', validators=[DataRequired(), NumberRange(min=0.00000001)])
    # Valor total investido na operação em reais (R$)
    valor_total = FloatField('Total Investido', validators=[DataRequired(), NumberRange(min=0.01)])
    # Botão que adiciona a criptomoeda ao portfolio do usuário
    submit = SubmitField('Aportar Moeda')


class VendaCriptoForm(FlaskForm):
    """
    Formulário de venda de criptomoedas.
    O código e tipo do ativo são preenchidos automaticamente.
    """
    codigo = HiddenField(validators=[DataRequired()])
    tipo_ativo = HiddenField(validators=[DataRequired()])
    data = DateField('Data da Venda', validators=[DataRequired()])
    # Quantidade fracionada vendida (aceita frações como 0.5 BTC)
    quantidade = FloatField('Quantidade', validators=[DataRequired(), NumberRange(min=0.00000001)])
    # Valor recebido em reais (R$) — conversão embutida no momento da venda
    valor_venda = FloatField('Valor Recebido (R$)', validators=[DataRequired(), NumberRange(min=0.01)])
    # Botão que registra a venda e calcula o ganho de capital em criptomoedas
    submit = SubmitField('Vender')


class ConfiguracaoForm(FlaskForm):
    """
    Formulário de parâmetros fiscais do usuário.
    Permite personalizar alíquotas e limites de isenção.
    Todos os campos são opcionais — valores em branco mantêm o padrão.
    """
    # Limite mensal de isenção para vendas na B3 (padrão: R$ 20.000,00)
    isencao_br = FloatField('Limite Isenção BR (R$)', validators=[Optional()])
    # Alíquota personalizada para swing trade em ações BR (padrão: 15%)
    swing = FloatField('Imposto Swing Trade (%)', validators=[Optional()])
    # Alíquota personalizada para day trade em ações BR (padrão: 20%)
    day = FloatField('Imposto Day Trade (%)', validators=[Optional()])
    # Alíquota personalizada para Fundos Imobiliários (padrão: 20%)
    fii = FloatField('Imposto FII (%)', validators=[Optional()])
    # Alíquota personalizada para operações no exterior (padrão: 15%)
    exterior = FloatField('Imposto Exterior (%)', validators=[Optional()])
    # Limite mensal de isenção para venda de criptomoedas (padrão: R$ 35.000,00)
    isencao_cripto = FloatField('Limite Isenção Cripto (R$)', validators=[Optional()])
    # Alíquota personalizada para ganho de capital em criptomoedas (padrão: 15%)
    taxa_cripto = FloatField('Imposto Cripto (%)', validators=[Optional()])
    # Botão que persiste todas as preferências fiscais no banco de dados
    submit = SubmitField('Salvar Parâmetros')
