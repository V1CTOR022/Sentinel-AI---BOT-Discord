from bot.services.moderation_service import FloodDetector


def test_abaixo_do_limite_nao_alerta():
    detector = FloodDetector(limit=4, window_seconds=10)
    assert [detector.check(1, 99) for _ in range(3)] == [False, False, False]


def test_alerta_ao_atingir_o_limite():
    detector = FloodDetector(limit=3, window_seconds=10)
    assert detector.check(1, 99) is False
    assert detector.check(1, 99) is False
    assert detector.check(1, 99) is True


def test_nao_repete_alerta_dentro_da_janela():
    detector = FloodDetector(limit=2, window_seconds=10)
    detector.check(1, 99)
    assert detector.check(1, 99) is True
    assert detector.check(1, 99) is False


def test_usuarios_sao_contados_separadamente():
    detector = FloodDetector(limit=2, window_seconds=10)
    detector.check(1, 10)
    assert detector.check(1, 20) is False


def test_janela_antiga_e_descartada(monkeypatch):
    detector = FloodDetector(limit=3, window_seconds=5)
    agora = [1000.0]
    monkeypatch.setattr("bot.services.moderation_service.monotonic", lambda: agora[0])

    detector.check(1, 99)
    detector.check(1, 99)
    agora[0] += 60  # passou muito tempo: o contador reinicia
    assert detector.check(1, 99) is False


def test_memoria_nao_cresce_indefinidamente(monkeypatch):
    detector = FloodDetector(limit=10, window_seconds=5)
    agora = [1000.0]
    monkeypatch.setattr("bot.services.moderation_service.monotonic", lambda: agora[0])

    for user_id in range(200):
        detector.check(1, user_id)
    assert detector.tracked_users == 200

    agora[0] += 600
    detector.check(1, 999)
    assert detector.tracked_users == 1
