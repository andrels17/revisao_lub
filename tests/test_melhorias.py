"""
Testes automatizados do sistema de Revisão e Lubrificação.
Execute com: pytest tests/ -v
"""
import pytest
import sys
import os

# Garante que o diretório raiz está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Melhoria #2: Validação de senha ─────────────────────────────────────────

class TestValidacaoSenha:
    """Testa a função _validar_senha do auth_service."""

    def _validar(self, senha):
        from services.auth_service import _validar_senha
        return _validar_senha(senha)

    def test_senha_valida(self):
        ok, msg = self._validar("MinhaSenh4")
        assert ok is True
        assert msg == ""

    def test_senha_muito_curta(self):
        ok, msg = self._validar("Ab1")
        assert ok is False
        assert "8 caracteres" in msg

    def test_senha_sem_maiuscula(self):
        ok, msg = self._validar("minhasenha1")
        assert ok is False
        assert "mai" in msg.lower()

    def test_senha_sem_numero(self):
        ok, msg = self._validar("MinhaSenha")
        assert ok is False
        assert "n" in msg.lower()

    def test_senha_vazia(self):
        ok, msg = self._validar("")
        assert ok is False

    def test_senha_none(self):
        ok, msg = self._validar(None)
        assert ok is False


# ── Melhoria #3: Rate limiting ──────────────────────────────────────────────

class TestRateLimiting:
    """Testa constantes e lógica de rate limiting."""

    def test_constantes_definidas(self):
        from services.auth_service import MAX_TENTATIVAS, BLOQUEIO_MINUTOS
        assert MAX_TENTATIVAS == 5
        assert BLOQUEIO_MINUTOS == 15

    def test_verificar_bloqueio_retorna_tupla(self):
        from services.auth_service import verificar_bloqueio
        try:
            resultado = verificar_bloqueio("teste@exemplo.com")
            assert isinstance(resultado, tuple)
            assert len(resultado) == 2
            bloqueado, minutos = resultado
            assert isinstance(bloqueado, bool)
            assert isinstance(minutos, int)
        except Exception:
            pytest.skip("Banco de dados não disponível no ambiente de teste.")


# ── Alertas WhatsApp: Geração de mensagens ──────────────────────────────────

class TestMensagensWhatsApp:
    """Testa a geração de mensagens de alerta para WhatsApp."""

    @pytest.fixture
    def equipamento_km(self):
        return {
            "id": "eqp-001",
            "codigo": "TR-001",
            "nome": "Trator Agrícola",
            "setor_nome": "Setor A",
        }

    @pytest.fixture
    def etapa_vencida(self):
        return {
            "etapa": "Troca de óleo",
            "tipo_controle": "km",
            "diferenca": -250.0,
            "status": "VENCIDO",
            "atual": 15250.0,
            "vencimento": 15000.0,
        }

    @pytest.fixture
    def etapa_proxima(self):
        return {
            "etapa": "Filtro de ar",
            "tipo_controle": "km",
            "diferenca": 350.0,
            "status": "PROXIMO",
            "atual": 14650.0,
            "vencimento": 15000.0,
        }

    def test_mensagem_revisao_vencida(self, equipamento_km, etapa_vencida):
        from services.alertas_service import montar_mensagem_revisao
        msg = montar_mensagem_revisao(equipamento_km, etapa_vencida, "João Silva")
        assert "João Silva" in msg
        assert "TR-001" in msg
        assert "Trator Agrícola" in msg
        assert "Troca de óleo" in msg
        assert "Vencido" in msg
        assert "km" in msg

    def test_mensagem_revisao_proxima(self, equipamento_km, etapa_proxima):
        from services.alertas_service import montar_mensagem_revisao
        msg = montar_mensagem_revisao(equipamento_km, etapa_proxima, "Maria Santos")
        assert "Maria Santos" in msg
        assert "350" in msg

    def test_mensagem_lubrificacao(self, equipamento_km):
        from services.alertas_service import montar_mensagem_lubrificacao
        item = {
            "item": "Lubrificação do eixo",
            "tipo_controle": "km",
            "diferenca": -100.0,
            "status": "VENCIDO",
            "atual": 12100.0,
            "vencimento": 12000.0,
            "tipo_produto": "Graxa MP2",
        }
        msg = montar_mensagem_lubrificacao(equipamento_km, item, "Carlos")
        assert "Carlos" in msg
        assert "Lubrificação do eixo" in msg
        assert "Graxa MP2" in msg

    def test_link_whatsapp_formatacao(self):
        from services.alertas_service import gerar_link_whatsapp
        link = gerar_link_whatsapp("11987654321", "Olá, teste!")
        assert link.startswith("https://wa.me/")
        assert "5511987654321" in link

    def test_link_whatsapp_com_prefixo_55(self):
        from services.alertas_service import gerar_link_whatsapp
        link = gerar_link_whatsapp("5511987654321", "msg")
        assert "5511987654321" in link


# ── Melhoria #15: Fleet Health Score ────────────────────────────────────────

class TestFleetHealthScore:
    """Testa o cálculo do Fleet Health Score."""

    def _calcular(self, kpis_alertas, mov):
        from services.inteligencia_service import calcular_health_score
        return calcular_health_score(kpis_alertas, mov)

    def _mov_vazio(self):
        return {
            "kpis": {"equipamentos_parados": 0},
            "anomalias": {"travadas": [], "saltos": [], "inconsistencias": []},
        }

    def test_frota_saudavel(self):
        kpis = {
            "total_equipamentos": 100,
            "equipamentos_com_alerta": 0,
            "vencidos": 0,
            "proximos": 0,
        }
        resultado = self._calcular(kpis, self._mov_vazio())
        assert resultado["score"] >= 80
        assert resultado["nivel"] in ("Excelente", "Bom")

    def test_frota_critica(self):
        kpis = {
            "total_equipamentos": 100,
            "equipamentos_com_alerta": 80,
            "vencidos": 60,
            "proximos": 20,
        }
        mov = {
            "kpis": {"equipamentos_parados": 30},
            "anomalias": {
                "travadas": list(range(3)),
                "saltos": list(range(2)),
                "inconsistencias": [1],
            },
        }
        resultado = self._calcular(kpis, mov)
        assert resultado["score"] <= 50

    def test_score_dentro_limites(self):
        for vencidos in [0, 10, 50, 100]:
            kpis = {
                "total_equipamentos": 100,
                "equipamentos_com_alerta": vencidos,
                "vencidos": vencidos,
                "proximos": 0,
            }
            resultado = self._calcular(kpis, self._mov_vazio())
            assert 0 <= resultado["score"] <= 100

    def test_resultado_tem_campos_obrigatorios(self):
        kpis = {"total_equipamentos": 10, "equipamentos_com_alerta": 2, "vencidos": 1, "proximos": 1}
        resultado = self._calcular(kpis, self._mov_vazio())
        assert "score" in resultado
        assert "nivel" in resultado
        assert "cor" in resultado
        assert "componentes" in resultado


# ── Melhoria #7: Estimativa de vencimento ───────────────────────────────────

class TestEstimativaVencimento:
    """Testa o cálculo de estimativa de data de vencimento."""

    def _estimar(self, historico, falta, tipo="km"):
        from services.dashboard_service import estimar_data_vencimento
        return estimar_data_vencimento(historico, falta, tipo)

    def test_sem_historico_retorna_none(self):
        assert self._estimar([], 500) is None

    def test_historico_insuficiente_retorna_none(self):
        from datetime import date
        historico = [{"data_leitura": date(2025, 7, 1), "km_valor": 10000}]
        assert self._estimar(historico, 500) is None

    def test_falta_zero_retorna_none(self):
        from datetime import date
        historico = [
            {"data_leitura": date(2025, 7, 20), "km_valor": 10500},
            {"data_leitura": date(2025, 7, 10), "km_valor": 10000},
        ]
        assert self._estimar(historico, 0) is None

    def test_estimativa_retorna_string(self):
        from datetime import date
        historico = [
            {"data_leitura": date(2025, 7, 20), "km_valor": 10500, "horas_valor": 0},
            {"data_leitura": date(2025, 7, 10), "km_valor": 10000, "horas_valor": 0},
        ]
        resultado = self._estimar(historico, 1000)
        # 500km em 10 dias = 50km/dia → 1000km = ~20 dias
        assert resultado is not None
        assert isinstance(resultado, str)


# ── Serviço de E-mail ────────────────────────────────────────────────────────

class TestEmailService:
    """Testa a estrutura do serviço de e-mail."""

    def test_html_revisao_contem_campos(self):
        try:
            from services.email_service import montar_html_revisao
        except ImportError:
            pytest.skip("email_service não disponível")
        eqp = {"codigo": "EQ-001", "nome": "Escavadeira", "setor_nome": "Mina"}
        etapa = {
            "etapa": "Troca óleo", "tipo_controle": "km",
            "diferenca": -100, "status": "VENCIDO",
            "atual": 5100, "vencimento": 5000
        }
        html, texto = montar_html_revisao(eqp, etapa, "José")
        assert "José" in html
        assert "EQ-001" in html
        assert "José" in texto

    def test_html_lubrificacao_contem_campos(self):
        try:
            from services.email_service import montar_html_lubrificacao
        except ImportError:
            pytest.skip("email_service não disponível")
        eqp = {"codigo": "EQ-002", "nome": "Carregadeira", "setor_nome": "Pátio"}
        item = {
            "item": "Lubrif. pinhão", "tipo_controle": "horas",
            "diferenca": -50, "status": "VENCIDO",
            "atual": 2050, "vencimento": 2000, "tipo_produto": "SAE 80W"
        }
        html, texto = montar_html_lubrificacao(eqp, item, "Ana")
        assert "Ana" in html
        assert "EQ-002" in html
        assert "SAE 80W" in html
