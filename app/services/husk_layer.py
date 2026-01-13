"""
Husk Layer - Quality Validation Service for FRIDA v0.5.2

Camada de validação que verifica se imagens processadas atendem
ao padrão DIGS. Calcula quality_score de 0-100.

Sistema de Pontuação:
- Resolução (30 pts): imagem ≥1200px na menor dimensão
- Centralização (40 pts): produto centralizado com cobertura 75-95%
- Pureza do Fundo (30 pts): RGB delta <5 do branco puro nos cantos

Threshold: score ≥ 80 = APROVADO
"""

from PIL import Image
from io import BytesIO
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class QualityReport:
    """
    Relatório de qualidade da imagem.
    
    Attributes:
        score: Pontuação total (0-100)
        passed: Se passou no threshold (≥80)
        details: Detalhes de cada verificação
    """
    score: int
    passed: bool
    details: Dict[str, dict] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Converte para dicionário serializável."""
        return {
            "score": self.score,
            "passed": self.passed,
            "details": self.details
        }


# =============================================================================
# Husk Layer Class
# =============================================================================

class HuskLayer:
    """
    Camada de validação de qualidade para imagens DIGS.
    
    Verifica resolução, centralização e pureza do fundo,
    gerando um quality_score de 0-100.
    """
    
    # ==========================================================================
    # Constantes de Pontuação
    # ==========================================================================
    
    SCORE_RESOLUTION: int = 30
    SCORE_CENTERING: int = 40
    SCORE_BACKGROUND: int = 30
    
    # ==========================================================================
    # Constantes de Validação
    # ==========================================================================
    
    MIN_RESOLUTION: int = 1200  # Resolução mínima (px)
    PASS_THRESHOLD: int = 80  # Score mínimo para aprovação
    RGB_DELTA_TOLERANCE: int = 5  # Tolerância de desvio do branco
    CENTER_TOLERANCE: float = 0.15  # Tolerância de centralização (15%)
    COVERAGE_MIN: float = 0.75  # Cobertura mínima do produto
    COVERAGE_MAX: float = 0.95  # Cobertura máxima do produto
    
    # ==========================================================================
    # Métodos Públicos
    # ==========================================================================
    
    def calculate_quality_score(self, image: Image.Image) -> QualityReport:
        """
        Calcula score de qualidade da imagem.
        
        Args:
            image: Imagem PIL (RGB ou RGBA)
            
        Returns:
            QualityReport com score, passed e detalhes
        """
        # Converter para RGB se necessário
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Executar checks
        resolution_result = self._check_resolution(image)
        centering_result = self._check_centering(image)
        background_result = self._check_background_purity(image)
        
        # Calcular score total
        total_score = (
            resolution_result['score'] +
            centering_result['score'] +
            background_result['score']
        )
        
        # Montar relatório
        report = QualityReport(
            score=total_score,
            passed=total_score >= self.PASS_THRESHOLD,
            details={
                'resolution': resolution_result,
                'centering': centering_result,
                'background': background_result
            }
        )
        
        status = "✓ APROVADO" if report.passed else "✗ REPROVADO"
        print(f"[HUSK] Quality Score: {report.score}/100 - {status}")
        
        return report
    
    def validate_from_bytes(self, image_bytes: bytes) -> QualityReport:
        """
        Versão para API: valida imagem a partir de bytes.
        
        Args:
            image_bytes: Imagem em bytes (PNG/JPEG)
            
        Returns:
            QualityReport com resultado da validação
        """
        image = Image.open(BytesIO(image_bytes))
        return self.calculate_quality_score(image)
    
    # ==========================================================================
    # Métodos Privados - Checks
    # ==========================================================================
    
    def _check_resolution(self, image: Image.Image) -> Dict:
        """
        Verifica se resolução atende ao mínimo.
        
        30 pontos se min(width, height) >= 1200px
        Escala linear para resoluções menores
        """
        width, height = image.size
        min_dim = min(width, height)
        
        if min_dim >= self.MIN_RESOLUTION:
            score = self.SCORE_RESOLUTION
            status = "OK"
        else:
            # Escala linear: 600px = 15pts, 0px = 0pts
            ratio = min_dim / self.MIN_RESOLUTION
            score = int(self.SCORE_RESOLUTION * ratio)
            status = "LOW"
        
        return {
            'score': score,
            'max_score': self.SCORE_RESOLUTION,
            'status': status,
            'width': width,
            'height': height,
            'min_dimension': min_dim,
            'required': self.MIN_RESOLUTION
        }
    
    def _check_centering(self, image: Image.Image) -> Dict:
        """
        Verifica centralização e cobertura do produto.
        
        40 pontos se:
        - Produto centralizado (±15% tolerância)
        - Cobertura entre 75-95% do frame
        """
        width, height = image.size
        
        # Encontrar bounding box do conteúdo
        bbox = self._find_content_bbox(image)
        
        if bbox is None:
            # Imagem toda branca
            return {
                'score': 0,
                'max_score': self.SCORE_CENTERING,
                'status': 'NO_CONTENT',
                'error': 'Nenhum conteúdo detectado na imagem'
            }
        
        left, top, right, bottom = bbox
        content_w = right - left
        content_h = bottom - top
        
        # Calcular centro do conteúdo
        content_center_x = left + content_w / 2
        content_center_y = top + content_h / 2
        
        # Centro ideal (metade da imagem)
        ideal_center_x = width / 2
        ideal_center_y = height / 2
        
        # Calcular desvio do centro
        offset_x = abs(content_center_x - ideal_center_x) / width
        offset_y = abs(content_center_y - ideal_center_y) / height
        max_offset = max(offset_x, offset_y)
        
        # Calcular cobertura
        coverage = max(content_w / width, content_h / height)
        
        # Pontuação de centralização (20 pts)
        if max_offset <= self.CENTER_TOLERANCE:
            center_score = 20
            center_status = "CENTERED"
        else:
            # Penalidade proporcional ao desvio
            penalty = min(1.0, max_offset / 0.5)  # 50% de desvio = 0 pts
            center_score = int(20 * (1 - penalty))
            center_status = "OFF_CENTER"
        
        # Pontuação de cobertura (20 pts)
        if self.COVERAGE_MIN <= coverage <= self.COVERAGE_MAX:
            coverage_score = 20
            coverage_status = "OK"
        elif coverage < self.COVERAGE_MIN:
            # Produto muito pequeno
            ratio = coverage / self.COVERAGE_MIN
            coverage_score = int(20 * ratio)
            coverage_status = "TOO_SMALL"
        else:
            # Produto muito grande (>95%)
            excess = coverage - self.COVERAGE_MAX
            penalty = min(1.0, excess / 0.1)  # 105% = 0 pts
            coverage_score = int(20 * (1 - penalty))
            coverage_status = "TOO_LARGE"
        
        total_score = center_score + coverage_score
        
        return {
            'score': total_score,
            'max_score': self.SCORE_CENTERING,
            'center_score': center_score,
            'coverage_score': coverage_score,
            'center_status': center_status,
            'coverage_status': coverage_status,
            'offset_x': round(offset_x, 3),
            'offset_y': round(offset_y, 3),
            'coverage': round(coverage, 3),
            'bbox': bbox
        }
    
    def _check_background_purity(self, image: Image.Image) -> Dict:
        """
        Verifica pureza do fundo branco nos cantos.
        
        30 pontos se RGB delta <5 do branco puro (255,255,255)
        """
        width, height = image.size
        
        # Definir áreas de amostragem (cantos, 5% do tamanho)
        sample_size = max(10, min(width, height) // 20)
        
        corners = [
            # Top-left
            (0, 0, sample_size, sample_size),
            # Top-right
            (width - sample_size, 0, width, sample_size),
            # Bottom-left
            (0, height - sample_size, sample_size, height),
            # Bottom-right
            (width - sample_size, height - sample_size, width, height)
        ]
        
        total_delta = 0
        corner_deltas = []
        
        for corner_bbox in corners:
            corner_region = image.crop(corner_bbox)
            delta = self._calculate_rgb_delta(corner_region)
            corner_deltas.append(delta)
            total_delta += delta
        
        avg_delta = total_delta / len(corners)
        
        # Calcular score
        if avg_delta <= self.RGB_DELTA_TOLERANCE:
            score = self.SCORE_BACKGROUND
            status = "PURE_WHITE"
        else:
            # Penalidade proporcional ao delta
            penalty_ratio = min(1.0, avg_delta / 50)  # Delta 50 = 0 pts
            score = int(self.SCORE_BACKGROUND * (1 - penalty_ratio))
            status = "IMPURE" if avg_delta > 20 else "SLIGHTLY_OFF"
        
        return {
            'score': score,
            'max_score': self.SCORE_BACKGROUND,
            'status': status,
            'avg_delta': round(avg_delta, 2),
            'corner_deltas': corner_deltas,
            'tolerance': self.RGB_DELTA_TOLERANCE
        }
    
    # ==========================================================================
    # Métodos Privados - Helpers
    # ==========================================================================
    
    def _find_content_bbox(self, image: Image.Image) -> Optional[Tuple[int, int, int, int]]:
        """
        Encontra bounding box da área não-branca.
        
        Args:
            image: Imagem RGB
            
        Returns:
            Tuple (left, top, right, bottom) ou None se toda branca
        """
        width, height = image.size
        pixels = image.load()
        
        # Threshold para considerar "branco"
        white_threshold = 250
        
        min_x, min_y = width, height
        max_x, max_y = 0, 0
        found_content = False
        
        # Scan mais eficiente: amostragem a cada 2 pixels
        for y in range(0, height, 2):
            for x in range(0, width, 2):
                r, g, b = pixels[x, y][:3] if isinstance(pixels[x, y], tuple) else (pixels[x, y],) * 3
                
                # Pixel não-branco
                if r < white_threshold or g < white_threshold or b < white_threshold:
                    found_content = True
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
        
        if not found_content:
            return None
        
        # Adicionar margem de segurança pelo step de 2
        return (
            max(0, min_x - 2),
            max(0, min_y - 2),
            min(width, max_x + 2),
            min(height, max_y + 2)
        )
    
    def _calculate_rgb_delta(self, region: Image.Image) -> float:
        """
        Calcula delta médio do branco puro na região.
        
        Args:
            region: Região de imagem RGB
            
        Returns:
            Delta médio (0 = branco puro)
        """
        # Converter para array de pixels
        pixels = list(region.getdata())
        
        if not pixels:
            return 0
        
        total_delta = 0
        for pixel in pixels:
            r, g, b = pixel[:3]
            # Delta = distância média do branco puro
            delta = (abs(255 - r) + abs(255 - g) + abs(255 - b)) / 3
            total_delta += delta
        
        return total_delta / len(pixels)


# =============================================================================
# Singleton Export
# =============================================================================

husk_layer = HuskLayer()
