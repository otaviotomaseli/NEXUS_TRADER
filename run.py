import os
# Importa a factory que monta e configura toda a aplicação Flask (extensões, blueprints, migrações, banco)
from app import create_app

# Cria a instância da aplicação: lê FLASK_ENV das variáveis de ambiente (development/production), ou usa 'development' como padrão
app = create_app(os.getenv('FLASK_ENV', 'development'))

# Ponto de entrada do servidor: só executa quando run.py é chamado diretamente (não ao ser importado por outro módulo)
if __name__ == '__main__':
    # Inicia o servidor de desenvolvimento Flask embutido (não usar em produção — usar Gunicorn, Waitress ou uvicorn)
    app.run()
