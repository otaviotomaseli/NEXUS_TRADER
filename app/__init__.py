import logging
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app(config_name=None):
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
        static_url_path='/static',
    )

    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    from config import config_map
    app.config.from_object(config_map.get(config_name, config_map['default']))

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Faça login para acessar o sistema.'
    login_manager.login_message_category = 'error'

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.brasil import brasil_bp
    from app.routes.exterior import exterior_bp
    from app.routes.cripto import cripto_bp
    from app.routes.api import api_bp
    from app.routes.editar import editar_bp
    from app.routes.perfil import perfil_bp
    from app.routes.lgpd import lgpd_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(brasil_bp)
    app.register_blueprint(exterior_bp)
    app.register_blueprint(cripto_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(editar_bp)
    app.register_blueprint(perfil_bp)
    app.register_blueprint(lgpd_bp)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    with app.app_context():
        db.create_all()
        _aplicar_migracoes_legado(app)
        _criar_usuario_padrao(app)

    _garantir_pasta_avatares(app)

    from app import cli
    cli.init_app(app)

    _exibir_instrucoes_acesso(app)

    return app


def _aplicar_migracoes_legado(app):
    from sqlalchemy import text
    from app.models import Configuracao, Transacao, TransacaoExterior

    migracoes = [
        'ALTER TABLE configuracao ADD COLUMN isencao_cripto FLOAT DEFAULT 35000.0',
        'ALTER TABLE configuracao ADD COLUMN taxa_cripto FLOAT DEFAULT 0.15',
        'ALTER TABLE transacao ADD COLUMN banco VARCHAR(50) DEFAULT "Não Informado"',
        'ALTER TABLE transacao_exterior ADD COLUMN banco VARCHAR(50) DEFAULT "Não Informado"',
        'ALTER TABLE user ADD COLUMN avatar VARCHAR(255) DEFAULT NULL',
        'ALTER TABLE user ADD COLUMN data_cadastro DATETIME DEFAULT NULL',
        'ALTER TABLE user ADD COLUMN data_ultimo_login DATETIME DEFAULT NULL',
        'ALTER TABLE user ADD COLUMN lgpd_consentimento BOOLEAN DEFAULT 0',
        'ALTER TABLE user ADD COLUMN lgpd_consentimento_data DATETIME DEFAULT NULL',
        'ALTER TABLE user ADD COLUMN lgpd_dados_excluidos BOOLEAN DEFAULT 0',
    ]
    for sql in migracoes:
        try:
            db.session.execute(text(sql))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _criar_usuario_padrao(app):
    from app.models import User, Configuracao

    nome = os.getenv('DEFAULT_USERNAME', '')
    senha_hash = os.getenv('DEFAULT_PASSWORD_HASH', '')
    if not nome or not senha_hash:
        return

    if not User.query.filter_by(username=nome).first():
        from datetime import datetime, timezone
        agora = datetime.now(timezone.utc)
        u = User(username=nome, password=senha_hash, data_cadastro=agora)
        db.session.add(u)
        db.session.flush()
        db.session.add(Configuracao(user_id=u.id))
        db.session.commit()
        app.logger.warning('Usuário padrão "%s" criado a partir do .env. Altere a senha o quanto antes!', nome)


def _garantir_pasta_avatares(app):
    import os
    pasta = os.path.join(app.static_folder, 'avatars')
    os.makedirs(pasta, exist_ok=True)


def _exibir_instrucoes_acesso(app):
    nome = os.getenv('DEFAULT_USERNAME', '')
    tem_hash = bool(os.getenv('DEFAULT_PASSWORD_HASH', ''))
    if nome and tem_hash:
        app.logger.warning(
            '╔══════════════════════════════════════════════════════╗\n'
            '║        RECUPERAÇÃO DE ACESSO                        ║\n'
            '╠══════════════════════════════════════════════════════╣\n'
            '║ Usuário padrão configurado no arquivo .env:         ║\n'
            '║   Username: %-40s║\n'
            '║                                                      ║\n'
            '║ Se ESQUECEU a senha, use no terminal:                ║\n'
            '║   flask reset-senha SEU_USUARIO NOVA_SENHA           ║\n'
            '║                                                      ║\n'
            '║ Para criar um novo usuário:                          ║\n'
            '║   flask criar-usuario NOVO_USUARIO NOVA_SENHA        ║\n'
            '║                                                      ║\n'
            '║ Para listar usuários:                                ║\n'
            '║   flask listar-usuarios                              ║\n'
            '╚══════════════════════════════════════════════════════╝',
            nome,
        )
