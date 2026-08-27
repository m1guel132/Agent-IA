"""Tests para el módulo de sanitización local (DataMasker)."""

from __future__ import annotations

import pytest
from agent_ia.infrastructure.sanitizer import DataMasker


def test_mask_emails():
    masker = DataMasker(enabled=True)
    text = "Enviar reporte a contacto@empresa.com y copia a soporte@test.org urgentemente."
    result = masker.mask(text)

    assert "contacto@empresa.com" not in result.masked_text
    assert "soporte@test.org" not in result.masked_text
    assert "<EMAIL_1>" in result.masked_text
    assert "<EMAIL_2>" in result.masked_text

    # Probar desofuscación
    restored = masker.unmask(result.masked_text, result.mapping)
    assert restored == text


def test_mask_amounts():
    masker = DataMasker(enabled=True)
    text = "El presupuesto es de $12,500 USD y tenemos una reserva de 3000 EUR para imprevistos."
    result = masker.mask(text)

    assert "$12,500 USD" not in result.masked_text or "$12,500" not in result.masked_text
    assert "<AMOUNT_" in result.masked_text

    restored = masker.unmask(result.masked_text, result.mapping)
    assert restored == text


def test_mask_secrets():
    masker = DataMasker(enabled=True)
    text = "Mi api_key: AIzaSyD983hf893hf893h y token=secret_token_123456789"
    result = masker.mask(text)

    assert "AIzaSyD983hf893hf893h" not in result.masked_text
    assert "secret_token_123456789" not in result.masked_text
    assert "<SECRET_1>" in result.masked_text
    assert "<SECRET_2>" in result.masked_text

    restored = masker.unmask(result.masked_text, result.mapping)
    assert restored == text


def test_disabled_masker():
    masker = DataMasker(enabled=False)
    text = "Contraseña: password12345 y correo miguel@example.com"
    result = masker.mask(text)

    assert result.masked_text == text
    assert len(result.mapping) == 0
    assert masker.unmask(result.masked_text, result.mapping) == text
