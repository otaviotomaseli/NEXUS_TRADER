"""Rotas LGPD — privacidade, consentimento, exportação e exclusão de dados."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user, logout_user

from app import db
from app.models import User, Configuracao, Transacao, TransacaoExterior, TransacaoCripto

logger = logging.getLogger(__name__)
lgpd_bp = Blueprint('lgpd', __name__)


@lgpd_bp.route('/privacidade')
def privacidade():
    """Exibe a página pública de política de privacidade."""
    return render_template('privacidade.html')


@lgpd_bp.route('/lgpd/termos', methods=['POST'])
@login_required
def aceitar_termos():
    """Registra o aceite do usuário aos termos de privacidade (LGPD)."""
    current_user.lgpd_consentimento = True
    current_user.lgpd_consentimento_data = datetime.now(timezone.utc)
    db.session.commit()
    flash('Termos de privacidade aceitos com sucesso.', 'success')
    return redirect(url_for('brasil.dashboard'))


@lgpd_bp.route('/lgpd/minha-conta')
@login_required
def minha_conta():
    """Exibe a página de gerenciamento de conta com total de registros armazenados."""
    qtd_transacoes = Transacao.query.filter_by(user_id=current_user.id).count()
    qtd_us = TransacaoExterior.query.filter_by(user_id=current_user.id).count()
    qtd_cripto = TransacaoCripto.query.filter_by(user_id=current_user.id).count()
    total_registros = qtd_transacoes + qtd_us + qtd_cripto
    return render_template('minha-conta.html', total_registros=total_registros)


@lgpd_bp.route('/lgpd/exportar')
@login_required
def exportar_dados():
    """Exporta todos os dados pessoais do usuário em formato JSON (portabilidade LGPD)."""
    # Estrutura base com dados do perfil do usuário
    dados = {
        'usuario': {
            'username': current_user.username,
            'data_cadastro': current_user.data_cadastro.isoformat() if current_user.data_cadastro else None,
            'ultimo_login': current_user.data_ultimo_login.isoformat() if current_user.data_ultimo_login else None,
            'possui_avatar': current_user.avatar is not None,
            'lgpd_consentimento': current_user.lgpd_consentimento,
            'lgpd_consentimento_data': current_user.lgpd_consentimento_data.isoformat() if current_user.lgpd_consentimento_data else None,
        },
        'configuracao': [],
        'transacoes_br': [],
        'transacoes_us': [],
        'transacoes_cripto': [],
    }

    # Adiciona as configurações fiscais do usuário
    conf = Configuracao.query.filter_by(user_id=current_user.id).first()
    if conf:
        dados['configuracao'].append({
            'isencao_br': conf.isencao_br,
            'taxa_swing_br': conf.taxa_swing_br,
            'taxa_day_br': conf.taxa_day_br,
            'taxa_fii_br': conf.taxa_fii_br,
            'taxa_exterior': conf.taxa_exterior,
            'isencao_cripto': conf.isencao_cripto,
            'taxa_cripto': conf.taxa_cripto,
        })

    # Exporta as transações do mercado brasileiro
    for t in Transacao.query.filter_by(user_id=current_user.id).all():
        dados['transacoes_br'].append({
            'id': t.id, 'tipo_ativo': t.tipo_ativo, 'codigo': t.codigo,
            'tipo_transacao': t.tipo_transacao, 'quantidade': t.quantidade,
            'valor_total': t.valor_total, 'data': t.data,
            'lucro_perda': t.lucro_perda, 'imposto': t.imposto,
            'darf': t.darf, 'banco': t.banco,
        })

    # Exporta as transações do exterior (EUA)
    for t in TransacaoExterior.query.filter_by(user_id=current_user.id).all():
        dados['transacoes_us'].append({
            'id': t.id, 'tipo_ativo': t.tipo_ativo, 'codigo': t.codigo,
            'tipo_transacao': t.tipo_transacao, 'quantidade': t.quantidade,
            'valor_total': t.valor_total, 'data': t.data,
            'lucro_perda': t.lucro_perda, 'imposto': t.imposto,
            'darf': t.darf, 'banco': t.banco,
        })

    # Exporta as transações de criptomoedas
    for t in TransacaoCripto.query.filter_by(user_id=current_user.id).all():
        dados['transacoes_cripto'].append({
            'id': t.id, 'tipo_ativo': t.tipo_ativo, 'codigo': t.codigo,
            'tipo_transacao': t.tipo_transacao, 'quantidade': t.quantidade,
            'valor_total': t.valor_total, 'data': t.data,
            'lucro_perda': t.lucro_perda, 'imposto': t.imposto,
            'darf': t.darf, 'banco': t.banco,
        })

    return jsonify(dados, ensure_ascii=False), 200, {'Content-Disposition': 'attachment; filename=meus_dados.json'}


@lgpd_bp.route('/lgpd/excluir', methods=['POST'])
@login_required
def excluir_conta():
    """Exclui permanentemente a conta e todos os dados associados (direito ao esquecimento LGPD).

    Remove configurações e transações, anonimiza o usuário e encerra a sessão.
    """
    # Exige consentimento prévio para prosseguir com a exclusão
    if not current_user.lgpd_consentimento:
        flash('Você precisa aceitar os termos de privacidade antes de gerenciar sua conta.', 'error')
        return redirect(url_for('lgpd.minha_conta'))

    uid = current_user.id

    # Remove todos os registros relacionados ao usuário
    Configuracao.query.filter_by(user_id=uid).delete()
    Transacao.query.filter_by(user_id=uid).delete()
    TransacaoExterior.query.filter_by(user_id=uid).delete()
    TransacaoCripto.query.filter_by(user_id=uid).delete()

    # Remove o avatar do disco se existir
    if current_user.avatar:
        import os
        from flask import current_app
        caminho = os.path.join(current_app.static_folder, 'avatars', current_user.avatar)
        if os.path.exists(caminho):
            os.remove(caminho)

    # Anonimiza o registro do usuário (não deleta da tabela para integridade referencial)
    current_user.username = f'usuario_excluido_{uid}'
    current_user.password = ''
    current_user.avatar = None
    current_user.data_cadastro = None
    current_user.data_ultimo_login = None
    current_user.lgpd_consentimento = False
    current_user.lgpd_consentimento_data = None
    current_user.lgpd_dados_excluidos = True

    db.session.commit()

    # Encerra a sessão e redireciona para o login
    logout_user()
    flash('Sua conta e todos os dados associados foram excluídos permanentemente.', 'success')
    return redirect(url_for('auth.login'))
