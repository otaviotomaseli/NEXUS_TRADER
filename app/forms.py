from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, FloatField, IntegerField,
    SelectField, DateField, HiddenField, SubmitField,
)
from wtforms.validators import DataRequired, NumberRange, Optional


class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Acessar')


class CompraForm(FlaskForm):
    data = DateField('Data', validators=[DataRequired()])
    tipo = SelectField('Tipo', choices=[
        ('acao', 'Ações (B3)'),
        ('fii', 'Fundo Imobiliário (FII)'),
    ], validators=[DataRequired()])
    codigo = StringField('Ticker', validators=[DataRequired()])
    banco = StringField('Corretora', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    valor_total = FloatField('Total (R$)', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Registrar')


class VendaBRForm(FlaskForm):
    codigo = HiddenField(validators=[DataRequired()])
    tipo_ativo = HiddenField(validators=[DataRequired()])
    data = DateField('Data da Venda', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    valor_venda = FloatField('Valor Recebido (R$)', validators=[DataRequired(), NumberRange(min=0.01)])
    operacao = SelectField('Tipo', choices=[
        ('swing_trade', 'Swing Trade'),
        ('day_trade', 'Day Trade'),
    ], validators=[DataRequired()])
    submit = SubmitField('Vender')


class CompraUSForm(FlaskForm):
    data = DateField('Data', validators=[DataRequired()])
    tipo = SelectField('Tipo', choices=[
        ('stock', 'Stock (Ações)'),
        ('reit', 'REIT (Fundos)'),
    ], validators=[DataRequired()])
    codigo = StringField('Ticker', validators=[DataRequired()])
    banco = StringField('Corretora', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    valor_total = FloatField('Total Pago (US$)', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Registrar')


class VendaUSForm(FlaskForm):
    codigo = HiddenField(validators=[DataRequired()])
    tipo_ativo = HiddenField(validators=[DataRequired()])
    data = DateField('Data da Venda', validators=[DataRequired()])
    quantidade = IntegerField('Quantidade', validators=[DataRequired(), NumberRange(min=1)])
    valor_venda = FloatField('Valor Recebido (US$)', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Vender')


class CompraCriptoForm(FlaskForm):
    data = DateField('Data da Compra', validators=[DataRequired()])
    tipo = SelectField('Tipo', choices=[('cripto', 'Criptomoeda')])
    codigo = StringField('Símbolo', validators=[DataRequired()])
    banco = StringField('Exchange / Wallet', validators=[DataRequired()])
    quantidade = FloatField('Quantidade', validators=[DataRequired(), NumberRange(min=0.00000001)])
    valor_total = FloatField('Total Investido', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Aportar Moeda')


class VendaCriptoForm(FlaskForm):
    codigo = HiddenField(validators=[DataRequired()])
    tipo_ativo = HiddenField(validators=[DataRequired()])
    data = DateField('Data da Venda', validators=[DataRequired()])
    quantidade = FloatField('Quantidade', validators=[DataRequired(), NumberRange(min=0.00000001)])
    valor_venda = FloatField('Valor Recebido (R$)', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Vender')


class ConfiguracaoForm(FlaskForm):
    isencao_br = FloatField('Limite Isenção BR (R$)', validators=[Optional()])
    swing = FloatField('Imposto Swing Trade (%)', validators=[Optional()])
    day = FloatField('Imposto Day Trade (%)', validators=[Optional()])
    fii = FloatField('Imposto FII (%)', validators=[Optional()])
    exterior = FloatField('Imposto Exterior (%)', validators=[Optional()])
    isencao_cripto = FloatField('Limite Isenção Cripto (R$)', validators=[Optional()])
    taxa_cripto = FloatField('Imposto Cripto (%)', validators=[Optional()])
    submit = SubmitField('Salvar Parâmetros')
