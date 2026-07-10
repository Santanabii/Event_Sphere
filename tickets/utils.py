import qrcode
import io
import base64
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent,
    FileName, FileType, Disposition
)
from django.conf import settings


def generate_qr_code(token):
    """Generate QR code image from token."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(str(token))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def generate_pdf_ticket(ticket):
    """Generate a PDF ticket with QR code."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Title
    p.setFont("Helvetica-Bold", 24)
    p.drawCentredString(width / 2, height - 80, "EventSphere")

    # Event details
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(
        width / 2,
        height - 130,
        ticket.tier.event.title
    )

    p.setFont("Helvetica", 12)
    p.drawCentredString(
        width / 2,
        height - 160,
        f"Venue: {ticket.tier.event.venue}"
    )
    p.drawCentredString(
        width / 2,
        height - 180,
        f"Date: {ticket.tier.event.date.strftime('%B %d, %Y at %I:%M %p')}"
    )
    p.drawCentredString(
        width / 2,
        height - 200,
        f"Tier: {ticket.tier.name}"
    )
    p.drawCentredString(
        width / 2,
        height - 220,
        f"Price: KES {ticket.purchase_price}"
    )
    p.drawCentredString(
        width / 2,
        height - 240,
        f"Owner: {ticket.owner.email}"
    )

    # QR Code
    # drawInlineImage() requires a real PIL Image (it reads .format internally).
    # A raw io.BytesIO has no .format attribute, which is exactly what was
    # crashing here. ImageReader is built to accept file-like objects directly,
    # so drawImage() + ImageReader is the correct pairing for a BytesIO buffer.
    qr_buffer = generate_qr_code(ticket.qr_token)
    qr_buffer.seek(0)

    p.drawImage(
        ImageReader(qr_buffer),
        width / 2 - 100,
        height - 460,
        200,
        200
    )

    p.setFont("Helvetica", 10)
    p.drawCentredString(
        width / 2,
        height - 480,
        f"Ticket ID: {ticket.qr_token}"
    )

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


def send_ticket_email(ticket):
    """Send ticket email with PDF attachment."""
    pdf_buffer = generate_pdf_ticket(ticket)
    pdf_data = base64.b64encode(pdf_buffer.read()).decode()

    message = Mail(
        from_email=settings.SENDGRID_SENDER_EMAIL,
        to_emails=ticket.owner.email,
        subject=f"Your ticket for {ticket.tier.event.title}",
        html_content=f"""
            <h2>Your EventSphere Ticket</h2>
            <p>Hi {ticket.owner.username},</p>
            <p>Thank you for purchasing a ticket for 
            <strong>{ticket.tier.event.title}</strong>!</p>
            <p><strong>Event Details:</strong></p>
            <ul>
                <li>Venue: {ticket.tier.event.venue}</li>
                <li>Date: {ticket.tier.event.date.strftime('%B %d, %Y at %I:%M %p')}</li>
                <li>Tier: {ticket.tier.name}</li>
                <li>Price: KES {ticket.purchase_price}</li>
            </ul>
            <p>Your ticket is attached as a PDF. 
            Please present the QR code at the entrance.</p>
            <p>See you there!</p>
            <p>EventSphere Team</p>
        """
    )

    attachment = Attachment(
        FileContent(pdf_data),
        FileName(f"ticket_{ticket.qr_token}.pdf"),
        FileType("application/pdf"),
        Disposition("attachment")
    )
    message.attachment = attachment

    sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
    sg.send(message)