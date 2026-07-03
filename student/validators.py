# Shared upload validation (ROADMAP item #3): extension allowlists + size limits.
import os

from django import forms

# Deliverables: documents, archives, images, common source code
ALLOWED_DELIVERABLE_EXTENSIONS = {
    # documents
    '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.csv', '.txt', '.md',
    # archives
    '.zip', '.rar', '.7z', '.tar', '.gz',
    # images
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
    # code / notebooks
    '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.js', '.ts', '.html', '.css',
    '.sql', '.ipynb', '.json', '.xml', '.yml', '.yaml',
}

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

MAX_DELIVERABLE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024         # 5 MB


def _extension(file):
    return os.path.splitext(file.name)[1].lower()


def validate_deliverable_file(file):
    """Validate a deliverable upload: size + extension allowlist."""
    if file.size > MAX_DELIVERABLE_SIZE:
        raise forms.ValidationError(
            "Le fichier est trop volumineux. La taille maximale est de 10 Mo."
        )
    ext = _extension(file)
    if ext not in ALLOWED_DELIVERABLE_EXTENSIONS:
        raise forms.ValidationError(
            f"Type de fichier non autorisé ({ext or 'sans extension'}). "
            "Formats acceptés: documents (PDF, Word, PowerPoint, Excel), "
            "archives (ZIP, RAR, 7Z), images et fichiers de code source."
        )
    return file


def validate_image_file(image):
    """Validate an image upload: size + extension + content type when available."""
    if image.size > MAX_IMAGE_SIZE:
        raise forms.ValidationError("L'image est trop volumineuse (maximum 5MB).")

    ext = _extension(image)
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise forms.ValidationError(
            "Format d'image non autorisé. Formats acceptés: PNG, JPG, GIF, WebP."
        )

    # Only freshly uploaded files carry a content_type; an unchanged existing
    # FieldFile doesn't (and was already validated at upload time).
    content_type = getattr(image, 'content_type', None)
    if content_type and not content_type.startswith('image/'):
        raise forms.ValidationError("Le fichier doit être une image.")

    return image
