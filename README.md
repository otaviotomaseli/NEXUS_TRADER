<p align="center">
  <img src="https://img.shields.io/badge/Flask-3.0-000?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Status-Conclu%C3%ADdo-green" alt="Status">
</p>

<h1 align="center">🚀 Nexus Trader (InvTrader)</h1>

<p align="center">
  <strong>Sistema completo de controle de investimentos</strong><br>
  B3 · Exterior (EUA) · Criptomoedas<br>
  Cálculo automático de impostos · Análise técnica · LGPD
</p>

---

## 📋 Sobre

O **Nexus Trader** é uma aplicação web desenvolvida em Flask que centraliza o gerenciamento da sua carteira de investimentos em um só lugar. Com ele, você acompanha ações brasileiras (B3), stocks americanos, REITs, FIIs e criptomoedas, com cálculo automático de imposto de renda e geração de DARF.

---

## ✨ Funcionalidades

### 📊 Dashboard Unificado
- Visão consolidada de **B3**, **Exterior (EUA)** e **Criptomoedas**
- Saldo atual, lucros realizados, prejuízos e rentabilidade em tempo real
- Status do mercado (aberto/fechado)

### 💰 Gestão de Carteira
- Registro de compras e vendas para cada mercado
- Preço médio ponderado automático
- Carteira ativa com saldo por ativo
- Edição e exclusão de transações

### 🧮 Imposto de Renda Automático
- **B3:** Swing trade (15%), Day trade (20%), FIIs (20%)
- **Exterior:** 15% sobre ganho de capital (provisão IRPF anual)
- **Criptomoedas:** Isenção até R$ 35.000/mês, 15% acima
- Geração de resumo de DARFs por mês
- Cálculo de data de vencimento

### 📈 Análise Técnica
- Gráfico interativo com Chart.js
- Suporte e resistência automáticos
- Cruzamento de médias SMA9/SMA21
- Sinais de compra e venda
- Suporte a B3 (.SA), EUA e criptomoedas

### 🔒 LGPD
- Política de privacidade integrada
- Consentimento registrado com data/hora
- Exportação de dados pessoais (JSON)
- Exclusão de conta com anonimização
- Transparência total sobre dados coletados

---

## 🛠️ Tecnologias

| Tecnologia | Finalidade |
|-----------|------------|
| **Flask 3.0** | Framework web |
| **SQLAlchemy 2.0** | ORM e banco de dados |
| **Flask-Login** | Autenticação de usuários |
| **Flask-WTF** | Formulários e proteção CSRF |
| **Werkzeug** | Hash de senhas (scrypt) |
| **yfinance** | Cotações de ações (Yahoo Finance) |
| **AwesomeAPI** | Câmbio e criptomoedas (BRL) |
| **Binance API** | Preços de criptomoedas |
| **Chart.js** | Gráficos interativos |
| **Pandas** | Análise de dados financeiros |

---

## 🚀 Como usar

### Pré-requisitos

- Python 3.12 ou superior
- pip

### Instalação

```bash
# Clone o repositório
git clone https://github.com/otaviotomaseli/NEXUS_TRADER.git
cd NEXUS_TRADER

# Configure o ambiente
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac

# Instale as dependências
pip install -r requirements.txt

# Execute
python run.py
```

Acesse em: **http://localhost:5000**

### Login padrão

| Campo | Valor |
|-------|-------|
| Usuário | `otavio` |
| Senha | Configurada no `.env` |

> ⚠️ Altere a senha após o primeiro acesso.

---

## 🗂️ Estrutura do Projeto

```
NEXUS_TRADER/
├── app/                          # Pacote principal
│   ├── __init__.py               # Factory create_app()
│   ├── models.py                 # Modelos SQLAlchemy
│   ├── forms.py                  # Formulários WTForms
│   ├── cli.py                    # Comandos Flask CLI
│   ├── routes/                   # Blueprints (controladores)
│   │   ├── auth.py               # Login/logout
│   │   ├── brasil.py             # B3 (dashboard, compra, venda)
│   │   ├── exterior.py           # EUA (compra, venda)
│   │   ├── cripto.py             # Criptomoedas
│   │   ├── api.py                # API de cotações e análise
│   │   ├── editar.py             # Edição de transações
│   │   ├── perfil.py             # Avatar / foto
│   │   └── lgpd.py               # Privacidade e LGPD
│   └── services/                 # Lógica de negócio
│       ├── carteira.py           # Processamento da carteira
│       ├── cotacao.py            # Consulta de preços
│       └── imposto.py            # Cálculo de impostos
├── templates/                    # Templates Jinja2
├── static/avatars/               # Uploads de avatar
├── config.py                     # Configurações do Flask
├── run.py                        # Ponto de entrada
├── requirements.txt              # Dependências
└── .env.example                  # Modelo de variáveis de ambiente
```

---

## 🔐 Segurança

- Senhas armazenadas com **hash scrypt** (mão única)
- **Proteção CSRF** em todos os formulários
- **Validação de entrada** em todas as rotas POST
- **Magic bytes** no upload de avatar (imagens reais apenas)
- **SSL/TLS** ativo em todas as chamadas a APIs externas
- **SECRET_KEY** gerenciada via variável de ambiente
- **DEBUG=False** em produção

---

## 📄 Licença

Distribuído sob licença **MIT**. Veja o arquivo `LICENSE` para mais detalhes.

---

<p align="center">
  Desenvolvido por <a href="https://github.com/otaviotomaseli">@otaviotomaseli</a>
</p>
