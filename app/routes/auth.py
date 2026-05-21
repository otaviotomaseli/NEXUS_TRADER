"""Blueprint de autenticação — gerencia login, logout e rota raiz."""
from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash

from app import db
from app.models import User
from app.forms import LoginForm

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    """Redireciona a raiz para a tela de login."""
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Exibe e processa o formulário de login."""
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        # Busca o usuário pelo nome de usuário
        user = User.query.filter_by(username=username).first()
        # Verifica se o usuário existe e se a senha confere com o hash
        if user and check_password_hash(user.password, password):
            login_user(user)
            # Atualiza o timestamp do último login
            user.data_ultimo_login = datetime.now(timezone.utc)
            db.session.commit()
            return redirect(url_for('brasil.dashboard'))
        flash('Login ou senha inválidos', 'error')
    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Encerra a sessão do usuário e redireciona para o login."""
    logout_user()
    return redirect(url_for('auth.login'))
