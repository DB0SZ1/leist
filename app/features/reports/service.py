import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from app.features.jobs.models import Job
from app.features.workspaces.models import Workspace

def generate_client_report(job: Job, workspace: Workspace | None) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Branding
    company_name = "List Intel"
    brand_color = colors.HexColor("#1b6015")
    
    if workspace:
        company_name = workspace.brand_company_name or workspace.name
        if workspace.brand_color:
            try:
                brand_color = colors.HexColor(workspace.brand_color)
            except:
                pass

    # Header Background
    c.setFillColor(brand_color)
    c.rect(0, height - 100, width, 100, fill=1, stroke=0)
    
    # Header Text
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(40, height - 60, company_name)
    c.setFont("Helvetica", 12)
    c.drawString(40, height - 80, "Campaign Intelligence Audit")
    
    # Job Info
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, height - 140, "Executive Summary")
    
    c.setFont("Helvetica", 12)
    s = job.summary or {}
    total = job.total_emails or 0
    fresh = s.get("fresh", 0)
    burned = s.get("burned", 0)
    
    c.drawString(40, height - 170, f"List Analyzed: {job.input_file_path.split('_', 1)[-1] if '_' in job.input_file_path else job.input_file_path}")
    c.drawString(40, height - 190, f"Total Contacts: {total:,}")
    c.drawString(40, height - 210, f"Fresh Leads: {fresh:,} ({(fresh/total*100) if total else 0:.1f}%)")
    c.drawString(40, height - 230, f"Burned Leads: {burned:,} ({(burned/total*100) if total else 0:.1f}%)")
    
    # Key Risk Factors
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, height - 280, "Target Infrastructure Risks")
    
    c.setFont("Helvetica", 12)
    mimecast = s.get("mimecast", 0)
    proofpoint = s.get("proofpoint", 0)
    catchall = s.get("catchall", 0)
    
    y = height - 310
    c.drawString(40, y, f"Enterprise Gateways (Mimecast): {mimecast:,}")
    y -= 20
    c.drawString(40, y, f"Enterprise Gateways (Proofpoint): {proofpoint:,}")
    y -= 20
    c.drawString(40, y, f"Catch-All Domains: {catchall:,}")
    
    # Recommendations
    y -= 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Action Plan")
    y -= 30
    c.setFont("Helvetica", 12)
    
    if (burned / (total or 1)) > 0.3:
        c.drawString(40, y, "• Do NOT send to this list as-is. High saturation detected.")
        y -= 20
        c.drawString(40, y, "• Use the Auto-Fix tool to remove burned leads before campaign launch.")
        y -= 20
    else:
        c.drawString(40, y, "• Normal saturation levels. Safe for standard warmup volume.")
        y -= 20
        
    if mimecast > (total * 0.1):
        c.drawString(40, y, "• Warning: High percentage of Mimecast filters. Prepare secondary domains.")
        y -= 20
        
    c.drawString(40, 40, f"Generated for {company_name} powered by List Intel")
    
    c.save()
    return buffer.getvalue()
