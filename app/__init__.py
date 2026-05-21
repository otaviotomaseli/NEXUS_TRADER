import logging
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

# Instâncias globais das extensões Flask (inicializadas sem app)
db = SQLAlchemy()          # ORM para banco de dados
login_manager = LoginManager()  # Gerenciamento de sessão/autenticação
csrf = CSRFProtect()       # Proteção contra CSRF em formulários
migrate = Migrate()        # Migrações do banco (Flask-Migrate)


def create_app(config_name=None):
    """Factory da aplicação Flask.

    Cria, configura e retorna uma instância do Flask com todas as
    extensões, blueprints, comandos CLI e dados iniciais carregados.

    Args:
        config_name: Nome da configuração ('development', 'production').
                     Se None, lê da variável de ambiente FLASK_ENV.
    """
    app = Flask(
        __name__,
        template_folder='../templates',   # Caminho relativo aos templates
        static_folder='../static',        # Pasta de arquivos estáticos (CSS, JS)
        static_url_path='/static',        # URL pública para arquivos estáticos
    )

    # Define o nome da configuração: argumento > env var > 'default'
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    # Carrega as configurações do dicionário config_map (config.py)
    from config import config_map
    app.config.from_object(config_map.get(config_name, config_map['default']))

    # Inicializa cada extensão com a instância do app
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Configura a view de login e mensagens exibidas para usuários não autenticados
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Faça login para acessar o sistema.'
    login_manager.login_message_category = 'error'

    # Importa o modelo User (necessário para o user_loader abaixo)
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        """Callback do Flask-Login: carrega um usuário pelo ID."""
        return User.query.get(int(user_id))

    # Importa e registra todos os blueprints (módulos de rotas)
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

    # Configura o logging global da aplicação
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )

    # Dentro do contexto da aplicação, cria tabelas e aplica migrações legadas
    with app.app_context():
        db.create_all()              # Garante que todas as tabelas existam
        _aplicar_migracoes_legado(app)  # Migrações manuais (colunas que faltam)
        _criar_usuario_padrao(app)      # Cria admin se configurado no .env

    # Garante que a pasta de avatares exista no diretório static
    _garantir_pasta_avatares(app)

    # Registra os comandos CLI personalizados (criar-usuario, reset-senha, etc.)
    from app import cli
    cli.init_app(app)

    # Exibe instruções de recuperação de acesso no log se houver usuário padrão
    _exibir_instrucoes_acesso(app)

    return app


def _aplicar_migracoes_legado(app):
    """Aplica migrações SQL manuais em banco já existente.

    Necessário para adicionar colunas que foram criadas depois da
    criação inicial das tabelas. Ignora erros silenciosamente para
    colunas que já existem.
    """
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
            # Coluna provavelmente já existe — faz rollback e continua
            db.session.rollback()


def _criar_usuario_padrao(app):
    """Cria um usuário administrador inicial a partir de variáveis de ambiente.

    Lê DEFAULT_USERNAME e DEFAULT_PASSWORD_HASH do .env. Se estiverem
    definidos e o usuário ainda não existir, cria o registro no banco
    junto com uma Configuracão padrão.
    """
    from app.models import User, Configuracao

    nome = os.getenv('DEFAULT_USERNAME', '')
    senha_hash = os.getenv('DEFAULT_PASSWORD_HASH', '')
    # Só prossegue se ambas as variáveis estiverem preenchidas
    if not nome or not senha_hash:
        return

    # Verifica se o usuário já existe para evitar duplicidade
    if not User.query.filter_by(username=nome).first():
        from datetime import datetime, timezone
        agora = datetime.now(timezone.utc)
        u = User(username=nome, password=senha_hash, data_cadastro=agora)
        db.session.add(u)
        db.session.flush()  # Garante o ID antes de criar a Configuracao
        db.session.add(Configuracao(user_id=u.id))
        db.session.commit()
        app.logger.warning(
            'Usuário padrão "%s" criado a partir do .env. Altere a senha o quanto antes!',
            nome,
        )


def _garantir_pasta_avatares(app):
    """Cria o diretório de avatares em static/ se não existir."""
    import os
    pasta = os.path.join(app.static_folder, 'avatars')
    os.makedirs(pasta, exist_ok=True)


def _exibir_instrucoes_acesso(app):
    """Exibe instruções de recuperação de senha e criação de usuários no log.

    Mostra uma caixa de ajuda com comandos Flask-CLI sempre que um
    usuário padrão estiver configurado no .env.
    """
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
