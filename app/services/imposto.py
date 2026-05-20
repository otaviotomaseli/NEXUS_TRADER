def calcular_imposto_venda_br(lucro, valor_venda, tipo_ativo, operacao, conf):
    """
    Calcula o imposto para venda de ativos na B3.
    Retorna (imposto, darf_label).
    """
    imposto = 0.0
    darf = 'Isento'

    if lucro <= 0:
        return 0.0, 'Prejuízo'

    if tipo_ativo == 'fii':
        imposto = lucro * conf.taxa_fii_br
        darf = f'DARF {int(conf.taxa_fii_br * 100)}%'
    else:
        if operacao == 'day_trade':
            imposto = lucro * conf.taxa_day_br
            darf = f'DARF {int(conf.taxa_day_br * 100)}%'
        elif valor_venda <= conf.isencao_br:
            darf = 'Isento'
        else:
            imposto = lucro * conf.taxa_swing_br
            darf = f'DARF {int(conf.taxa_swing_br * 100)}%'

    return imposto, darf


def calcular_imposto_venda_us(lucro, conf):
    """Calcula imposto para venda de ativos no exterior."""
    if lucro <= 0:
        return 0.0, 'Prejuízo'
    imposto = lucro * conf.taxa_exterior
    darf = f'Provisão {int(conf.taxa_exterior * 100)}%'
    return imposto, darf


def calcular_imposto_venda_cripto(lucro, valor_venda, conf):
    """Calcula imposto para venda de criptomoedas."""
    imposto = 0.0
    darf = 'Isento'

    if lucro <= 0:
        return 0.0, 'Prejuízo'

    if valor_venda <= conf.isencao_cripto:
        darf = f'Isento (< {conf.isencao_cripto:.0f})'
    else:
        imposto = lucro * conf.taxa_cripto
        darf = f'DARF {int(conf.taxa_cripto * 100)}%'

    return imposto, darf
