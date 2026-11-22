"""
Email Service - Resend integration for application notifications
"""
import logging
import resend
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Email service using Resend API"""
    
    def __init__(self):
        self.settings = get_settings()
        self.enabled = self.settings.email_enabled and bool(self.settings.resend_api_key)
        
        if self.enabled:
            resend.api_key = self.settings.resend_api_key
            self.from_email = self.settings.resend_from_email
        else:
            logger.info("Email service disabled (no API key or EMAIL_ENABLED=false)")
    
    async def send_application_submitted(
        self,
        applicant_email: str,
        applicant_name: str,
        job_title: str,
        company_name: Optional[str] = None
    ) -> bool:
        """Send confirmation email when application is submitted"""
        if not self.enabled:
            logger.info("Skipping application confirmation email because email notifications are disabled")
            return False
        
        company = company_name or "the company"
        subject = f"Application Received - {job_title}"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ padding: 30px; background: #f9fafb; }}
                .footer {{ padding: 20px; text-align: center; color: #6b7280; font-size: 12px; }}
                .highlight {{ background: #e0e7ff; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                h1 {{ margin: 0; font-size: 24px; }}
                .job-title {{ font-size: 18px; opacity: 0.9; margin-top: 10px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Application Received! ✓</h1>
                <div class="job-title">{job_title}</div>
            </div>
            <div class="content">
                <p>Hi {applicant_name},</p>
                <p>Thank you for applying for the <strong>{job_title}</strong> position at {company}.</p>
                
                <div class="highlight">
                    <strong>What happens next?</strong>
                    <ul>
                        <li>Our team will review your application</li>
                        <li>You'll receive an email when your status changes</li>
                        <li>Shortlisted candidates will be contacted for interviews</li>
                    </ul>
                </div>
                
                <p>We appreciate your interest and will be in touch soon!</p>
                
                <p>Best regards,<br>The Recruitment Team</p>
            </div>
            <div class="footer">
                This is an automated message. Please do not reply directly to this email.
            </div>
        </body>
        </html>
        """
        
        try:
            resend.Emails.send({
                "from": self.from_email,
                "to": applicant_email,
                "subject": subject,
                "html": html_content
            })
            logger.info("Sent application confirmation email")
            return True
        except Exception:
            logger.exception("Failed to send application confirmation email")
            return False
    
    async def send_status_update(
        self,
        applicant_email: str,
        applicant_name: str,
        job_title: str,
        new_status: str,
        company_name: Optional[str] = None
    ) -> bool:
        """Send email when application status changes"""
        if not self.enabled:
            logger.info("Skipping application status email because email notifications are disabled")
            return False
        
        # Only send for these statuses
        if new_status not in ["shortlisted", "accepted", "rejected"]:
            return False
        
        company = company_name or "the company"
        templates = self._get_status_templates(applicant_name, job_title, company, new_status)
        
        try:
            resend.Emails.send({
                "from": self.from_email,
                "to": applicant_email,
                "subject": templates["subject"],
                "html": templates["html"]
            })
            logger.info("Sent application status email")
            return True
        except Exception:
            logger.exception("Failed to send application status email")
            return False
    
    def _get_status_templates(self, name: str, job_title: str, company: str, status: str) -> dict:
        """Get email templates for each status type"""
        
        base_style = """
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }
            .header { color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }
            .content { padding: 30px; background: #f9fafb; }
            .footer { padding: 20px; text-align: center; color: #6b7280; font-size: 12px; }
            h1 { margin: 0; font-size: 24px; }
            .job-title { font-size: 18px; opacity: 0.9; margin-top: 10px; }
            .highlight { padding: 15px; border-radius: 8px; margin: 20px 0; }
        </style>
        """
        
        if status == "shortlisted":
            return {
                "subject": f"Great news! You've been shortlisted - {job_title}",
                "html": f"""
                <!DOCTYPE html>
                <html><head>{base_style}</head>
                <body>
                    <div class="header" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%);">
                        <h1>You've Been Shortlisted! 🎉</h1>
                        <div class="job-title">{job_title}</div>
                    </div>
                    <div class="content">
                        <p>Hi {name},</p>
                        <p>Great news! We've reviewed your application for <strong>{job_title}</strong> at {company}, and you've been <strong>shortlisted</strong> for the next stage.</p>
                        
                        <div class="highlight" style="background: #d1fae5;">
                            <strong>What this means:</strong>
                            <ul>
                                <li>Your profile stood out among applicants</li>
                                <li>We'll reach out soon with next steps</li>
                                <li>Please ensure your contact information is up to date</li>
                            </ul>
                        </div>
                        
                        <p>Congratulations on making it this far!</p>
                        <p>Best regards,<br>The Recruitment Team</p>
                    </div>
                    <div class="footer">This is an automated message.</div>
                </body></html>
                """
            }
        
        elif status == "accepted":
            return {
                "subject": f"Congratulations! You got the job - {job_title}",
                "html": f"""
                <!DOCTYPE html>
                <html><head>{base_style}</head>
                <body>
                    <div class="header" style="background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);">
                        <h1>Congratulations! 🎊</h1>
                        <div class="job-title">{job_title}</div>
                    </div>
                    <div class="content">
                        <p>Hi {name},</p>
                        <p>We are thrilled to inform you that you have been <strong>accepted</strong> for the <strong>{job_title}</strong> position at {company}!</p>
                        
                        <div class="highlight" style="background: #ede9fe;">
                            <strong>Next Steps:</strong>
                            <ul>
                                <li>Our HR team will contact you shortly</li>
                                <li>Prepare any required documentation</li>
                                <li>Get ready to start your new journey!</li>
                            </ul>
                        </div>
                        
                        <p>Welcome to the team! We're excited to have you on board.</p>
                        <p>Best regards,<br>The Recruitment Team</p>
                    </div>
                    <div class="footer">This is an automated message.</div>
                </body></html>
                """
            }
        
        else:  # rejected
            return {
                "subject": f"Application Update - {job_title}",
                "html": f"""
                <!DOCTYPE html>
                <html><head>{base_style}</head>
                <body>
                    <div class="header" style="background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);">
                        <h1>Application Update</h1>
                        <div class="job-title">{job_title}</div>
                    </div>
                    <div class="content">
                        <p>Hi {name},</p>
                        <p>Thank you for your interest in the <strong>{job_title}</strong> position at {company}.</p>
                        
                        <p>After careful consideration, we have decided to move forward with other candidates whose experience more closely matches our current needs.</p>
                        
                        <div class="highlight" style="background: #f3f4f6;">
                            <p>This decision does not reflect on your abilities or potential. We encourage you to:</p>
                            <ul>
                                <li>Apply for other positions that match your skills</li>
                                <li>Continue developing your expertise</li>
                                <li>Keep an eye on future opportunities with us</li>
                            </ul>
                        </div>
                        
                        <p>We wish you the best in your job search and future endeavors.</p>
                        <p>Best regards,<br>The Recruitment Team</p>
                    </div>
                    <div class="footer">This is an automated message.</div>
                </body></html>
                """
            }


# Create a module-level instance that gets recreated on module reload
_email_service_instance = None

def get_email_service() -> EmailService:
    """Dependency injection for email service"""
    global _email_service_instance
    if _email_service_instance is None:
        _email_service_instance = EmailService()
    return _email_service_instance
