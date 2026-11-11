# -*- coding: utf-8 -*-
"""Politica de decision del Razonador (la misma evaluada en el reporte):
   SINTETICO si indicios >= 2 y naturalidad <= 1;  AUTENTICO si naturalidad >= 2 y indicios == 0;
   en otro caso (incluida la ausencia de evidencia) se ESCALA a un analista humano."""


def decidir(n_indicios, n_naturalidad):
    if n_indicios + n_naturalidad == 0:
        return dict(veredicto="ESCALAR", regla="R0", motivo="Conocimiento insuficiente: ningun rasgo cayo en una zona de indicio ni de naturalidad.")
    if n_indicios >= 2 and n_naturalidad <= 1:
        return dict(veredicto="SINTETICO", regla="R1", motivo="Al menos 2 indicios de sintesis y a lo mas 1 rasgo de naturalidad.")
    if n_naturalidad >= 2 and n_indicios == 0:
        return dict(veredicto="AUTENTICO", regla="R2", motivo="Al menos 2 rasgos de naturalidad y ningun indicio de sintesis.")
    return dict(veredicto="ESCALAR", regla="R3", motivo="Evidencia insuficiente o contradictoria (%d indicios, %d rasgos de naturalidad)." % (n_indicios, n_naturalidad))
