import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()
# Se a SECRET_KEY não foi definida, carrega do .env.example como fallback
if not os.getenv('SECRET_KEY'):
    load_dotenv('.env.example', override=True)


class Config:
    """Configurações base da aplicação Nexus Trader.

    Define chaves de segurança, URI do banco de dados, CSRF,
    modo debug e as taxas/tributações padrão para cálculos de IR.
    """

    # Chave secreta para sessões Flask e tokens CSRF
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(64).hex())
    # URI de conexão com o banco de dados (SQLite como fallback)
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///nexus.db')
    # Desabilita notificações de modificação do SQLAlchemy (economia de memória)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Habilita proteção CSRF global para formulários Flask-WTF
    WTF_CSRF_ENABLED = True
    # Modo debug desligado por padrão (segurança em produção)
    DEBUG = False

    # Taxas padrão (usadas se o usuário não tiver config personalizada)
    ISENCAO_BR = 20000.0          # Isenção mensal para operações em bolsa BR (R$)
    TAXA_SWING_BR = 0.15          # Alíquota IR para swing trade BR (15%)
    TAXA_DAY_BR = 0.20            # Alíquota IR para day trade BR (20%)
    TAXA_FII_BR = 0.20            # Alíquota IR para FIIs BR (20%)
    TAXA_EXTERIOR = 0.15          # Alíquota IR para operações no exterior (15%)
    ISENCAO_CRIPTO = 35000.0      # Isenção mensal para venda de criptomoedas (R$)
    TAXA_CRIPTO = 0.15            # Alíquota IR para criptomoedas (15% sobre ganho de capital)


class DevelopmentConfig(Config):
    """Configuração para ambiente de desenvolvimento — debug ativado."""
    DEBUG = True


class ProductionConfig(Config):
    """Configuração para ambiente de produção — debug desativado."""
    DEBUG = False


# Mapeamento de nomes para classes de configuração, usado pelo create_app()
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
