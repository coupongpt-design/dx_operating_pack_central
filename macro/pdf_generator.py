"""
PDF 리포트 생성기
ReportLab을 사용하여 전문적인 분석 리포트 생성
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import logging

class PDFReportGenerator:
    """PDF 리포트 생성 클래스"""
    
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=2*cm,
            rightMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        self.story = []
        self.styles = getSampleStyleSheet()
        
        # 한글 폰트 등록 시도 (시스템에 없으면 영문 사용)
        try:
            pdfmetrics.registerFont(TTFont('malgun', 'malgun.ttf'))
            self.font_name = 'malgun'
        except:
            self.font_name = 'Helvetica'
            logging.warning("한글 폰트 없음. 영문 폰트 사용")
    
    def add_title(self, text: str):
        """제목 추가"""
        style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#667eea'),
            spaceAfter=20,
            alignment=1  # 중앙 정렬
        )
        self.story.append(Paragraph(text, style))
        self.story.append(Spacer(1, 0.5*cm))
    
    def add_heading(self, text: str):
        """소제목 추가"""
        style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#764ba2'),
            spaceAfter=10
        )
        self.story.append(Paragraph(text, style))
    
    def add_text(self, text: str):
        """일반 텍스트 추가"""
        self.story.append(Paragraph(text, self.styles['Normal']))
        self.story.append(Spacer(1, 0.3*cm))
    
    def add_table(self, data: List[List[str]], col_widths=None):
        """테이블 추가"""
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        self.story.append(table)
        self.story.append(Spacer(1, 0.5*cm))
    
    def add_spacer(self, height_cm=1):
        """여백 추가"""
        self.story.append(Spacer(1, height_cm*cm))
    
    def generate(self):
        """PDF 생성"""
        try:
            self.doc.build(self.story)
            logging.info(f"✅ PDF 리포트 생성 완료: {self.output_path}")
            return True
        except Exception as e:
            logging.error(f"❌ PDF 생성 실패: {e}")
            return False

def create_summary_report(output_dir: Path, summary_data: Dict, keyword_data: Dict, customer_data: List[Dict]):
    """요약 리포트 생성"""
    report_path = output_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf = PDFReportGenerator(report_path)
    
    # 제목
    pdf.add_title("Google Messages Scraper - Analysis Report")
    pdf.add_text(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pdf.add_spacer(0.5)
    
    # 요약 통계
    pdf.add_heading("1. Summary Statistics")
    summary_table = [
        ["Metric", "Value"],
        ["Total Customers", str(summary_data.get('total_customers', 0))],
        ["Total Messages", str(summary_data.get('total_messages', 0))],
        ["Total Attachments", str(summary_data.get('total_attachments', 0))],
        ["Avg Messages/Customer", str(summary_data.get('avg_messages_per_customer', 0))]
    ]
    pdf.add_table(summary_table, col_widths=[8*cm, 8*cm])
    
    # 키워드 분석
    if keyword_data:
        pdf.add_heading("2. Keyword Frequency Analysis")
        keyword_table = [["Keyword", "Count"]]
        for kw, count in sorted(keyword_data.items(), key=lambda x: x[1], reverse=True):
            keyword_table.append([kw, str(count)])
        pdf.add_table(keyword_table, col_widths=[8*cm, 8*cm])
    
    # 고객별 통계 (Top 10)
    if customer_data:
        pdf.add_heading("3. Top 10 Customers by Message Count")
        customer_table = [["Customer", "Total Msgs", "My Msgs", "Attachments"]]
        for cust in customer_data[:10]:
            customer_table.append([
                cust['name'][:30],  # 이름 길이 제한
                str(cust['total_messages']),
                str(cust['my_messages']),
                str(cust['attachments'])
            ])
        pdf.add_table(customer_table, col_widths=[6*cm, 3*cm, 3*cm, 4*cm])
    
    pdf.generate()
    return report_path
