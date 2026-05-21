import os
# Importa a factory da aplicação Flask
from app import create_app

# Cria a instância da aplicação com o ambiente configurado (dev/prod)
# Lê FLASK_ENV das variáveis de ambiente, ou usa 'development' como padrão
app = create_app(os.getenv('FLASK_ENV', 'development'))

# Ponto de entrada: só executa o servidor se este arquivo for chamado diretamente
if __name__ == '__main__':
    app.run()
