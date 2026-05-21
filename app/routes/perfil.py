"""Rotas para gerenciamento de perfil do usuário, incluindo avatar."""

import os
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db

perfil_bp = Blueprint('perfil', __name__)

# Extensões de imagem permitidas para upload
EXTENSOES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
PASTA_AVATAR = 'avatars'


def extensao_ok(nome):
    """Verifica se a extensão do arquivo está na lista de formatos permitidos."""
    return '.' in nome and nome.rsplit('.', 1)[1].lower() in EXTENSOES


def magic_bytes_ok(arquivo):
    """Valida os bytes de cabeçalho para garantir que é uma imagem real."""
    inicio = arquivo.read(12)
    arquivo.seek(0)
    # JPEG: FF D8 FF
    if inicio[:3] == b'\xff\xd8\xff':
        return True
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if inicio[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    # GIF: GIF87a ou GIF89a
    if inicio[:6] in (b'GIF87a', b'GIF89a'):
        return True
    # WebP: RIFF .... WEBP
    if inicio[:4] == b'RIFF' and inicio[8:12] == b'WEBP':
        return True
    return False


@perfil_bp.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Faz upload e valida uma nova foto de perfil (avatar) para o usuário logado.

    Realiza validações consecutivas: presença do arquivo, extensão e
    magic bytes. Em caso de sucesso, salva com nome único e vincula ao usuário.
    """
    # Verifica se o campo 'avatar' existe no formulário
    if 'avatar' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('brasil.dashboard'))

    arquivo = request.files['avatar']

    # Verifica se o usuário selecionou um arquivo
    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Valida a extensão do arquivo
    if not extensao_ok(arquivo.filename):
        flash('Formato inválido. Use: PNG, JPG, GIF ou WebP.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Valida o conteúdo real através dos primeiros bytes
    if not magic_bytes_ok(arquivo):
        flash('Arquivo corrompido ou não é uma imagem válida.', 'error')
        return redirect(url_for('brasil.dashboard'))

    # Gera nome único para evitar colisão e sobrescrita
    nome_seguro = secure_filename(arquivo.filename)
    ext = nome_seguro.rsplit('.', 1)[1].lower()
    nome_arquivo = f'avatar_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}'
    caminho = os.path.join(current_app.static_folder, PASTA_AVATAR, nome_arquivo)

    # Garante que a pasta de destino existe e salva o arquivo
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    arquivo.save(caminho)

    # Atualiza o avatar do usuário no banco
    current_user.avatar = nome_arquivo
    db.session.commit()

    flash('Foto de perfil atualizada!', 'success')
    return redirect(url_for('brasil.dashboard'))


@perfil_bp.route('/remover_avatar', methods=['POST'])
@login_required
def remover_avatar():
    """Remove a foto de perfil do usuário logado, apagando o arquivo do disco."""
    if current_user.avatar:
        caminho = os.path.join(current_app.static_folder, PASTA_AVATAR, current_user.avatar)
        if os.path.exists(caminho):
            os.remove(caminho)
        current_user.avatar = None
        db.session.commit()
        flash('Foto de perfil removida.', 'success')
    return redirect(url_for('brasil.dashboard'))
