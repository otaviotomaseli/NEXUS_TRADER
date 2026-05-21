# Módulo de cálculo de impostos sobre operações na bolsa (IRRF)
# Contém as funções que calculam o IR devido para cada categoria de ativo: BR (ações/FIIs), exterior (US) e criptomoedas.


def calcular_imposto_venda_br(lucro, valor_venda, tipo_ativo, operacao, conf):
    """
    Calcula o imposto devido na venda de ativos nacionais (B3).

    Regras:
    - FIIs: alíquota fixa sobre o lucro (taxa_fii_br).
    - Day trade: alíquota de 20% (taxa_day_br) sobre o lucro, sem isenção.
    - Swing trade: isento se valor_venda <= isencao_br; caso contrário 15% (taxa_swing_br).

    Retorna uma tupla (imposto: float, darf_label: str).
    """
    # Valores padrão: imposto zero e operação isenta até que se prove o contrário
    imposto = 0.0
    darf = 'Isento'

    # Se a operação gerou prejuízo (lucro negativo ou zero), não há imposto a pagar
    if lucro <= 0:
        return 0.0, 'Prejuízo'

    # Fundos Imobiliários (FIIs) têm alíquota fixa sobre o lucro, sem limite de isenção
    if tipo_ativo == 'fii':
        imposto = lucro * conf.taxa_fii_br
        darf = f'DARF {int(conf.taxa_fii_br * 100)}%'
    else:
        # Ações: day trade tem alíquota majorada (20%) sobre o lucro, sem direito a isenção
        if operacao == 'day_trade':
            imposto = lucro * conf.taxa_day_br
            darf = f'DARF {int(conf.taxa_day_br * 100)}%'
        elif valor_venda <= conf.isencao_br:
            # Vendas de swing trade até R$ 20.000 no mês são isentas de IR (Lei 11.196/2005)
            darf = 'Isento'
        else:
            # Acima do limite de isenção: alíquota de 15% sobre o lucro (swing trade padrão)
            imposto = lucro * conf.taxa_swing_br
            darf = f'DARF {int(conf.taxa_swing_br * 100)}%'

    return imposto, darf


def calcular_imposto_venda_us(lucro, conf):
    """
    Calcula o imposto devido na venda de ativos no exterior (stocks/REITs).
    Alíquota fixa de 15% (taxa_exterior) sobre o lucro, sem limite de isenção.
    Retorna uma tupla (imposto: float, darf_label: str).
    """
    # Prejuízo no exterior também não gera imposto; retorna zero com indicação de prejuízo
    if lucro <= 0:
        return 0.0, 'Prejuízo'
    # Ativos no exterior (stocks, REITs) têm alíquota fixa de 15% sobre o lucro, sem faixa de isenção
    imposto = lucro * conf.taxa_exterior
    # O imposto US é provisionado para declaração anual, não gerando DARF mensal como no BR
    darf = f'Provisão {int(conf.taxa_exterior * 100)}%'
    return imposto, darf


def calcular_imposto_venda_cripto(lucro, valor_venda, conf):
    """
    Calcula o imposto devido na venda de criptomoedas.

    Regras:
    - Isento se o valor total da venda no mês for <= isencao_cripto (R$ 35.000 padrão).
    - Acima do limite: alíquota de 15% (taxa_cripto) sobre o lucro.

    Retorna uma tupla (imposto: float, darf_label: str).
    """
    # Inicializa imposto como zero e operação como isenta até avaliação das condições
    imposto = 0.0
    darf = 'Isento'

    # Operação com prejuízo em cripto também não gera imposto devido
    if lucro <= 0:
        return 0.0, 'Prejuízo'

    # Vendas de criptomoedas até R$ 35.000 no mês são isentas (Instrução Normativa RFB 1888/2019)
    if valor_venda <= conf.isencao_cripto:
        darf = f'Isento (< {conf.isencao_cripto:.0f})'
    else:
        # Acima do limite: alíquota de 15% sobre o lucro (ganho de capital)
        imposto = lucro * conf.taxa_cripto
        darf = f'DARF {int(conf.taxa_cripto * 100)}%'

    return imposto, darf
