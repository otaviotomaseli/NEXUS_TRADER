import os
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy 
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import text 
import calendar
import yfinance as yf
import requests 
import pandas as pd

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(64).hex())
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nexus.db'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def status_mercado(pais):
    agora_brt = datetime.utcnow() - timedelta(hours=3)
    if pais == 'CRIPTO':
        return "ABERTO (24/7)"
    dia_semana = agora_brt.weekday()
    if dia_semana >= 5: 
        return "FECHADO"
    hora_atual = agora_brt.strftime('%H:%M')
    if pais == 'BR':
        if '10:00' <= hora_atual <= '17:00': return "ABERTO"
    elif pais == 'US':
        if '10:30' <= hora_atual <= '17:00': return "ABERTO"
    return "FECHADO"

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login ou senha inválidos', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()
    mercado_br = status_mercado('BR')
    mercado_us = status_mercado('US')
    mercado_cripto = status_mercado('CRIPTO')
    
    # PROCESSAMENTO BRASIL
    transacoes = Transacao.query.filter_by(user_id=current_user.id).order_by(Transacao.id).all()
    carteira = {}; vendas_realizadas = []; compras_realizadas = []
    for t in transacoes:
        if t.tipo_transacao == 'Compra': compras_realizadas.append(t)
        if t.codigo not in carteira: carteira[t.codigo] = {'tipo_ativo': t.tipo_ativo, 'quantidade': 0, 'custo_total': 0.0, 'banco': 'Vários'}
        if t.tipo_transacao == 'Compra':
            carteira[t.codigo]['tipo_ativo'] = t.tipo_ativo
            carteira[t.codigo]['banco'] = getattr(t, 'banco', 'Não Informado')
            carteira[t.codigo]['quantidade'] += t.quantidade
            carteira[t.codigo]['custo_total'] += t.valor_total
        elif t.tipo_transacao == 'Venda':
            pm = carteira[t.codigo]['custo_total'] / carteira[t.codigo]['quantidade'] if carteira[t.codigo]['quantidade'] > 0 else 0
            carteira[t.codigo]['quantidade'] -= t.quantidade
            carteira[t.codigo]['custo_total'] -= (t.quantidade * pm)
            vendas_realizadas.append(t)
            
    carteira_ativa = {k: v for k, v in carteira.items() if v['quantidade'] > 0}
    saldo_atual_b3 = 0.0
    for k, v in carteira_ativa.items():
        v['preco_medio'] = v['custo_total'] / v['quantidade'] if v['quantidade'] > 0 else 0
        try:
            hist = yf.Ticker(f"{k}.SA").history(period="1d")
            v['preco_atual'] = float(hist['Close'].iloc[-1]) if not hist.empty else v['preco_medio']
        except: v['preco_atual'] = v['preco_medio'] 
        v['valor_atual'] = v['quantidade'] * v['preco_atual']
        v['lucro_aberto'] = v['valor_atual'] - v['custo_total']
        v['rentabilidade_pct'] = (v['lucro_aberto'] / v['custo_total'] * 100) if v['custo_total'] > 0 else 0
        saldo_atual_b3 += v['valor_atual']
        
    for v in vendas_realizadas:
        if v.imposto > 0:
            y, m, d = map(int, v.data.split('-'))
            y_v, m_v = (y+1, 1) if m == 12 else (y, m+1)
            _, last = calendar.monthrange(y_v, m_v)
            v.vencimento_darf = f"{last:02d}/{m_v:02d}/{y_v}"
        else: v.vencimento_darf = "-"

    anos_br = sorted(list(set(t.data.split('-')[0] for t in transacoes)), reverse=True)
    resumo_darfs_br = {}
    for v in vendas_realizadas:
        mes_ano = v.data[:7] 
        if mes_ano not in resumo_darfs_br:
            y, m = map(int, mes_ano.split('-'))
            y_v, m_v = (y+1, 1) if m == 12 else (y, m+1)
            _, last = calendar.monthrange(y_v, m_v)
            resumo_darfs_br[mes_ano] = {'mes': f"{m:02d}/{y}", 'ano_mes_ordem': mes_ano, 'lucro_total': 0.0, 'imposto_total': 0.0, 'vencimento': f"{last:02d}/{m_v:02d}/{y_v}"}
        resumo_darfs_br[mes_ano]['lucro_total'] += v.lucro_perda
        if v.imposto > 0: resumo_darfs_br[mes_ano]['imposto_total'] += v.imposto
    lista_darfs_br = sorted([d for d in resumo_darfs_br.values() if d['imposto_total'] > 0], key=lambda x: x['ano_mes_ordem'], reverse=True)

    # PROCESSAMENTO EXTERIOR
    transacoes_us = TransacaoExterior.query.filter_by(user_id=current_user.id).order_by(TransacaoExterior.id).all()
    carteira_us = {}; vendas_us = []; compras_us = []
    for t in transacoes_us:
        if t.tipo_transacao == 'Compra': compras_us.append(t)
        if t.codigo not in carteira_us: carteira_us[t.codigo] = {'tipo_ativo': t.tipo_ativo, 'quantidade': 0, 'custo_total': 0.0, 'banco': 'Vários'}
        if t.tipo_transacao == 'Compra':
            carteira_us[t.codigo]['tipo_ativo'] = t.tipo_ativo
            carteira_us[t.codigo]['banco'] = getattr(t, 'banco', 'Não Informado')
            carteira_us[t.codigo]['quantidade'] += t.quantidade
            carteira_us[t.codigo]['custo_total'] += t.valor_total
        elif t.tipo_transacao == 'Venda':
            pm = carteira_us[t.codigo]['custo_total'] / carteira_us[t.codigo]['quantidade'] if carteira_us[t.codigo]['quantidade'] > 0 else 0
            carteira_us[t.codigo]['quantidade'] -= t.quantidade
            carteira_us[t.codigo]['custo_total'] -= (t.quantidade * pm)
            vendas_us.append(t)
            
    carteira_ativa_us = {k: v for k, v in carteira_us.items() if v['quantidade'] > 0}
    saldo_atual_us = 0.0
    for k, v in carteira_ativa_us.items():
        v['preco_medio'] = v['custo_total'] / v['quantidade'] if v['quantidade'] > 0 else 0
        try:
            hist = yf.Ticker(k).history(period="1d")
            v['preco_atual'] = float(hist['Close'].iloc[-1]) if not hist.empty else v['preco_medio']
        except: v['preco_atual'] = v['preco_medio']
        v['valor_atual'] = v['quantidade'] * v['preco_atual']
        v['lucro_aberto'] = v['valor_atual'] - v['custo_total']
        v['rentabilidade_pct'] = (v['lucro_aberto'] / v['custo_total'] * 100) if v['custo_total'] > 0 else 0
        saldo_atual_us += v['valor_atual']

    anos_us = sorted(list(set(t.data.split('-')[0] for t in transacoes_us)), reverse=True)
    resumo_impostos_us = {}
    for v in vendas_us:
        ano = v.data[:4] 
        if ano not in resumo_impostos_us:
            resumo_impostos_us[ano] = {'ano': ano, 'lucro_total': 0.0, 'imposto_total': 0.0, 'vencimento': f"Na Declaração IRPF {int(ano)+1}"}
        resumo_impostos_us[ano]['lucro_total'] += v.lucro_perda
        if v.imposto > 0: resumo_impostos_us[ano]['imposto_total'] += v.imposto
    lista_impostos_us = sorted([d for d in resumo_impostos_us.values() if d['imposto_total'] > 0], key=lambda x: x['ano'], reverse=True)

    # PROCESSAMENTO CRIPTOMOEDAS
    transacoes_cripto = TransacaoCripto.query.filter_by(user_id=current_user.id).order_by(TransacaoCripto.id).all()
    carteira_cripto = {}; vendas_cripto = []; compras_cripto = []
    for t in transacoes_cripto:
        if t.tipo_transacao == 'Compra': compras_cripto.append(t)
        if t.codigo not in carteira_cripto: carteira_cripto[t.codigo] = {'tipo_ativo': t.tipo_ativo, 'quantidade': 0.0, 'custo_total': 0.0, 'banco': 'Vários'}
        if t.tipo_transacao == 'Compra':
            carteira_cripto[t.codigo]['tipo_ativo'] = t.tipo_ativo
            carteira_cripto[t.codigo]['banco'] = getattr(t, 'banco', 'Não Informado')
            carteira_cripto[t.codigo]['quantidade'] += t.quantidade
            carteira_cripto[t.codigo]['custo_total'] += t.valor_total
        elif t.tipo_transacao == 'Venda':
            pm = carteira_cripto[t.codigo]['custo_total'] / carteira_cripto[t.codigo]['quantidade'] if carteira_cripto[t.codigo]['quantidade'] > 0 else 0
            carteira_cripto[t.codigo]['quantidade'] -= t.quantidade
            carteira_cripto[t.codigo]['custo_total'] -= (t.quantidade * pm)
            vendas_cripto.append(t)
            
    carteira_ativa_cripto = {k: v for k, v in carteira_cripto.items() if v['quantidade'] > 0.00000001}
    saldo_atual_cripto = 0.0
    for k, v in carteira_ativa_cripto.items():
        v['preco_medio'] = v['custo_total'] / v['quantidade'] if v['quantidade'] > 0 else 0
        
        # --- A NOVA CACHOEIRA DE APIs PARA CRIPTOMOEDAS ---
        preco_encontrado = False
        
        # 1. Tenta AwesomeAPI para pares em Real
        if k.endswith('-BRL'):
            try:
                res = requests.get(f"https://economia.awesomeapi.com.br/last/{k}", timeout=2)
                if res.status_code == 200:
                    v['preco_atual'] = float(res.json()[k.replace('-', '')]['bid'])
                    preco_encontrado = True
            except: pass
            
        # 2. Tenta Binance
        if not preco_encontrado:
            try:
                symbol = k.replace('-', '')
                if symbol.endswith('USD') and not symbol.endswith('USDT'): symbol += 'T'
                res = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=2)
                if res.status_code == 200:
                    v['preco_atual'] = float(res.json()['price'])
                    preco_encontrado = True
            except: pass
            
        # 3. Tenta Yahoo Finance Direto
        if not preco_encontrado:
            try:
                hist = yf.Ticker(k).history(period="1d")
                if not hist.empty:
                    v['preco_atual'] = float(hist['Close'].iloc[-1])
                    preco_encontrado = True
            except: pass
            
        # 4. Fallback Matemático Especial (Para Moedas Delistadas como Monero)
        if not preco_encontrado and k.endswith('-BRL'):
            try:
                base = k.split('-')[0]
                hist_usd = yf.Ticker(f"{base}-USD").history(period="1d")
                res_usd = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL", timeout=2)
                if not hist_usd.empty and res_usd.status_code == 200:
                    usd_brl = float(res_usd.json()['USDBRL']['bid'])
                    v['preco_atual'] = float(hist_usd['Close'].iloc[-1]) * usd_brl
                    preco_encontrado = True
            except: pass
            
        if not preco_encontrado:
            v['preco_atual'] = v['preco_medio'] # Se tudo der errado, congela no preço médio
            
        v['valor_atual'] = v['quantidade'] * v['preco_atual']
        v['lucro_aberto'] = v['valor_atual'] - v['custo_total']
        v['rentabilidade_pct'] = (v['lucro_aberto'] / v['custo_total'] * 100) if v['custo_total'] > 0 else 0
        saldo_atual_cripto += v['valor_atual']

    anos_cripto = sorted(list(set(t.data.split('-')[0] for t in transacoes_cripto)), reverse=True)
    resumo_darfs_cripto = {}
    for v in vendas_cripto:
        mes_ano = v.data[:7] 
        if mes_ano not in resumo_darfs_cripto:
            y, m = map(int, mes_ano.split('-'))
            y_v, m_v = (y+1, 1) if m == 12 else (y, m+1)
            _, last = calendar.monthrange(y_v, m_v)
            resumo_darfs_cripto[mes_ano] = {'mes': f"{m:02d}/{y}", 'ano_mes_ordem': mes_ano, 'lucro_total': 0.0, 'imposto_total': 0.0, 'vencimento': f"{last:02d}/{m_v:02d}/{y_v}"}
        resumo_darfs_cripto[mes_ano]['lucro_total'] += v.lucro_perda
        if v.imposto > 0: resumo_darfs_cripto[mes_ano]['imposto_total'] += v.imposto
    lista_darfs_cripto = sorted([d for d in resumo_darfs_cripto.values() if d['imposto_total'] > 0], key=lambda x: x['ano_mes_ordem'], reverse=True)

    # Consolidações
    total_investido = sum(v['custo_total'] for v in carteira_ativa.values())
    total_lucro_realizado = sum(v.lucro_perda for v in vendas_realizadas if v.lucro_perda > 0)
    total_perda_realizada = sum(v.lucro_perda for v in vendas_realizadas if v.lucro_perda < 0)
    
    total_investido_us = sum(v['custo_total'] for v in carteira_ativa_us.values())
    total_lucro_realizado_us = sum(v.lucro_perda for v in vendas_us if v.lucro_perda > 0)
    total_perda_realizada_us = sum(v.lucro_perda for v in vendas_us if v.lucro_perda < 0)

    total_investido_cripto = sum(v['custo_total'] for v in carteira_ativa_cripto.values())
    total_lucro_realizado_cripto = sum(v.lucro_perda for v in vendas_cripto if v.lucro_perda > 0)
    total_perda_realizada_cripto = sum(v.lucro_perda for v in vendas_cripto if v.lucro_perda < 0)

    return render_template('dashboard.html', nome=current_user.username, conf=conf,
                           mercado_br=mercado_br, mercado_us=mercado_us, mercado_cripto=mercado_cripto,
                           carteira=carteira_ativa, compras=compras_realizadas, anos_br=anos_br, lista_darfs_br=lista_darfs_br, 
                           total_investido=total_investido, saldo_atual_b3=saldo_atual_b3, lucro_aberto_total_br=saldo_atual_b3-total_investido, total_lucro_realizado=total_lucro_realizado, total_perda_realizada=total_perda_realizada,
                           carteira_us=carteira_ativa_us, compras_us=compras_us, anos_us=anos_us, lista_impostos_us=lista_impostos_us, 
                           total_investido_us=total_investido_us, saldo_atual_us=saldo_atual_us, lucro_aberto_total_us=saldo_atual_us-total_investido_us, total_lucro_realizado_us=total_lucro_realizado_us, total_perda_realizada_us=total_perda_realizada_us,
                           carteira_cripto=carteira_ativa_cripto, compras_cripto=compras_cripto, anos_cripto=anos_cripto, lista_darfs_cripto=lista_darfs_cripto,
                           total_investido_cripto=total_investido_cripto, saldo_atual_cripto=saldo_atual_cripto, lucro_aberto_total_cripto=saldo_atual_cripto-total_investido_cripto, total_lucro_realizado_cripto=total_lucro_realizado_cripto, total_perda_realizada_cripto=total_perda_realizada_cripto)

@app.route('/salvar_config', methods=['POST'])
@login_required
def salvar_config():
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()
    conf.isencao_br = float(request.form.get('isencao'))
    conf.taxa_swing_br = float(request.form.get('swing')) / 100
    conf.taxa_day_br = float(request.form.get('day')) / 100
    conf.taxa_fii_br = float(request.form.get('fii')) / 100
    conf.taxa_exterior = float(request.form.get('exterior')) / 100
    conf.isencao_cripto = float(request.form.get('isencao_cripto'))
    conf.taxa_cripto = float(request.form.get('taxa_cripto')) / 100
    db.session.commit()
    flash('Configurações atualizadas com sucesso!', 'success')
    return redirect(url_for('dashboard'))

# ============== ROTAS BRASIL ==============
@app.route('/comprar', methods=['POST'])
@login_required
def comprar():
    if status_mercado('BR') == 'FECHADO':
        flash('MERCADO FECHADO: Não é possível comprar na B3 agora.', 'error')
        return redirect(url_for('dashboard'))
    nova_compra = Transacao(user_id=current_user.id, tipo_ativo=request.form.get('tipo'), codigo=request.form.get('codigo').upper(), tipo_transacao='Compra',
                            quantidade=int(request.form.get('quantidade')), valor_total=float(request.form.get('valor_compra')), data=request.form.get('data_compra'), banco=request.form.get('banco'))
    db.session.add(nova_compra); db.session.commit(); flash('Compra registrada!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/vender', methods=['POST'])
@login_required
def vender():
    if status_mercado('BR') == 'FECHADO':
        flash('MERCADO FECHADO: Não é possível vender na B3 agora.', 'error')
        return redirect(url_for('dashboard'))
    codigo = request.form.get('codigo'); tipo_ativo = request.form.get('tipo_ativo'); qtd_vendida = int(request.form.get('quantidade')); valor_venda = float(request.form.get('valor_venda'))
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()
    transacoes = Transacao.query.filter_by(user_id=current_user.id, codigo=codigo).all()
    qtd_atual = 0; custo_atual = 0.0
    for t in transacoes:
        if t.tipo_transacao == 'Compra': qtd_atual += t.quantidade; custo_atual += t.valor_total
        else: pm = custo_atual / qtd_atual if qtd_atual > 0 else 0; qtd_atual -= t.quantidade; custo_atual -= (t.quantidade * pm)
    pm_venda = custo_atual / qtd_atual if qtd_atual > 0 else 0
    lucro = valor_venda - (qtd_vendida * pm_venda); imposto = 0.0; darf = "Isento"
    if lucro > 0:
        if tipo_ativo == 'fii': imposto = lucro * conf.taxa_fii_br; darf = f"DARF {int(conf.taxa_fii_br*100)}%"
        else:
            if request.form.get('operacao') == 'day_trade': imposto = lucro * conf.taxa_day_br; darf = f"DARF {int(conf.taxa_day_br*100)}%"
            elif valor_venda <= conf.isencao_br: darf = "Isento"
            else: imposto = lucro * conf.taxa_swing_br; darf = f"DARF {int(conf.taxa_swing_br*100)}%"
    nova_venda = Transacao(user_id=current_user.id, tipo_ativo=tipo_ativo, codigo=codigo, tipo_transacao='Venda',
                           quantidade=qtd_vendida, valor_total=valor_venda, data=request.form.get('data_venda'), lucro_perda=lucro, imposto=imposto, darf=darf)
    db.session.add(nova_venda); db.session.commit(); flash('Venda realizada!', 'success')
    return redirect(url_for('dashboard'))

# ============== ROTAS EXTERIOR ==============
@app.route('/comprar_us', methods=['POST'])
@login_required
def comprar_us():
    if status_mercado('US') == 'FECHADO':
        flash('MERCADO FECHADO: Não é possível comprar nos EUA agora.', 'error')
        return redirect(url_for('dashboard'))
    nova_compra_us = TransacaoExterior(user_id=current_user.id, tipo_ativo=request.form.get('tipo'), codigo=request.form.get('codigo').upper(), tipo_transacao='Compra',
                                       quantidade=int(request.form.get('quantidade')), valor_total=float(request.form.get('valor_compra')), data=request.form.get('data_compra'), banco=request.form.get('banco'))
    db.session.add(nova_compra_us); db.session.commit(); flash('Compra EUA registrada!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/vender_us', methods=['POST'])
@login_required
def vender_us():
    if status_mercado('US') == 'FECHADO':
        flash('MERCADO FECHADO: Não é possível vender nos EUA agora.', 'error')
        return redirect(url_for('dashboard'))
    codigo = request.form.get('codigo'); tipo_ativo = request.form.get('tipo_ativo'); qtd_vendida = int(request.form.get('quantidade')); valor_venda = float(request.form.get('valor_venda'))
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()
    transacoes = TransacaoExterior.query.filter_by(user_id=current_user.id, codigo=codigo).all()
    qtd_atual = 0; custo_atual = 0.0
    for t in transacoes:
        if t.tipo_transacao == 'Compra': qtd_atual += t.quantidade; custo_atual += t.valor_total
        else: pm = custo_atual / qtd_atual if qtd_atual > 0 else 0; qtd_atual -= t.quantidade; custo_atual -= (t.quantidade * pm)
    pm_venda = custo_atual / qtd_atual if qtd_atual > 0 else 0
    lucro = valor_venda - (qtd_vendida * pm_venda); imposto = 0.0; darf = "Prejuízo"
    if lucro > 0: imposto = lucro * conf.taxa_exterior; darf = f"Provisão {int(conf.taxa_exterior*100)}%"
    nova_venda_us = TransacaoExterior(user_id=current_user.id, tipo_ativo=tipo_ativo, codigo=codigo, tipo_transacao='Venda',
                                      quantidade=qtd_vendida, valor_total=valor_venda, data=request.form.get('data_venda'), lucro_perda=lucro, imposto=imposto, darf=darf)
    db.session.add(nova_venda_us); db.session.commit(); flash('Venda EUA realizada!', 'success')
    return redirect(url_for('dashboard'))

# ============== ROTAS CRIPTOMOEDAS ==============
@app.route('/comprar_cripto', methods=['POST'])
@login_required
def comprar_cripto():
    nova_compra_cripto = TransacaoCripto(user_id=current_user.id, tipo_ativo=request.form.get('tipo'), codigo=request.form.get('codigo').upper(), tipo_transacao='Compra',
                                         quantidade=float(request.form.get('quantidade')), valor_total=float(request.form.get('valor_compra')), data=request.form.get('data_compra'), banco=request.form.get('banco'))
    db.session.add(nova_compra_cripto); db.session.commit(); flash('Compra de Criptomoeda registrada!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/vender_cripto', methods=['POST'])
@login_required
def vender_cripto():
    codigo = request.form.get('codigo'); tipo_ativo = request.form.get('tipo_ativo'); qtd_vendida = float(request.form.get('quantidade')); valor_venda = float(request.form.get('valor_venda'))
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()
    transacoes = TransacaoCripto.query.filter_by(user_id=current_user.id, codigo=codigo).all()
    qtd_atual = 0.0; custo_atual = 0.0
    for t in transacoes:
        if t.tipo_transacao == 'Compra': qtd_atual += t.quantidade; custo_atual += t.valor_total
        else: pm = custo_atual / qtd_atual if qtd_atual > 0 else 0; qtd_atual -= t.quantidade; custo_atual -= (t.quantidade * pm)
    pm_venda = custo_atual / qtd_atual if qtd_atual > 0 else 0
    lucro = valor_venda - (qtd_vendida * pm_venda); imposto = 0.0; darf = "Isento"
    if lucro > 0:
        if valor_venda <= conf.isencao_cripto: darf = "Isento (< 35k)"
        else: imposto = lucro * conf.taxa_cripto; darf = f"DARF {int(conf.taxa_cripto*100)}%"
    nova_venda_cripto = TransacaoCripto(user_id=current_user.id, tipo_ativo=tipo_ativo, codigo=codigo, tipo_transacao='Venda',
                                        quantidade=qtd_vendida, valor_total=valor_venda, data=request.form.get('data_venda'), lucro_perda=lucro, imposto=imposto, darf=darf)
    db.session.add(nova_venda_cripto); db.session.commit(); flash('Venda de Criptomoeda realizada!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/excluir_cripto/<int:id>')
@login_required
def excluir_cripto(id):
    t = TransacaoCripto.query.get(id)
    if t and t.user_id == current_user.id: db.session.delete(t); db.session.commit(); flash('Lançamento Cripto excluído.', 'success')
    return redirect(request.referrer or url_for('dashboard'))

# ================= ROTA DE COTAÇÃO SEGURA E CASCATA =================
@app.route('/api/cotacao/<ticker>')
@login_required
def api_cotacao(ticker):
    ticker_busca = ticker.upper().strip()
    preco_encontrado = False
    
    # 1. Tenta AwesomeAPI para BRL
    if ticker_busca.endswith('-BRL'):
        try:
            r = requests.get(f"https://economia.awesomeapi.com.br/last/{ticker_busca}", timeout=3)
            if r.status_code == 200:
                data = r.json()
                key = ticker_busca.replace('-', '')
                if key in data:
                    return {"preco": float(data[key]['bid'])}
        except: pass

    # 2. Tenta Binance (Funciona pra USDT e outros que passaram batido no 1)
    if '-' in ticker_busca:
        try:
            symbol = ticker_busca.replace('-', '')
            if symbol.endswith('USD') and not symbol.endswith('USDT'):
                symbol += 'T'
            r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=3)
            if r.status_code == 200:
                return {"preco": float(r.json()['price'])}
        except: pass
            
    # 3. Tenta Yahoo Finance (Ações normais e algumas moedas como XMR-USD)
    try:
        hist = yf.Ticker(ticker_busca).history(period="1d")
        if not hist.empty:
            preco = float(hist['Close'].iloc[-1])
            if preco > 0: return {"preco": preco}
    except: pass

    # 4. MÁGICA: Fallback matemático (Ex: Pegar XMR-USD no Yahoo e multiplicar pelo Dólar do BC)
    if ticker_busca.endswith('-BRL'):
        try:
            base_coin = ticker_busca.split('-')[0]
            # Preço da Moeda em Dólar no Yahoo
            hist_coin = yf.Ticker(f"{base_coin}-USD").history(period="1d")
            preco_usd = float(hist_coin['Close'].iloc[-1])
            
            # Preço do Dólar Hoje na AwesomeAPI
            r_usd = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL", timeout=3)
            dolar_brl = float(r_usd.json()['USDBRL']['bid'])
            
            preco_final = preco_usd * dolar_brl
            if preco_final > 0:
                return {"preco": preco_final}
        except: pass

    return {"preco": 0.0, "error": "Ativo não encontrado"}

# ================= ROTA DE ANÁLISE TÉCNICA (CAMUFLADA CONTRA BLOQUEIOS) =================
@app.route('/api/analise/<pais>/<ticker>/<periodo>')
@login_required
def api_analise(pais, ticker, periodo):
    ticker_busca = ticker.upper().strip()
    ticker_db = ticker_busca 
    
    try:
        dates = []; prices = []; highs = []; lows = []
        
        if pais == 'CRIPTO':
            if '-' not in ticker_busca: ticker_busca += '-BRL'
            
            days_map = {'1mo': 30, '2mo': 60, '3mo': 90, '4mo': 120, '5mo': 150, '6mo': 180}
            limit = days_map.get(periodo, 180)
            
            # MOTOR 1: AWESOME API
            if ticker_busca.endswith('-BRL'):
                try:
                    r_aws = requests.get(f"https://economia.awesomeapi.com.br/json/daily/{ticker_busca}/{limit}", timeout=5)
                    if r_aws.status_code == 200:
                        data_aws = r_aws.json()
                        data_aws.reverse() 
                        for candle in data_aws:
                            dt = datetime.fromtimestamp(int(candle['timestamp'])).strftime('%d-%m-%Y')
                            dates.append(dt)
                            prices.append(round(float(candle['bid']), 2))
                            highs.append(float(candle['high']))
                            lows.append(float(candle['low']))
                except: pass
            
            # MOTOR 2: BINANCE COM DISFARCE
            if not dates:
                symbol = ticker_busca.replace('-', '')
                if symbol.endswith('USD') and not symbol.endswith('USDT'): symbol += 'T'
                
                headers = {'User-Agent': 'Mozilla/5.0'}
                r_bin = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}", headers=headers, timeout=5)
                
                if r_bin.status_code == 200:
                    data_bin = r_bin.json()
                    for candle in data_bin:
                        dt = datetime.fromtimestamp(candle[0]/1000).strftime('%d-%m-%Y')
                        dates.append(dt)
                        prices.append(round(float(candle[4]), 2))
                        highs.append(float(candle[2]))
                        lows.append(float(candle[1]))

            if not dates:
                return {"error": "A corretora global bloqueou o acesso ou o ativo não existe."}
                
            resistance = round(max(highs), 2)
            support = round(min(lows), 2)
            
        else: 
            # Ações Tradicionais continuam no Yahoo
            if pais == 'BR' and not ticker_busca.endswith('.SA'): ticker_busca += '.SA'
                
            stock = yf.Ticker(ticker_busca)
            hist = stock.history(period=periodo)
            
            if hist.empty: return {"error": "Ativo não encontrado na base de dados global."}
                
            dates = hist.index.strftime('%d-%m-%Y').tolist()
            prices = [round(float(p), 2) for p in hist['Close'].tolist()]
            resistance = round(float(max(hist['High'])), 2)
            support = round(float(min(hist['Low'])), 2)
            
        df = pd.DataFrame({'Close': prices})
        sma9 = df['Close'].rolling(window=9).mean()
        sma21 = df['Close'].rolling(window=21).mean()
        
        buy_signals = []; sell_signals = []
        
        if len(prices) > 21:
            for i in range(21, len(prices)):
                if sma9.iloc[i] > sma21.iloc[i] and sma9.iloc[i-1] <= sma21.iloc[i-1]:
                    buy_signals.append({"x": dates[i], "y": prices[i]})
                elif sma9.iloc[i] < sma21.iloc[i] and sma9.iloc[i-1] >= sma21.iloc[i-1]:
                    sell_signals.append({"x": dates[i], "y": prices[i]})
                    
        user_purchases = []
        if pais == 'BR': compras_bd = Transacao.query.filter_by(user_id=current_user.id, codigo=ticker_db, tipo_transacao='Compra').all()
        elif pais == 'US': compras_bd = TransacaoExterior.query.filter_by(user_id=current_user.id, codigo=ticker_db, tipo_transacao='Compra').all()
        elif pais == 'CRIPTO': compras_bd = TransacaoCripto.query.filter_by(user_id=current_user.id, codigo=ticker_db, tipo_transacao='Compra').all()

        for c in compras_bd:
            y, m, d = c.data.split('-')
            data_formatada = f"{d}-{m}-{y}"
            preco_pago = round(c.valor_total / c.quantidade, 2) if c.quantidade > 0 else 0
            if data_formatada in dates:
                user_purchases.append({"x": data_formatada, "y": preco_pago})
                
        return { "dates": dates, "prices": prices, "support": support, "resistance": resistance, "buy_signals": buy_signals, "sell_signals": sell_signals, "user_purchases": user_purchases, "ticker": ticker_db }
    except Exception as e:
        return {"error": "Erro interno do servidor. Tente novamente mais tarde."}

@app.route('/excluir_br/<int:id>')
@login_required
def excluir_br(id):
    t = Transacao.query.get(id)
    if t and t.user_id == current_user.id: db.session.delete(t); db.session.commit(); flash('Lançamento excluído.', 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/excluir_us/<int:id>')
@login_required
def excluir_us(id):
    t = TransacaoExterior.query.get(id)
    if t and t.user_id == current_user.id: db.session.delete(t); db.session.commit(); flash('Lançamento excluído.', 'success')
    return redirect(request.referrer or url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        try:
            db.session.execute(text('ALTER TABLE configuracao ADD COLUMN isencao_cripto FLOAT DEFAULT 35000.0'))
            db.session.execute(text('ALTER TABLE configuracao ADD COLUMN taxa_cripto FLOAT DEFAULT 0.15'))
            db.session.commit()
        except: pass
        try:
            db.session.execute(text('ALTER TABLE transacao ADD COLUMN banco VARCHAR(50) DEFAULT "Não Informado"'))
            db.session.execute(text('ALTER TABLE transacao_exterior ADD COLUMN banco VARCHAR(50) DEFAULT "Não Informado"'))
            db.session.commit()
        except: pass 
            
        nome = os.getenv('DEFAULT_USERNAME', '')
        senha_hash = os.getenv('DEFAULT_PASSWORD_HASH', '')
        if nome and senha_hash and not User.query.filter_by(username=nome).first():
            u = User(username=nome, password=senha_hash)
            db.session.add(u); db.session.commit(); db.session.add(Configuracao(user_id=u.id)); db.session.commit()
    app.run()