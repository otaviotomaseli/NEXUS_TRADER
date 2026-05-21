import click
from flask.cli import with_appcontext


@click.command('criar-usuario')
@click.argument('username')
@click.argument('senha')
@with_appcontext
def criar_usuario(username, senha):
    """Cria um novo usuário com senha em texto plano (gera hash automaticamente)."""
    # Importações tardias para evitar circular imports
    from werkzeug.security import generate_password_hash
    from app import db
    from app.models import User, Configuracao

    # Verifica se o username já existe no banco
    if User.query.filter_by(username=username).first():
        click.echo(f'ERRO: Usuário "{username}" já existe.')
        return

    # Cria o usuário com a senha hasheada e sua configuração padrão
    u = User(username=username, password=generate_password_hash(senha))
    db.session.add(u)
    db.session.flush()          # Obtém o ID gerado para associar a Configuracao
    db.session.add(Configuracao(user_id=u.id))
    db.session.commit()
    click.echo(f'Usuário "{username}" criado com sucesso!')


@click.command('reset-senha')
@click.argument('username')
@click.argument('nova-senha')
@with_appcontext
def reset_senha(username, nova_senha):
    """Redefine a senha de um usuário existente."""
    from werkzeug.security import generate_password_hash
    from app import db
    from app.models import User

    # Busca o usuário pelo nome
    user = User.query.filter_by(username=username).first()
    if not user:
        click.echo(f'ERRO: Usuário "{username}" não encontrado.')
        return

    # Atualiza o campo password com o novo hash e persiste
    user.password = generate_password_hash(nova_senha)
    db.session.commit()
    click.echo(f'Senha do usuário "{username}" redefinida com sucesso!')


@click.command('listar-usuarios')
@with_appcontext
def listar_usuarios():
    """Lista todos os usuários cadastrados."""
    from app.models import User

    users = User.query.all()
    if not users:
        click.echo('Nenhum usuário cadastrado.')
        return

    click.echo('Usuários cadastrados:')
    for u in users:
        click.echo(f'  - {u.username}')


def init_app(app):
    """Registra os comandos CLI personalizados no objeto app do Flask."""
    app.cli.add_command(criar_usuario)
    app.cli.add_command(reset_senha)
    app.cli.add_command(listar_usuarios)
