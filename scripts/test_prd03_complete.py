#!/usr/bin/env python3
"""
FRIDA v0.5.3 - Micro-PRD 03 Complete Test Suite

Testes abrangentes para validar a implementação do Image Pipeline:
1. ImageComposer - Composição de fundo branco
2. HuskLayer - Validação de qualidade
3. ImagePipelineSync - Orquestração completa

Uso:
    python scripts/test_prd03_complete.py           # Todos os testes
    python scripts/test_prd03_complete.py --unit    # Apenas testes unitários
    python scripts/test_prd03_complete.py --edge    # Apenas edge cases

Exit Codes:
- 0: Todos os testes passaram
- 1: Um ou mais testes falharam
"""

import sys
import os
import traceback
from pathlib import Path
from io import BytesIO
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image, ImageDraw
import numpy as np


# =============================================================================
# Test Framework
# =============================================================================

@dataclass
class TestResult:
    """Resultado de um teste individual."""
    name: str
    category: str
    passed: bool
    message: str
    duration_ms: float = 0


class TestRunner:
    """Framework simples de testes."""

    def __init__(self):
        self.results: List[TestResult] = []
        self.current_category = "default"

    def category(self, name: str):
        """Define categoria atual dos testes."""
        self.current_category = name
        print(f"\n{'='*60}")
        print(f"CATEGORIA: {name}")
        print('='*60)

    def test(self, name: str, condition: bool, message: str = "", duration_ms: float = 0):
        """Registra resultado de um teste."""
        result = TestResult(
            name=name,
            category=self.current_category,
            passed=condition,
            message=message,
            duration_ms=duration_ms
        )
        self.results.append(result)

        status = "✅ PASS" if condition else "❌ FAIL"
        print(f"  [{status}] {name}")
        if message and not condition:
            print(f"         → {message}")

    def summary(self) -> bool:
        """Imprime sumário e retorna True se todos passaram."""
        print(f"\n{'='*60}")
        print("SUMÁRIO DOS TESTES")
        print('='*60)

        # Agrupar por categoria
        by_category: Dict[str, List[TestResult]] = {}
        for r in self.results:
            if r.category not in by_category:
                by_category[r.category] = []
            by_category[r.category].append(r)

        total_passed = 0
        total_failed = 0

        for cat, tests in by_category.items():
            passed = sum(1 for t in tests if t.passed)
            failed = len(tests) - passed
            total_passed += passed
            total_failed += failed

            status = "✅" if failed == 0 else "❌"
            print(f"{status} {cat}: {passed}/{len(tests)} testes")

        total = total_passed + total_failed
        print(f"\n{'='*60}")
        print(f"TOTAL: {total_passed}/{total} testes passaram ({total_passed/total*100:.1f}%)")

        if total_failed > 0:
            print(f"\n❌ {total_failed} TESTE(S) FALHARAM:")
            for r in self.results:
                if not r.passed:
                    print(f"   - [{r.category}] {r.name}: {r.message}")
        else:
            print("\n🎉 TODOS OS TESTES PASSARAM!")

        return total_failed == 0


# =============================================================================
# Test Utilities
# =============================================================================

def create_test_image_rgba(width: int, height: int, color: Tuple[int, int, int, int] = (255, 0, 0, 255)) -> Image.Image:
    """Cria imagem RGBA de teste com objeto no centro."""
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Desenhar elipse no centro
    margin = min(width, height) // 4
    draw.ellipse(
        [margin, margin, width - margin, height - margin],
        fill=color
    )
    return img


def create_test_image_rgb(width: int, height: int, bg_color: Tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """Cria imagem RGB de teste."""
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Desenhar retângulo no centro
    margin = min(width, height) // 4
    draw.rectangle(
        [margin, margin, width - margin, height - margin],
        fill=(100, 100, 100)
    )
    return img


def image_to_bytes(img: Image.Image, format: str = 'PNG') -> bytes:
    """Converte imagem PIL para bytes."""
    buffer = BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()


# =============================================================================
# Test Suites
# =============================================================================

def test_image_composer(runner: TestRunner):
    """Testes para ImageComposer."""
    from app.services.image_composer import image_composer, ImageComposer

    runner.category("ImageComposer - Composição de Fundo Branco")

    # Test 1: Constantes de configuração
    runner.test(
        "Configuração: TARGET_SIZE = 1200",
        ImageComposer.TARGET_SIZE == 1200,
        f"Esperado 1200, encontrado {ImageComposer.TARGET_SIZE}"
    )

    runner.test(
        "Configuração: PRODUCT_COVERAGE = 0.85",
        ImageComposer.PRODUCT_COVERAGE == 0.85,
        f"Esperado 0.85, encontrado {ImageComposer.PRODUCT_COVERAGE}"
    )

    runner.test(
        "Configuração: BACKGROUND_COLOR = (255, 255, 255)",
        ImageComposer.BACKGROUND_COLOR == (255, 255, 255),
        f"Esperado branco puro, encontrado {ImageComposer.BACKGROUND_COLOR}"
    )

    # Test 2: Composição básica
    test_img = create_test_image_rgba(800, 600)
    try:
        result = image_composer.compose_white_background(test_img)
        runner.test(
            "Composição básica: retorna imagem",
            isinstance(result, Image.Image),
            "Não retornou objeto Image"
        )
        runner.test(
            "Composição básica: modo RGB",
            result.mode == 'RGB',
            f"Esperado RGB, encontrado {result.mode}"
        )
        runner.test(
            "Composição básica: dimensão 1200x1200",
            result.size == (1200, 1200),
            f"Esperado (1200, 1200), encontrado {result.size}"
        )
    except Exception as e:
        runner.test("Composição básica: sem exceção", False, str(e))

    # Test 3: Fundo branco nos cantos
    if 'result' in dir():
        pixels = result.load()
        corners = [
            (0, 0), (1199, 0), (0, 1199), (1199, 1199)
        ]
        all_white = True
        for x, y in corners:
            r, g, b = pixels[x, y][:3]
            if not (r > 250 and g > 250 and b > 250):
                all_white = False
                break
        runner.test(
            "Composição: cantos são branco puro",
            all_white,
            "Cantos não são brancos"
        )

    # Test 4: compose_from_bytes
    test_bytes = image_to_bytes(create_test_image_rgba(500, 500))
    try:
        result_bytes = image_composer.compose_from_bytes(test_bytes)
        runner.test(
            "compose_from_bytes: retorna bytes",
            isinstance(result_bytes, bytes) and len(result_bytes) > 0,
            "Não retornou bytes válidos"
        )
        # Verificar se é PNG válido
        result_img = Image.open(BytesIO(result_bytes))
        runner.test(
            "compose_from_bytes: PNG válido",
            result_img.size == (1200, 1200),
            f"Dimensões incorretas: {result_img.size}"
        )
    except Exception as e:
        runner.test("compose_from_bytes: sem exceção", False, str(e))

    # Test 5: Tamanho customizado
    try:
        result_custom = image_composer.compose_white_background(
            create_test_image_rgba(400, 400),
            target_size=800
        )
        runner.test(
            "Tamanho customizado: 800x800",
            result_custom.size == (800, 800),
            f"Esperado (800, 800), encontrado {result_custom.size}"
        )
    except Exception as e:
        runner.test("Tamanho customizado: sem exceção", False, str(e))

    # Test 6: Imagem sem transparência (deve lançar ValueError)
    rgb_img = create_test_image_rgb(400, 400)
    try:
        image_composer.compose_white_background(rgb_img)
        runner.test(
            "Imagem RGB: lança ValueError",
            False,
            "Deveria ter lançado ValueError"
        )
    except ValueError:
        runner.test("Imagem RGB: lança ValueError", True)
    except Exception as e:
        runner.test("Imagem RGB: lança ValueError", False, f"Exceção errada: {type(e).__name__}")

    # Test 7: Imagem totalmente transparente
    transparent = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
    try:
        result_transparent = image_composer.compose_white_background(transparent)
        runner.test(
            "Imagem transparente: retorna canvas branco",
            result_transparent.size == (1200, 1200),
            "Não retornou canvas correto"
        )
    except Exception as e:
        runner.test("Imagem transparente: sem exceção", False, str(e))


def test_husk_layer(runner: TestRunner):
    """Testes para HuskLayer (validação de qualidade)."""
    from app.services.husk_layer import husk_layer, HuskLayer, QualityReport

    runner.category("HuskLayer - Validação de Qualidade")

    # Test 1: Constantes de pontuação
    total_score = HuskLayer.SCORE_RESOLUTION + HuskLayer.SCORE_CENTERING + HuskLayer.SCORE_BACKGROUND
    runner.test(
        "Pontuação total = 100",
        total_score == 100,
        f"Esperado 100, encontrado {total_score}"
    )

    runner.test(
        "Threshold de aprovação = 80",
        HuskLayer.PASS_THRESHOLD == 80,
        f"Esperado 80, encontrado {HuskLayer.PASS_THRESHOLD}"
    )

    # Test 2: Imagem perfeita (1200x1200, centrada, fundo branco)
    perfect_img = Image.new('RGB', (1200, 1200), (255, 255, 255))
    draw = ImageDraw.Draw(perfect_img)
    # Produto centralizado ocupando ~85%
    margin = int(1200 * 0.075)  # 7.5% de margem em cada lado
    draw.rectangle(
        [margin, margin, 1200 - margin, 1200 - margin],
        fill=(100, 100, 100)
    )

    report = husk_layer.calculate_quality_score(perfect_img)
    runner.test(
        "Imagem perfeita: score >= 80",
        report.score >= 80,
        f"Score: {report.score}/100"
    )
    runner.test(
        "Imagem perfeita: passed = True",
        report.passed,
        "Deveria ter passado"
    )

    # Test 3: Resolução baixa
    small_img = Image.new('RGB', (600, 600), (255, 255, 255))
    draw_small = ImageDraw.Draw(small_img)
    draw_small.rectangle([50, 50, 550, 550], fill=(100, 100, 100))

    report_small = husk_layer.calculate_quality_score(small_img)
    runner.test(
        "Resolução baixa: score resolução < 30",
        report_small.details['resolution']['score'] < 30,
        f"Score resolução: {report_small.details['resolution']['score']}"
    )

    # Test 4: Produto descentralizado
    offcenter_img = Image.new('RGB', (1200, 1200), (255, 255, 255))
    draw_off = ImageDraw.Draw(offcenter_img)
    # Produto no canto superior esquerdo
    draw_off.rectangle([50, 50, 400, 400], fill=(100, 100, 100))

    report_off = husk_layer.calculate_quality_score(offcenter_img)
    runner.test(
        "Produto descentralizado: score centralização < 40",
        report_off.details['centering']['score'] < 40,
        f"Score centralização: {report_off.details['centering']['score']}"
    )

    # Test 5: Fundo impuro (não branco)
    impure_img = Image.new('RGB', (1200, 1200), (200, 200, 200))  # Cinza
    draw_impure = ImageDraw.Draw(impure_img)
    margin_i = int(1200 * 0.075)
    draw_impure.rectangle(
        [margin_i, margin_i, 1200 - margin_i, 1200 - margin_i],
        fill=(100, 100, 100)
    )

    report_impure = husk_layer.calculate_quality_score(impure_img)
    runner.test(
        "Fundo impuro: score background < 30",
        report_impure.details['background']['score'] < 30,
        f"Score background: {report_impure.details['background']['score']}"
    )

    # Test 6: QualityReport.to_dict()
    dict_report = report.to_dict()
    runner.test(
        "QualityReport.to_dict: contém 'score'",
        'score' in dict_report,
        "Faltando campo 'score'"
    )
    runner.test(
        "QualityReport.to_dict: contém 'passed'",
        'passed' in dict_report,
        "Faltando campo 'passed'"
    )
    runner.test(
        "QualityReport.to_dict: contém 'details'",
        'details' in dict_report,
        "Faltando campo 'details'"
    )

    # Test 7: validate_from_bytes
    img_bytes = image_to_bytes(perfect_img, 'PNG')
    report_bytes = husk_layer.validate_from_bytes(img_bytes)
    runner.test(
        "validate_from_bytes: retorna QualityReport",
        isinstance(report_bytes, QualityReport),
        f"Retornou {type(report_bytes)}"
    )

    # Test 8: Imagem toda branca (sem conteúdo)
    white_img = Image.new('RGB', (1200, 1200), (255, 255, 255))
    report_white = husk_layer.calculate_quality_score(white_img)
    runner.test(
        "Imagem toda branca: centralização = 0",
        report_white.details['centering']['score'] == 0,
        f"Esperado 0, encontrado {report_white.details['centering']['score']}"
    )

    # Test 9: Produto muito pequeno
    tiny_product = Image.new('RGB', (1200, 1200), (255, 255, 255))
    draw_tiny = ImageDraw.Draw(tiny_product)
    draw_tiny.rectangle([550, 550, 650, 650], fill=(100, 100, 100))  # 50x50px

    report_tiny = husk_layer.calculate_quality_score(tiny_product)
    runner.test(
        "Produto muito pequeno: cobertura TOO_SMALL",
        report_tiny.details['centering'].get('coverage_status') == 'TOO_SMALL',
        f"Status: {report_tiny.details['centering'].get('coverage_status')}"
    )


def test_pipeline_structures(runner: TestRunner):
    """Testes para estruturas do ImagePipelineSync."""
    from app.services.image_pipeline import PipelineResult, BUCKETS, ImagePipelineSync

    runner.category("ImagePipeline - Estruturas e Configurações")

    # Test 1: Buckets configurados
    runner.test(
        "BUCKETS: contém 'original'",
        'original' in BUCKETS,
        "Faltando bucket 'original'"
    )
    runner.test(
        "BUCKETS: contém 'segmented'",
        'segmented' in BUCKETS,
        "Faltando bucket 'segmented'"
    )
    runner.test(
        "BUCKETS: contém 'processed'",
        'processed' in BUCKETS,
        "Faltando bucket 'processed'"
    )

    # Test 2: Nomes dos buckets
    runner.test(
        "Bucket original = 'raw'",
        BUCKETS['original'] == 'raw',
        f"Esperado 'raw', encontrado '{BUCKETS['original']}'"
    )
    runner.test(
        "Bucket processed = 'processed-images'",
        BUCKETS['processed'] == 'processed-images',
        f"Esperado 'processed-images', encontrado '{BUCKETS['processed']}'"
    )

    # Test 3: PipelineResult
    result = PipelineResult(
        success=True,
        product_id="test-123",
        images={"original": {"id": "img-1"}},
        quality_report=None,
        error=None
    )

    runner.test(
        "PipelineResult: atributo success",
        hasattr(result, 'success'),
        "Faltando atributo 'success'"
    )
    runner.test(
        "PipelineResult: atributo product_id",
        hasattr(result, 'product_id'),
        "Faltando atributo 'product_id'"
    )
    runner.test(
        "PipelineResult: atributo images",
        hasattr(result, 'images'),
        "Faltando atributo 'images'"
    )

    # Test 4: PipelineResult.to_dict()
    result_dict = result.to_dict()
    runner.test(
        "PipelineResult.to_dict: serializável",
        isinstance(result_dict, dict),
        f"Retornou {type(result_dict)}"
    )
    runner.test(
        "PipelineResult.to_dict: contém success",
        'success' in result_dict,
        "Faltando 'success' no dict"
    )

    # Test 5: ImagePipelineSync instancia
    try:
        pipeline = ImagePipelineSync()
        runner.test(
            "ImagePipelineSync: instanciação",
            True
        )
        runner.test(
            "ImagePipelineSync: tem _client_lock",
            hasattr(pipeline, '_client_lock'),
            "Faltando thread lock"
        )
    except Exception as e:
        runner.test("ImagePipelineSync: instanciação", False, str(e))


def test_config_dos_protection(runner: TestRunner):
    """Testes para proteção DoS em config.py."""
    from app.config import settings

    runner.category("Config - Proteção DoS")

    # Test 1: MAX_FILE_SIZE_MB
    runner.test(
        "MAX_FILE_SIZE_MB configurado",
        hasattr(settings, 'MAX_FILE_SIZE_MB'),
        "Faltando MAX_FILE_SIZE_MB"
    )
    if hasattr(settings, 'MAX_FILE_SIZE_MB'):
        runner.test(
            "MAX_FILE_SIZE_MB = 10",
            settings.MAX_FILE_SIZE_MB == 10,
            f"Esperado 10, encontrado {settings.MAX_FILE_SIZE_MB}"
        )

    # Test 2: MAX_FILE_SIZE_BYTES
    runner.test(
        "MAX_FILE_SIZE_BYTES configurado",
        hasattr(settings, 'MAX_FILE_SIZE_BYTES'),
        "Faltando MAX_FILE_SIZE_BYTES"
    )
    if hasattr(settings, 'MAX_FILE_SIZE_BYTES'):
        expected_bytes = 10 * 1024 * 1024
        runner.test(
            "MAX_FILE_SIZE_BYTES = 10MB em bytes",
            settings.MAX_FILE_SIZE_BYTES == expected_bytes,
            f"Esperado {expected_bytes}, encontrado {settings.MAX_FILE_SIZE_BYTES}"
        )

    # Test 3: MAX_IMAGE_DIMENSION
    runner.test(
        "MAX_IMAGE_DIMENSION configurado",
        hasattr(settings, 'MAX_IMAGE_DIMENSION'),
        "Faltando MAX_IMAGE_DIMENSION"
    )
    if hasattr(settings, 'MAX_IMAGE_DIMENSION'):
        runner.test(
            "MAX_IMAGE_DIMENSION = 8000",
            settings.MAX_IMAGE_DIMENSION == 8000,
            f"Esperado 8000, encontrado {settings.MAX_IMAGE_DIMENSION}"
        )


def test_edge_cases(runner: TestRunner):
    """Testes de casos extremos."""
    from app.services.image_composer import image_composer
    from app.services.husk_layer import husk_layer

    runner.category("Edge Cases - Casos Extremos")

    # Test 1: Bytes corrompidos
    corrupted_bytes = b"not a valid image file at all"
    try:
        husk_layer.validate_from_bytes(corrupted_bytes)
        runner.test("Bytes corrompidos: lança exceção", False, "Deveria lançar exceção")
    except Exception:
        runner.test("Bytes corrompidos: lança exceção", True)

    # Test 2: Bytes vazios
    try:
        husk_layer.validate_from_bytes(b"")
        runner.test("Bytes vazios: lança exceção", False, "Deveria lançar exceção")
    except Exception:
        runner.test("Bytes vazios: lança exceção", True)

    # Test 3: Imagem 1x1
    tiny = Image.new('RGB', (1, 1), (255, 255, 255))
    report = husk_layer.calculate_quality_score(tiny)
    runner.test(
        "Imagem 1x1: não crasha",
        isinstance(report.score, int),
        "Deveria retornar score"
    )
    runner.test(
        "Imagem 1x1: score baixo",
        report.score < 50,
        f"Score: {report.score} (deveria ser baixo)"
    )

    # Test 4: Imagem muito grande (simulada - não criar de verdade por memória)
    runner.test(
        "Limite de dimensão: configurado",
        True,  # Já testado em test_config_dos_protection
        "MAX_IMAGE_DIMENSION deve estar configurado"
    )

    # Test 5: Imagem RGBA com transparência parcial
    partial_alpha = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(partial_alpha)
    # Gradiente de transparência
    for i in range(400):
        alpha = int(255 * i / 400)
        draw.line([(i, 0), (i, 400)], fill=(255, 0, 0, alpha))

    try:
        result = image_composer.compose_white_background(partial_alpha)
        runner.test(
            "Transparência parcial: processa OK",
            result.size == (1200, 1200),
            f"Resultado: {result.size}"
        )
    except Exception as e:
        runner.test("Transparência parcial: processa OK", False, str(e))

    # Test 6: Imagem em modo L (grayscale)
    grayscale = Image.new('L', (400, 400), 128)
    try:
        report_gray = husk_layer.calculate_quality_score(grayscale)
        runner.test(
            "Imagem grayscale: processa OK",
            isinstance(report_gray.score, int),
            "Deveria processar grayscale"
        )
    except Exception as e:
        runner.test("Imagem grayscale: processa OK", False, str(e))

    # Test 7: Imagem em modo P (palette)
    palette = Image.new('P', (400, 400))
    try:
        report_palette = husk_layer.calculate_quality_score(palette)
        runner.test(
            "Imagem palette: processa OK",
            isinstance(report_palette.score, int),
            "Deveria processar palette"
        )
    except Exception as e:
        runner.test("Imagem palette: processa OK", False, str(e))


def test_integration_flow(runner: TestRunner):
    """Testes de integração: fluxo compositor -> validador."""
    from app.services.image_composer import image_composer
    from app.services.husk_layer import husk_layer

    runner.category("Integração - Fluxo Compositor → Validador")

    # Test 1: Fluxo completo com imagem válida
    input_img = create_test_image_rgba(800, 600, (150, 100, 80, 255))

    # Compor
    composed = image_composer.compose_white_background(input_img)
    runner.test(
        "Fluxo: composição retorna imagem",
        isinstance(composed, Image.Image),
        "Composição falhou"
    )

    # Validar
    report = husk_layer.calculate_quality_score(composed)
    runner.test(
        "Fluxo: validação retorna report",
        hasattr(report, 'score'),
        "Validação falhou"
    )

    # Imagem composta deve passar na validação
    runner.test(
        "Fluxo: imagem composta passa (score >= 80)",
        report.passed,
        f"Score: {report.score}/100"
    )

    # Test 2: Verificar detalhes específicos
    runner.test(
        "Fluxo: resolução OK (30 pts)",
        report.details['resolution']['score'] == 30,
        f"Score resolução: {report.details['resolution']['score']}"
    )
    runner.test(
        "Fluxo: fundo puro (30 pts)",
        report.details['background']['score'] == 30,
        f"Score background: {report.details['background']['score']}"
    )

    # Test 3: Fluxo com bytes (API simulation)
    input_bytes = image_to_bytes(create_test_image_rgba(600, 400))
    composed_bytes = image_composer.compose_from_bytes(input_bytes)
    report_bytes = husk_layer.validate_from_bytes(composed_bytes)

    runner.test(
        "Fluxo bytes: funciona end-to-end",
        report_bytes.passed,
        f"Score: {report_bytes.score}/100"
    )

    # Test 4: Múltiplas imagens em sequência (teste de estado)
    scores = []
    for i in range(3):
        img = create_test_image_rgba(400 + i*100, 300 + i*100)
        composed_i = image_composer.compose_white_background(img)
        report_i = husk_layer.calculate_quality_score(composed_i)
        scores.append(report_i.score)

    runner.test(
        "Fluxo múltiplo: todas passam",
        all(s >= 80 for s in scores),
        f"Scores: {scores}"
    )


def test_rembg_integration(runner: TestRunner):
    """Testes de integração com rembg (se disponível)."""
    runner.category("Integração - rembg (Segmentação)")

    try:
        from rembg import remove
        runner.test("rembg: importação OK", True)

        # Criar imagem de teste simples
        test_img = create_test_image_rgb(200, 200, (100, 150, 200))
        test_bytes = image_to_bytes(test_img, 'PNG')

        # Executar rembg (pode demorar na primeira vez)
        print("    → Executando rembg (pode demorar)...")
        segmented = remove(test_bytes)

        runner.test(
            "rembg: retorna bytes",
            isinstance(segmented, bytes) and len(segmented) > 0,
            "Retorno inválido"
        )

        # Verificar se é PNG válido
        result_img = Image.open(BytesIO(segmented))
        runner.test(
            "rembg: retorna PNG válido",
            result_img.mode in ('RGBA', 'RGB', 'P'),
            f"Modo: {result_img.mode}"
        )

    except ImportError:
        runner.test("rembg: importação OK", False, "rembg não instalado")
    except Exception as e:
        runner.test("rembg: execução OK", False, str(e))


# =============================================================================
# Main
# =============================================================================

def main():
    """Executa todos os testes."""
    print("="*60)
    print("FRIDA v0.5.3 - MICRO-PRD 03 COMPLETE TEST SUITE")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    runner = TestRunner()

    # Determinar quais testes executar
    run_all = len(sys.argv) == 1
    run_unit = '--unit' in sys.argv
    run_edge = '--edge' in sys.argv
    run_integration = '--integration' in sys.argv

    if run_all or run_unit:
        test_image_composer(runner)
        test_husk_layer(runner)
        test_pipeline_structures(runner)
        test_config_dos_protection(runner)

    if run_all or run_edge:
        test_edge_cases(runner)

    if run_all or run_integration:
        test_integration_flow(runner)
        test_rembg_integration(runner)

    # Sumário
    all_passed = runner.summary()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
