import os
import uuid
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db

perfil_bp = Blueprint('perfil', __name__)

EXTENSOES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
PASTA_AVATAR = 'avatars'

def extensao_ok(nome):
    return '.' in nome and nome.rsplit('.', 1)[1].lower() in EXTENSOES

def magic_bytes_ok(arquivo):
    inicio = arquivo.read(12)
    arquivo.seek(0)
    if inicio[:3] == b'\xff\xd8\xff':
        return True
    if inicio[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    if inicio[:6] in (b'GIF87a', b'GIF89a'):
        return True
    if inicio[:4] == b'RIFF' and inicio[8:12] == b'WEBP':
        return True
    return False

@perfil_bp.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('brasil.dashboard'))

    arquivo = request.files['avatar']

    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('brasil.dashboard'))

    if not extensao_ok(arquivo.filename):
        flash('Formato inválido. Use: PNG, JPG, GIF ou WebP.', 'error')
        return redirect(url_for('brasil.dashboard'))

    if not magic_bytes_ok(arquivo):
        flash('Arquivo corrompido ou não é uma imagem válida.', 'error')
        return redirect(url_for('brasil.dashboard'))

    nome_seguro = secure_filename(arquivo.filename)
    ext = nome_seguro.rsplit('.', 1)[1].lower()
    nome_arquivo = f'avatar_{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}'
    caminho = os.path.join(current_app.static_folder, PASTA_AVATAR, nome_arquivo)

    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    arquivo.save(caminho)

    current_user.avatar = nome_arquivo
    db.session.commit()

    flash('Foto de perfil atualizada!', 'success')
    return redirect(url_for('brasil.dashboard'))

@perfil_bp.route('/remover_avatar', methods=['POST'])
@login_required
def remover_avatar():
    if current_user.avatar:
        caminho = os.path.join(current_app.static_folder, PASTA_AVATAR, current_user.avatar)
        if os.path.exists(caminho):
            os.remove(caminho)
        current_user.avatar = None
        db.session.commit()
        flash('Foto de perfil removida.', 'success')
    return redirect(url_for('brasil.dashboard'))
