"""
Resume Parser Service - Extract text from PDF/DOCX and parse with LLM
"""
import os
import re
import pymupdf as fitz
from uuid import uuid4
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from app.config import get_settings
from app.services.llm_provider import LLMProvider

settings = get_settings()


def redact_resume_identifiers(text: str) -> str:
    """Mask direct contact identifiers before resume text is sent to the LLM provider."""
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[EMAIL REDACTED]", text, flags=re.IGNORECASE)

    def redact_phone(match):
        digits = re.sub(r"\D", "", match.group(0))
        return "[PHONE REDACTED]" if 10 <= len(digits) <= 15 else match.group(0)

    text = re.sub(r"(?<!\w)\+?\d[\d .()/-]{8,}\d(?!\w)", redact_phone, text)
    text = re.sub(r"\b(?:https?://|www\.)\S+", "[PROFILE LINK REDACTED]", text, flags=re.IGNORECASE)

    lines = text.splitlines()
    nonempty = [index for index, line in enumerate(lines) if line.strip()]
    if nonempty:
        first_index = nonempty[0]
        first_line = lines[first_index].strip()
        contact_window = " ".join(lines[first_index + 1:first_index + 4])
        words = re.findall(r"[A-Za-z][A-Za-z'-]*", first_line)
        if (
            2 <= len(words) <= 4
            and len(first_line) <= 64
            and re.search(r"(?:\[EMAIL REDACTED\]|\[PHONE REDACTED\]|\[PROFILE LINK REDACTED\])", contact_window)
            and not re.search(r"\b(?:resume|curriculum|vitae|profile|summary|experience|engineer|developer|manager|designer|analyst|consultant)\b", first_line, re.IGNORECASE)
        ):
            lines[first_index] = "[NAME REDACTED]"
    return "\n".join(lines)


class ResumeParser:
    """
    Resume text extraction and LLM-based parsing
    """
    
    def __init__(self):
        self.llm = LLMProvider()
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """
        Extract text from PDF using PyMuPDF.
        Falls back to OCR for scanned PDFs if available.
        """
        text_parts = []
        
        with fitz.open(file_path) as doc:
            for page_num, page in enumerate(doc):
                # Try direct text extraction first
                text = page.get_text()
                
                if text.strip():
                    text_parts.append(text)
                elif OCR_AVAILABLE:
                    # Fallback to OCR for scanned pages
                    pix = page.get_pixmap()
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr_text = pytesseract.image_to_string(img)
                    text_parts.append(ocr_text)
        
        return "\n".join(text_parts)
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        if not DOCX_AVAILABLE:
            raise ImportError("python-docx is not installed")
        
        doc = Document(file_path)
        text_parts = []
        
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        
        # Also extract from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text)
        
        return "\n".join(text_parts)
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract text from resume file (PDF or DOCX)
        """
        file_path = str(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".pdf":
            return self.extract_text_from_pdf(file_path)
        elif ext in [".docx", ".doc"]:
            return self.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
    
    async def parse_resume(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text from resume and parse with LLM.
        
        Returns:
            Structured resume data (skills, education, experience, etc.)
        """
        # Extract text
        text = self.extract_text(file_path)
        
        if not text.strip():
            return {"error": "No text could be extracted from the resume"}
        
        # Redact direct identifiers before the document leaves this application.
        parsed = await self.llm.parse_resume(redact_resume_identifiers(text))
        
        return parsed
    
    def save_uploaded_file(self, file_content: bytes, filename: str, user_id: int) -> str:
        """
        Save uploaded resume file to disk.
        
        Returns:
            Path to saved file
        """
        # Create user directory
        user_dir = self.upload_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Never use an uploaded filename as a path. Keep the extension for parsing,
        # but generate the stored name locally to prevent path traversal and collisions.
        suffix = Path(filename).suffix.lower()
        file_path = user_dir / f"{uuid4().hex}{suffix}"
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return str(file_path)


# Singleton instance
resume_parser = ResumeParser()


def get_resume_parser() -> ResumeParser:
    """Dependency for getting resume parser"""
    return resume_parser
