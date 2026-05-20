import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(64).hex())
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///nexus.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    DEBUG = False

    # Taxas padrão (usadas se o usuário não tiver config personalizada)
    ISENCAO_BR = 20000.0
    TAXA_SWING_BR = 0.15
    TAXA_DAY_BR = 0.20
    TAXA_FII_BR = 0.20
    TAXA_EXTERIOR = 0.15
    ISENCAO_CRIPTO = 35000.0
    TAXA_CRIPTO = 0.15


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
