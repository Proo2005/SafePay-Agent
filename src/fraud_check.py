from pypdf import PdfReader
import os

def check_pdf_integrity(file_path):
    """
    Scans a PDF for signs of tampering or editing software.
    Returns: (is_suspicious, reason)
    """
    try:
        if not file_path or not os.path.exists(file_path):
            return False, "File not found skipped check"

        reader = PdfReader(file_path)
        metadata = reader.metadata
        
        if not metadata:
            return True, "No metadata found (Suspicious: Metadata might be wiped)"

        # 1. Check the "Producer" (Software used to make the PDF)
        # We handle cases where metadata might be None
        producer = metadata.get('/Producer', '').lower() if metadata.get('/Producer') else ''
        creator = metadata.get('/Creator', '').lower() if metadata.get('/Creator') else ''
        
        # List of red-flag software (Editing tools vs Accounting tools)
        suspicious_software = ['photoshop', 'gimp', 'illustrator', 'inkscape', 'canva']
        
        for software in suspicious_software:
            if software in producer or software in creator:
                return True, f"Tampering Detected: File created using {software.capitalize()}"

        return False, f"File seems clean. Created by: {metadata.get('/Producer', 'Unknown')}"

    except Exception as e:
        # If we can't read it, we treat it as suspicious or just log error
        return True, f"Error reading file: {str(e)}"