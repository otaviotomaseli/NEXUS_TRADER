# Módulo de formulários WTForms
# Define todos os formulários web utilizados nas views do Nexus Trader.

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, FloatField, IntegerField,
    SelectField, DateField, HiddenField, SubmitField,
)
from wtforms.validators import DataRequired, NumberRange, Optional


class LoginForm(FlaskForm):
    """
    Formulário de autenticação.
    Coleta usuário e senha para login no sistema.
    """
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Acessar')


class CompraForm(FlaskForm):
    """
    Formulário de registro de compra de ativos nacionais (B3).
    Usado tanto para ações quanto para FIIs.
    """
    data = DateField('Data', validators=[DataRequired()])
    tipo = SelectField('Tipo', choices=[
        ('acao', 'Ações (B3)'),
        ('fii', 'Fundo Imobiliário (FII)'),
    ], validators=[DataRequired()])
    codigo = StringField('Ticker', validators=[DataRequired()])
    # Corretora responsável pela operação
    banco = StringField('Corretora', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    valor_total = FloatField('Total (R$)', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Registrar')


class VendaBRForm(FlaskForm):
    """
    Formulário de venda de ativos nacionais (B3).
    Utiliza campos ocultos para código e tipo do ativo,
    preenchidos dinamicamente pela interface.
    """
    codigo = HiddenField(validators=[DataRequired()])
    tipo_ativo = HiddenField(validators=[DataRequired()])
    data = DateField('Data da Venda', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    valor_venda = FloatField('Valor Recebido (R$)', validators=[DataRequired(), NumberRange(min=0.01)])
    # Classificação da operação para cálculo de alíquota
    operacao = SelectField('Tipo', choices=[
        ('swing_trade', 'Swing Trade'),
        ('day_trade', 'Day Trade'),
    ], validators=[DataRequired()])
    submit = SubmitField('Vender')


class CompraUSForm(FlaskForm):
    """
    Formulário de registro de compra de ativos internacionais.
    Suporta stocks (ações) e REITs (fundos imobiliários americanos).
    """
    data = DateField('Data', validators=[DataRequired()])
    tipo = SelectField('Tipo', choices=[
        ('stock', 'Stock (Ações)'),
        ('reit', 'REIT (Fundos)'),
    ], validators=[DataRequired()])
    codigo = StringField('Ticker', validators=[DataRequired()])
    banco = StringField('Corretora', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    # Valor em dólares americanos (US$)
    valor_total = FloatField('Total Pago (US$)', validators=[DataRequired(), NumberRange(min=0.01)])
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
    # Valor recebido em dólares americanos
    valor_venda = FloatField('Valor Recebido (US$)', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Vender')


class CompraCriptoForm(FlaskForm):
    """
    Formulário de registro de compra de criptomoedas.
    A quantidade aceita valores fracionados com alta precisão.
    """
    data = DateField('Data da Compra', validators=[DataRequired()])
    tipo = SelectField('Tipo', choices=[('cripto', 'Criptomoeda')])
    codigo = StringField('Símbolo', validators=[DataRequired()])
    # Exchange ou wallet utilizada na operação
    banco = StringField('Exchange / Wallet', validators=[DataRequired()])
    quantidade = FloatField('Quantidade', validators=[DataRequired(), NumberRange(min=0.00000001)])
    valor_total = FloatField('Total Investido', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Aportar Moeda')


class VendaCriptoForm(FlaskForm):
    """
    Formulário de venda de criptomoedas.
    O código e tipo do ativo são preenchidos automaticamente.
    """
    codigo = HiddenField(validators=[DataRequired()])
    tipo_ativo = HiddenField(validators=[DataRequired()])
    data = DateField('Data da Venda', validators=[DataRequired()])
    quantidade = FloatField('Quantidade', validators=[DataRequired(), NumberRange(min=0.00000001)])
    # Valor recebido em reais (conversão considerada no momento da venda)
    valor_venda = FloatField('Valor Recebido (R$)', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Vender')


class ConfiguracaoForm(FlaskForm):
    """
    Formulário de parâmetros fiscais do usuário.
    Permite personalizar alíquotas e limites de isenção.
    Todos os campos são opcionais — valores em branco mantêm o padrão.
    """
    isencao_br = FloatField('Limite Isenção BR (R$)', validators=[Optional()])
    swing = FloatField('Imposto Swing Trade (%)', validators=[Optional()])
    day = FloatField('Imposto Day Trade (%)', validators=[Optional()])
    fii = FloatField('Imposto FII (%)', validators=[Optional()])
    exterior = FloatField('Imposto Exterior (%)', validators=[Optional()])
    isencao_cripto = FloatField('Limite Isenção Cripto (R$)', validators=[Optional()])
    taxa_cripto = FloatField('Imposto Cripto (%)', validators=[Optional()])
    submit = SubmitField('Salvar Parâmetros')
