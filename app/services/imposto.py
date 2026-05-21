# Módulo de cálculo de impostos
# Contém as funções que calculam o IR devido para cada categoria de ativo.


def calcular_imposto_venda_br(lucro, valor_venda, tipo_ativo, operacao, conf):
    """
    Calcula o imposto devido na venda de ativos nacionais (B3).

    Regras:
    - FIIs: alíquota fixa sobre o lucro (taxa_fii_br).
    - Day trade: alíquota de 20% (taxa_day_br) sobre o lucro, sem isenção.
    - Swing trade: isento se valor_venda <= isencao_br; caso contrário 15% (taxa_swing_br).

    Retorna uma tupla (imposto: float, darf_label: str).
    """
    imposto = 0.0
    darf = 'Isento'

    # Operação com prejuízo: imposto zero
    if lucro <= 0:
        return 0.0, 'Prejuízo'

    # Cálculo específico para Fundos Imobiliários
    if tipo_ativo == 'fii':
        imposto = lucro * conf.taxa_fii_br
        darf = f'DARF {int(conf.taxa_fii_br * 100)}%'
    else:
        # Ações: diferencia day trade de swing trade
        if operacao == 'day_trade':
            imposto = lucro * conf.taxa_day_br
            darf = f'DARF {int(conf.taxa_day_br * 100)}%'
        elif valor_venda <= conf.isencao_br:
            # Venda dentro do limite de isenção mensal
            darf = 'Isento'
        else:
            # Venda acima do limite: alíquota de swing trade
            imposto = lucro * conf.taxa_swing_br
            darf = f'DARF {int(conf.taxa_swing_br * 100)}%'

    return imposto, darf


def calcular_imposto_venda_us(lucro, conf):
    """
    Calcula o imposto devido na venda de ativos no exterior (stocks/REITs).
    Alíquota fixa de 15% (taxa_exterior) sobre o lucro, sem limite de isenção.
    Retorna uma tupla (imposto: float, darf_label: str).
    """
    if lucro <= 0:
        return 0.0, 'Prejuízo'
    imposto = lucro * conf.taxa_exterior
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
    imposto = 0.0
    darf = 'Isento'

    if lucro <= 0:
        return 0.0, 'Prejuízo'

    # Verifica se o valor da venda está dentro do limite de isenção
    if valor_venda <= conf.isencao_cripto:
        darf = f'Isento (< {conf.isencao_cripto:.0f})'
    else:
        imposto = lucro * conf.taxa_cripto
        darf = f'DARF {int(conf.taxa_cripto * 100)}%'

    return imposto, darf
