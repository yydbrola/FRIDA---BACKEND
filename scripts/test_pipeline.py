#!/usr/bin/env python3
"""
FRIDA v0.5.2 - Teste do Image Pipeline

Testa o pipeline de processamento de imagem localmente sem Supabase.

Uso:
    python scripts/test_pipeline.py path/to/test_image.jpg
    
Funcionalidades:
1. Carrega imagem do disco
2. Executa segmentação (rembg)
3. Salva imagem segmentada como *_segmented.png
4. Executa composição (image_composer)
5. Salva imagem processada como *_processed.png
6. Executa validação (husk_layer)
7. Imprime relatório detalhado no terminal

Exit Codes:
- 0 se passou (score >= 80)
- 1 se falhou ou erro
"""

import sys
import os
from pathlib import Path

# Adicionar diretório pai ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image
from io import BytesIO
from rembg import remove

from app.services.image_composer import image_composer
from app.services.husk_layer import husk_layer, QualityReport


# =============================================================================
# Funções de Teste
# =============================================================================

def test_composer(image_path: str) -> bytes:
    """
    Testa ImageComposer: segmentação + composição.
    
    Args:
        image_path: Caminho para imagem de teste
        
    Returns:
        Bytes da imagem processada
    """
    print("\n" + "=" * 60)
    print("TESTE: ImageComposer")
    print("=" * 60)
    
    # Carregar imagem
    with open(image_path, 'rb') as f:
        image_bytes = f.read()
    
    print(f"✓ Imagem carregada: {os.path.basename(image_path)}")
    print(f"  → Tamanho: {len(image_bytes):,} bytes")
    
    # Remover fundo com rembg
    print("→ Removendo fundo (rembg)...")
    segmented_bytes = remove(image_bytes)
    print(f"✓ Fundo removido: {len(segmented_bytes):,} bytes")
    
    # Salvar imagem segmentada
    base_name = Path(image_path).stem
    output_dir = Path(image_path).parent
    segmented_path = output_dir / f"{base_name}_segmented.png"
    
    with open(segmented_path, 'wb') as f:
        f.write(segmented_bytes)
    print(f"✓ Segmentada salva: {segmented_path.name}")
    
    # Compor fundo branco
    print("→ Compondo fundo branco...")
    processed_bytes = image_composer.compose_from_bytes(segmented_bytes)
    
    # Salvar imagem processada
    processed_path = output_dir / f"{base_name}_processed.png"
    
    with open(processed_path, 'wb') as f:
        f.write(processed_bytes)
    print(f"✓ Processada salva: {processed_path.name}")
    
    # Verificar dimensões
    processed_image = Image.open(BytesIO(processed_bytes))
    print(f"✓ Dimensões finais: {processed_image.size}")
    
    return processed_bytes


def test_husk_layer(processed_bytes: bytes) -> QualityReport:
    """
    Testa HuskLayer: validação de qualidade.
    
    Args:
        processed_bytes: Bytes da imagem processada
        
    Returns:
        QualityReport com detalhes da validação
    """
    print("\n" + "=" * 60)
    print("TESTE: HuskLayer (Validação de Qualidade)")
    print("=" * 60)
    
    # Executar validação
    report = husk_layer.validate_from_bytes(processed_bytes)
    
    # Score total
    status = "✅ APROVADO" if report.passed else "❌ REPROVADO"
    print(f"\n📊 QUALITY SCORE: {report.score}/100")
    print(f"{status} (threshold: {husk_layer.PASS_THRESHOLD})")
    
    # Detalhes
    print("\n--- Detalhes ---")
    
    # Resolução
    res = report.details.get('resolution', {})
    res_score = res.get('score', 0)
    res_max = res.get('max_score', 30)
    res_status = res.get('status', 'UNKNOWN')
    res_w = res.get('width', 0)
    res_h = res.get('height', 0)
    print(f"📐 Resolução: {res_score}/{res_max} pontos")
    print(f"   → {res_status}: {res_w}x{res_h}px (mínimo: {husk_layer.MIN_RESOLUTION})")
    
    # Centralização
    ctr = report.details.get('centering', {})
    ctr_score = ctr.get('score', 0)
    ctr_max = ctr.get('max_score', 40)
    ctr_coverage = ctr.get('coverage', 0) * 100
    ctr_offset = max(ctr.get('offset_x', 0), ctr.get('offset_y', 0)) * 100
    ctr_status = f"{ctr.get('center_status', '?')}/{ctr.get('coverage_status', '?')}"
    print(f"🎯 Centralização: {ctr_score}/{ctr_max} pontos")
    print(f"   → Cobertura: {ctr_coverage:.1f}%, Desvio: {ctr_offset:.1f}% ({ctr_status})")
    
    # Fundo
    bg = report.details.get('background', {})
    bg_score = bg.get('score', 0)
    bg_max = bg.get('max_score', 30)
    bg_delta = bg.get('avg_delta', 0)
    bg_status = bg.get('status', 'UNKNOWN')
    print(f"⬜ Pureza do Fundo: {bg_score}/{bg_max} pontos")
    print(f"   → Delta médio: {bg_delta:.1f} (tolerância: {husk_layer.RGB_DELTA_TOLERANCE}) - {bg_status}")
    
    return report


def test_full_pipeline(image_path: str) -> bool:
    """
    Executa pipeline completo de teste.

    Args:
        image_path: Caminho para imagem de teste

    Returns:
        True se passou (score >= 80), False caso contrário
    """
    print("=" * 60)
    print("FRIDA v0.5.2 - TESTE DO IMAGE PIPELINE")
    print("=" * 60)
    print(f"Imagem de entrada: {image_path}")

    try:
        # Fase 1: Composição
        processed_bytes = test_composer(image_path)

        # Fase 2: Validação
        report = test_husk_layer(processed_bytes)

        # Resultado final
        print("\n" + "=" * 60)
        print("RESULTADO FINAL")
        print("=" * 60)

        if report.passed:
            print("✅ PIPELINE APROVADO - Imagem pronta para produção!")
        else:
            print("❌ PIPELINE REPROVADO - Imagem precisa de ajustes")
            print("   Verifique os detalhes acima para melhorar a qualidade.")

        print()
        return report.passed

    except Exception as e:
        print(f"\n❌ ERRO NO PIPELINE: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# Testes de Casos de Erro
# =============================================================================

def test_error_cases() -> dict:
    """
    Executa testes de casos de erro para validar tratamento de exceções.

    Returns:
        Dict com resultados dos testes {nome: passed}
    """
    print("\n" + "=" * 60)
    print("TESTES DE CASOS DE ERRO")
    print("=" * 60)

    results = {}

    # Teste 1: Arquivo corrompido
    print("\n[TEST 1] Arquivo corrompido...")
    try:
        corrupted_bytes = b"not a valid image file"
        remove(corrupted_bytes)
        results["corrupted_file"] = False
        print("  ❌ FALHOU - Deveria ter lançado exceção")
    except Exception as e:
        results["corrupted_file"] = True
        print(f"  ✅ OK - Exceção capturada: {type(e).__name__}")

    # Teste 2: Imagem muito pequena (1x1 pixel)
    print("\n[TEST 2] Imagem muito pequena (1x1)...")
    try:
        tiny_image = Image.new('RGB', (1, 1), color='white')
        buffer = BytesIO()
        tiny_image.save(buffer, format='PNG')
        tiny_bytes = buffer.getvalue()

        report = husk_layer.validate_from_bytes(tiny_bytes)
        # Deve falhar na validação (score baixo)
        if report.score < 80:
            results["tiny_image"] = True
            print(f"  ✅ OK - Score baixo como esperado: {report.score}/100")
        else:
            results["tiny_image"] = False
            print(f"  ❌ FALHOU - Score deveria ser baixo: {report.score}/100")
    except Exception as e:
        results["tiny_image"] = True
        print(f"  ✅ OK - Exceção capturada: {type(e).__name__}")

    # Teste 3: Imagem totalmente transparente
    print("\n[TEST 3] Imagem totalmente transparente...")
    try:
        transparent_image = Image.new('RGBA', (100, 100), color=(0, 0, 0, 0))
        buffer = BytesIO()
        transparent_image.save(buffer, format='PNG')
        transparent_bytes = buffer.getvalue()

        processed = image_composer.compose_from_bytes(transparent_bytes)
        # Deve retornar imagem branca (canvas vazio)
        result_image = Image.open(BytesIO(processed))
        if result_image.size[0] > 0:
            results["transparent_image"] = True
            print(f"  ✅ OK - Retornou canvas branco: {result_image.size}")
        else:
            results["transparent_image"] = False
            print("  ❌ FALHOU - Retornou imagem inválida")
    except Exception as e:
        results["transparent_image"] = False
        print(f"  ❌ FALHOU - Exceção inesperada: {e}")

    # Teste 4: Bytes vazios
    print("\n[TEST 4] Bytes vazios...")
    try:
        empty_bytes = b""
        remove(empty_bytes)
        results["empty_bytes"] = False
        print("  ❌ FALHOU - Deveria ter lançado exceção")
    except Exception as e:
        results["empty_bytes"] = True
        print(f"  ✅ OK - Exceção capturada: {type(e).__name__}")

    # Resumo
    print("\n" + "-" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"RESULTADO: {passed}/{total} testes de erro passaram")

    return results


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/test_pipeline.py <caminho_imagem>")
        print("      python scripts/test_pipeline.py --errors")
        print()
        print("Exemplos:")
        print("  python scripts/test_pipeline.py ~/bolsa_teste.jpg  # Teste normal")
        print("  python scripts/test_pipeline.py --errors           # Testes de erro")
        sys.exit(1)

    # Modo de testes de erro
    if sys.argv[1] == "--errors":
        results = test_error_cases()
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        sys.exit(0 if passed == total else 1)

    # Modo normal
    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"❌ Arquivo não encontrado: {image_path}")
        sys.exit(1)

    success = test_full_pipeline(image_path)
    sys.exit(0 if success else 1)
