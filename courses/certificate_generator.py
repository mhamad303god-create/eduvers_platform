# ===== Certificate Generator with PDF and QR Code =====
# Professional certificate generation system

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from .models import Certificate, Enrollment
import uuid
import os
import logging

logger = logging.getLogger(__name__)


class CertificateGenerator:
    """
    Professional certificate generator with:
    - Custom designs
    - QR code for verification
    - PDF generation
    - Digital signatures
    """
    
    def __init__(self):
        self.page_width, self.page_height = landscape(A4)
        self.certificate_id_prefix = "EDU-CERT"
        
    def generate_certificate(self, enrollment):
        """
        Generate certificate for completed enrollment
        
        Args:
            enrollment: Enrollment instance
        
        Returns:
            Certificate instance
        """
        if enrollment.status != 'completed':
            raise ValueError("Cannot generate certificate for incomplete enrollment")
        
        # Check if certificate already exists
        existing = Certificate.objects.filter(enrollment=enrollment).first()
        if existing:
            logger.info(f"Certificate already exists: {existing.certificate_id}")
            return existing
        
        # Generate certificate ID
        cert_id = f"{self.certificate_id_prefix}-{uuid.uuid4().hex[:8].upper()}"
        
        # Create certificate record
        certificate = Certificate.objects.create(
            enrollment=enrollment,
            certificate_id=cert_id,
            issued_date=timezone.now(),
            is_verified=True
        )
        
        # Generate PDF
        pdf_buffer = self._generate_pdf(certificate)
        
        # Save PDF file
        pdf_filename = f"certificate_{cert_id}.pdf"
        certificate.certificate_file.save(
            pdf_filename,
            ContentFile(pdf_buffer.getvalue()),
            save=True
        )
        
        # Generate and save QR code
        qr_buffer = self._generate_qr_code(certificate)
        qr_filename = f"qr_{cert_id}.png"
        certificate.qr_code.save(
            qr_filename,
            ContentFile(qr_buffer.getvalue()),
            save=True
        )
        
        logger.info(f"Certificate generated: {cert_id}")
        
        return certificate
    
    def _generate_pdf(self, certificate):
        """Generate PDF certificate"""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=landscape(A4))
        
        enrollment = certificate.enrollment
        student_name = enrollment.student.user.get_full_name()
        course_title = enrollment.course.title
        teacher_name = enrollment.course.teacher.user.get_full_name()
        issue_date = certificate.issued_date.strftime("%B %d, %Y")
        cert_id = certificate.certificate_id
        
        # Background (you can add a background image here)
        # c.drawImage('path/to/background.png', 0, 0, width=self.page_width, height=self.page_height)
        
        # Border
        c.setStrokeColor(colors.HexColor('#1a73e8'))
        c.setLineWidth(3)
        c.rect(20*mm, 20*mm, self.page_width - 40*mm, self.page_height - 40*mm)
        
        c.setLineWidth(1)
        c.rect(22*mm, 22*mm, self.page_width - 44*mm, self.page_height - 44*mm)
        
        # Title
        c.setFillColor(colors.HexColor('#1a73e8'))
        c.setFont("Helvetica-Bold", 36)
        title = "Certificate of Completion"
        title_width = c.stringWidth(title, "Helvetica-Bold", 36)
        c.drawString((self.page_width - title_width) / 2, self.page_height - 60*mm, title)
        
        # Subtitle
        c.setFont("Helvetica", 14)
        c.setFillColor(colors.HexColor('#666666'))
        subtitle = "This is to certify that"
        subtitle_width = c.stringWidth(subtitle, "Helvetica", 14)
        c.drawString((self.page_width - subtitle_width) / 2, self.page_height - 75*mm, subtitle)
        
        # Student name
        c.setFont("Helvetica-Bold", 28)
        c.setFillColor(colors.HexColor('#1a73e8'))
        name_width = c.stringWidth(student_name, "Helvetica-Bold", 28)
        c.drawString((self.page_width - name_width) / 2, self.page_height - 95*mm, student_name)
        
        # Draw underline under name
        c.setStrokeColor(colors.HexColor('#1a73e8'))
        c.setLineWidth(2)
        c.line((self.page_width - name_width) / 2 - 10*mm, self.page_height - 97*mm,
               (self.page_width + name_width) / 2 + 10*mm, self.page_height - 97*mm)
        
        # Course completion text
        c.setFont("Helvetica", 14)
        c.setFillColor(colors.HexColor('#333333'))
        completion_text = "has successfully completed the course"
        comp_width = c.stringWidth(completion_text, "Helvetica", 14)
        c.drawString((self.page_width - comp_width) / 2, self.page_height - 110*mm, completion_text)
        
        # Course title
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(colors.HexColor('#1a73e8'))
        course_width = c.stringWidth(course_title, "Helvetica-Bold", 20)
        c.drawString((self.page_width - course_width) / 2, self.page_height - 125*mm, course_title)
        
        # Date
        c.setFont("Helvetica", 12)
        c.setFillColor(colors.HexColor('#666666'))
        date_text = f"Issued on: {issue_date}"
        date_width = c.stringWidth(date_text, "Helvetica", 12)
        c.drawString((self.page_width - date_width) / 2, self.page_height - 140*mm, date_text)
        
        # Signatures section
        y_signature = 40*mm
        
        # Teacher signature
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor('#333333'))
        c.drawString(60*mm, y_signature + 15*mm, "_" * 30)
        c.drawString(60*mm, y_signature + 10*mm, "Instructor Signature")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(60*mm, y_signature + 5*mm, teacher_name)
        
        # Platform signature
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor('#333333'))
        c.drawString(self.page_width - 120*mm, y_signature + 15*mm, "_" * 30)
        c.drawString(self.page_width - 120*mm, y_signature + 10*mm, "Platform Director")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(self.page_width - 120*mm, y_signature + 5*mm, "EduVerse Platform")
        
        # Certificate ID
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor('#999999'))
        cert_id_text = f"Certificate ID: {cert_id}"
        c.drawString(25*mm, 25*mm, cert_id_text)
        
        # QR Code placeholder text
        c.drawString(self.page_width - 70*mm, 25*mm, "Scan to verify")
        
        # Add QR code
        qr_buffer = self._generate_qr_code(certificate)
        qr_image = ImageReader(qr_buffer)
        c.drawImage(qr_image, self.page_width - 65*mm, 30*mm, 
                   width=40*mm, height=40*mm, mask='auto')
        
        # Footer
        c.setFont("Helvetica", 8)
        footer_text = "EduVerse - Empowering Education"
        footer_width = c.stringWidth(footer_text, "Helvetica", 8)
        c.drawString((self.page_width - footer_width) / 2, 15*mm, footer_text)
        
        c.showPage()
        c.save()
        
        buffer.seek(0)
        return buffer
    
    def _generate_qr_code(self, certificate):
        """Generate QR code for certificate verification"""
        # Create verification URL
        base_url = getattr(settings, 'SITE_URL', 'https://eduverse.com')
        verification_url = f"{base_url}/certificates/verify/{certificate.certificate_id}/"
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(verification_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to buffer
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer
    
    def verify_certificate(self, certificate_id):
        """
        Verify certificate authenticity
        
        Returns:
            dict with verification result
        """
        try:
            certificate = Certificate.objects.select_related(
                'enrollment__student__user',
                'enrollment__course'
            ).get(certificate_id=certificate_id)
            
            return {
                'valid': True,
                'certificate_id': certificate.certificate_id,
                'student_name': certificate.enrollment.student.user.get_full_name(),
                'course_title': certificate.enrollment.course.title,
                'issued_date': certificate.issued_date.strftime("%B %d, %Y"),
                'is_verified': certificate.is_verified,
            }
            
        except Certificate.DoesNotExist:
            return {
                'valid': False,
                'error': 'Certificate not found'
            }


class CertificateTemplate:
    """Customizable certificate templates"""
    
    TEMPLATES = {
        'classic': {
            'border_color': '#1a73e8',
            'title_color': '#1a73e8',
            'text_color': '#333333',
        },
        'elegant': {
            'border_color': '#8b5cf6',
            'title_color': '#8b5cf6',
            'text_color': '#1e293b',
        },
        'modern': {
            'border_color': '#10b981',
            'title_color': '#10b981',
            'text_color': '#111827',
        },
    }
    
    @classmethod
    def get_template(cls, template_name='classic'):
        """Get certificate template configuration"""
        return cls.TEMPLATES.get(template_name, cls.TEMPLATES['classic'])
