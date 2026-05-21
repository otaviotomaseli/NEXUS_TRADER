"""Blueprint de autenticação — gerencia login, logout e rota raiz."""
# Módulos da biblioteca padrão para manipulação de datas com timezone
from datetime import datetime, timezone

# Flask: ferramentas para rotas, templates, redirecionamento, mensagens e request
from flask import Blueprint, render_template, redirect, url_for, flash, request
# Flask-Login: gerencia sessão do usuário logado e protege rotas
from flask_login import login_user, logout_user, login_required
# Werkzeug: compara a senha fornecida com o hash armazenado no banco
from werkzeug.security import check_password_hash

# Instância do banco de dados e modelos da aplicação
from app import db
from app.models import User
# Formulário WTForms para a tela de login
from app.forms import LoginForm

# Cria o blueprint 'auth' para organizar as rotas de autenticação
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    """Redireciona a raiz para a tela de login."""
    # Qualquer acesso à raiz do site é redirecionado imediatamente para /login
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Exibe e processa o formulário de login."""
    # Cria instância do formulário de login (WTForms valida automaticamente)
    form = LoginForm()
    # Se a requisição for POST e os dados passarem na validação do formulário
    if form.validate_on_submit():
        # Extrai os campos de usuário e senha do formulário submetido
        username = form.username.data
        password = form.password.data
        # Busca o usuário pelo nome de usuário no banco de dados
        user = User.query.filter_by(username=username).first()
        # Verifica se o usuário existe e se a senha confere com o hash armazenado
        if user and check_password_hash(user.password, password):
            # Inicia a sessão do Flask-Login para o usuário encontrado
            login_user(user)
            # Atualiza o timestamp do último login para auditoria/histórico
            user.data_ultimo_login = datetime.now(timezone.utc)
            db.session.commit()
            # Redireciona para o dashboard principal (Brasil) após login bem-sucedido
            return redirect(url_for('brasil.dashboard'))
        # Se usuário não existe ou senha incorreta, exibe mensagem de erro
        flash('Login ou senha inválidos', 'error')
    # Em requisição GET (ou após erro) renderiza a página de login com o formulário
    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Encerra a sessão do usuário e redireciona para o login."""
    # Remove o usuário da sessão atual (Flask-Login)
    logout_user()
    # Redireciona de volta para a tela de login
    return redirect(url_for('auth.login'))
