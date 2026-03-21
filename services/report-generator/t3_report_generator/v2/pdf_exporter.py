"""PDF 보고서 생성 모듈.

마크다운 보고서 텍스트와 일별 데이터를 결합하여 PDF 파일을 생성합니다.
ReportLab을 사용하여 PDF를 직접 생성합니다.
"""

import logging
import tempfile
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle

logger: logging.Logger = logging.getLogger(__name__)


def create_pdf(
    report_markdown: str,
    daily_breakdown: list[dict] = None,
    output_path: str = None,
) -> str:
    """마크다운 보고서와 차트를 결합하여 PDF를 생성합니다.

    Args:
        report_markdown: 마크다운 형식의 보고서 텍스트
        daily_breakdown: 일별 성과 데이터 리스트 (차트 생성용)
        output_path: PDF 저장 경로. None이면 자동 생성

    Returns:
        생성된 PDF 파일 경로
    """
    if not output_path:
        today: str = datetime.now().strftime("%Y-%m-%d")
        output_path = f"report_{today}.pdf"

    # 한글 폰트 등록
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    try:
        # 우선 리눅스(도커 컨테이너) 환경의 나눔고딕을 시도합니다
        try:
            pdfmetrics.registerFont(TTFont('Nanum', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'))
            korean_font = 'Nanum'
            logger.info("한글 폰트 등록 성공: NanumGothic")
        except:
            # 실패하면 로컬 윈도우 환경의 맑은 고딕을 시도합니다
            try:
                # Windows Fonts 디렉토리
                pdfmetrics.registerFont(TTFont('Malgun', 'C:\\Windows\\Fonts\\malgun.ttf'))
                korean_font = 'Malgun'
                logger.info("한글 폰트 등록 성공: MalgunGothic")
            except:
                # 맑은 고딕 실패 시 나눔고딕 시도
                try:
                    pdfmetrics.registerFont(TTFont('Noto', 'C:\\Windows\\Fonts\\NotoSansCJKkr-Regular.otf'))
                    korean_font = 'Noto'
                    logger.info("한글 폰트 등록 성공: Noto Sans CJK")
                except:
                    raise Exception("사용 가능한 한글 폰트 없음")
    except Exception as e:
        # 폰트 등록 실패 시 기본 폰트 사용
        logger.warning(f"한글 폰트 등록 실패: {e}. 기본 폰트를 사용합니다.")
        korean_font = 'Helvetica'

    # PDF 문서 생성
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm,
    )

    # 스타일 정의
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1F4E79'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName=korean_font,
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#1F4E79'),
        spaceAfter=8,
        spaceBefore=8,
        fontName=korean_font,
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=9,
        leading=12,
        alignment=TA_JUSTIFY,
        fontName=korean_font,
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=9,
        fontName=korean_font,
    )

    # 문서 요소 구성
    story = []

    # 헤더
    story.append(Paragraph("CAPA 광고 성과 보고서", title_style))
    story.append(Paragraph(f"생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}", normal_style))
    story.append(Spacer(1, 0.5*cm))

    # 마크다운 파싱 후 요소 추가
    _parse_markdown_and_add_to_story(report_markdown, story, heading_style, body_style, korean_font)

    # 차트 추가
    chart_path = None
    if daily_breakdown and len(daily_breakdown) > 0:
        story.append(PageBreak())
        story.append(Paragraph("일별 추이 차트", heading_style))
        story.append(Spacer(1, 0.3*cm))

        chart_path = _create_trend_chart(daily_breakdown)
        if chart_path:
            try:
                img = Image(chart_path, width=16*cm, height=6*cm)
                story.append(img)
                story.append(Spacer(1, 0.3*cm))
            except Exception as e:
                logger.warning(f"차트 추가 실패: {e}")
                chart_path = None

    # 푸터
    story.append(Spacer(1, 0.5*cm))
    footer_text = "CAPA 광고 분석 플랫폼 | 자동생성 보고서"
    story.append(Paragraph(footer_text, normal_style))

    # PDF 생성
    doc.build(story)
    logger.info(f"PDF 보고서 생성 완료: {output_path}")

    # 임시 차트 파일 정리
    if chart_path:
        try:
            Path(chart_path).unlink()
        except Exception as e:
            logger.warning(f"임시 파일 삭제 실패: {e}")

    return output_path


def _parse_markdown_and_add_to_story(
    markdown_text: str, story: list, heading_style, body_style, korean_font: str = 'Helvetica'
) -> None:
    """마크다운 텍스트를 파싱하여 story에 요소를 추가합니다."""
    lines = markdown_text.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 제목 (##)
        if line.startswith('## '):
            title = line[3:].strip()
            story.append(Paragraph(title, heading_style))
            i += 1

        # 제목 (###)
        elif line.startswith('### '):
            title = line[4:].strip()
            styles = getSampleStyleSheet()
            sub_style = ParagraphStyle(
                'SubHeading',
                parent=styles['Heading3'],
                fontSize=10,
                textColor=colors.HexColor('#2E75B6'),
                spaceAfter=6,
                fontName=korean_font,
            )
            story.append(Paragraph(title, sub_style))
            i += 1

        # 테이블 (마크다운 테이블)
        elif '|' in line:
            table_lines = []
            while i < len(lines) and '|' in lines[i]:
                table_lines.append(lines[i])
                i += 1

            if table_lines:
                table_data = _parse_table(table_lines)
                if table_data:
                    table = Table(table_data, colWidths=[None]*len(table_data[0]))
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E79')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), korean_font),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('FONTNAME', (0, 1), (-1, -1), korean_font),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                    ]))
                    story.append(table)
                    story.append(Spacer(1, 0.3*cm))

        # 빈 줄
        elif not line:
            story.append(Spacer(1, 0.2*cm))
            i += 1

        # 불릿 포인트
        elif line.startswith('- ') or line.startswith('* '):
            bullet_text = line[2:].strip()
            story.append(Paragraph(f"• {bullet_text}", body_style))
            i += 1

        # 일반 텍스트
        else:
            story.append(Paragraph(line, body_style))
            i += 1


def _parse_table(table_lines: list[str]) -> list[list[str]]:
    """마크다운 테이블을 파싱합니다."""
    if len(table_lines) < 2:
        return []

    # 헤더 파싱
    header = [col.strip() for col in table_lines[0].split('|')[1:-1]]

    # 데이터 파싱
    data = [header]
    for line in table_lines[2:]:  # 구분자 줄 건너뛰기
        row = [col.strip() for col in line.split('|')[1:-1]]
        if row:
            data.append(row)

    return data


def _create_trend_chart(daily_breakdown: list[dict]) -> str | None:
    """일별 트렌드 차트를 생성합니다.

    Args:
        daily_breakdown: 일별 성과 데이터 리스트

    Returns:
        생성된 PNG 이미지 파일 경로
    """
    try:
        if not daily_breakdown or len(daily_breakdown) == 0:
            return None

        # DataFrame으로 변환
        df = pd.DataFrame(daily_breakdown)

        # 필요한 컬럼 확인
        if 'date' not in df.columns or 'impressions' not in df.columns:
            logger.warning("필요한 컬럼이 없습니다")
            return None

        # 숫자로 변환
        df['impressions'] = pd.to_numeric(df['impressions'], errors='coerce').fillna(0)
        df['clicks'] = pd.to_numeric(df['clicks'], errors='coerce').fillna(0)
        df['conversions'] = pd.to_numeric(df['conversions'], errors='coerce').fillna(0)

        # 차트 생성
        import platform
        if platform.system() == "Linux":
            plt.rcParams["font.family"] = "NanumGothic"
        else:
            plt.rcParams["font.family"] = "Malgun Gothic"

        fig, ax = plt.subplots(figsize=(12, 5))

        dates = df['date'].tolist()
        x_range = range(len(dates))

        ax.plot(x_range, df['impressions'], marker="o", label="노출", linewidth=2, color="#1F4E79")
        ax.plot(x_range, df['clicks'], marker="s", label="클릭", linewidth=2, color="#2E75B6")
        ax.plot(x_range, df['conversions'], marker="^", label="전환", linewidth=2, color="#70AD47")

        ax.set_xticks(list(x_range))
        ax.set_xticklabels(dates, rotation=45, ha="right", fontsize=8)
        ax.set_title("일별 광고 성과 추이", fontsize=14, fontweight="bold")
        ax.set_xlabel("날짜")
        ax.set_ylabel("수량")
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        # 임시 파일에 저장
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path: str = tmp.name
            plt.savefig(tmp_path, dpi=150, bbox_inches="tight")

        plt.close(fig)
        logger.info(f"차트 생성 완료: {tmp_path}")
        return tmp_path

    except Exception as e:
        logger.error(f"차트 생성 오류: {e}")
        return None
