"""
Email service using Resend.

Handles all transactional emails:
- Newsletter delivery
- Subscription confirmations
- Password reset
- Welcome emails
"""

import resend
import logging
from typing import Optional, List
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize Resend
if settings.resend_api_key:
    resend.api_key = settings.resend_api_key


async def send_email(
    to: str | List[str],
    subject: str,
    html: str,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None,
    tags: Optional[List[dict]] = None
) -> dict:
    """
    Send an email using Resend.
    
    Args:
        to: Recipient email(s)
        subject: Email subject line
        html: HTML content
        from_email: Sender email (defaults to settings.from_email)
        reply_to: Reply-to address
        tags: List of tags for tracking (e.g., [{"name": "category", "value": "newsletter"}])
    
    Returns:
        Resend API response with email ID
    """
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured. Email not sent.")
        return {"id": None, "error": "Email service not configured"}
    
    try:
        params = {
            "from": from_email or settings.from_email,
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "html": html,
        }
        
        if reply_to:
            params["reply_to"] = reply_to
        
        if tags:
            params["tags"] = tags
        
        response = resend.Emails.send(params)
        logger.info(f"Email sent successfully: {response.get('id')}")
        return response
        
    except Exception as e:
        logger.exception(f"Failed to send email to {to}: {e}")
        raise


async def send_newsletter(
    to: str | List[str],
    subject: str,
    html_content: str,
    unsubscribe_url: str,
    topic_name: str
) -> dict:
    """
    Send a newsletter email with proper headers.
    
    Includes:
    - List-Unsubscribe header for one-click unsubscribe
    - Proper tagging for analytics
    """
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured. Newsletter not sent.")
        return {"id": None, "error": "Email service not configured"}
    
    try:
        params = {
            "from": settings.from_email,
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "html": html_content,
            "headers": {
                "List-Unsubscribe": f"<{unsubscribe_url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
            },
            "tags": [
                {"name": "category", "value": "newsletter"},
                {"name": "topic", "value": topic_name}
            ]
        }
        
        response = resend.Emails.send(params)
        logger.info(f"Newsletter sent: {response.get('id')}")
        return response
        
    except Exception as e:
        logger.exception(f"Failed to send newsletter: {e}")
        raise


async def send_password_reset(
    to: str,
    reset_url: str,
    expires_in_minutes: int = 60
) -> dict:
    """Send password reset email."""
    html = f"""
    <h2>Reset Your Password</h2>
    <p>Click the link below to reset your password:</p>
    <p><a href="{reset_url}" style="background-color: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Reset Password</a></p>
    <p>This link will expire in {expires_in_minutes} minutes.</p>
    <p>If you didn't request this, you can safely ignore this email.</p>
    """
    
    return await send_email(
        to=to,
        subject="Reset your password",
        html=html,
        tags=[{"name": "category", "value": "password-reset"}]
    )


async def send_welcome_email(
    to: str,
    name: Optional[str] = None
) -> dict:
    """Send welcome email to new users."""
    greeting = f"Hi {name}," if name else "Welcome!"
    
    html = f"""
    <h2>{greeting}</h2>
    <p>Thanks for signing up for Evidence Synthesis Newsletter!</p>
    <p>Here's what you can do:</p>
    <ul>
        <li>Create custom topics for literature monitoring</li>
        <li>Review papers with our human-in-the-loop interface</li>
        <li>Generate beautiful newsletters automatically</li>
    </ul>
    <p><a href="{settings.frontend_url}/dashboard" style="background-color: #4F46E5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Go to Dashboard</a></p>
    """
    
    return await send_email(
        to=to,
        subject="Welcome to Evidence Synthesis Newsletter!",
        html=html,
        tags=[{"name": "category", "value": "welcome"}]
    )
