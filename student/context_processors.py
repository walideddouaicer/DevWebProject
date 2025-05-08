# Add to a new file called context_processors.py
from .models import StudentProfile, CollaborationInvitation

def invitation_count(request):
    """Context processor to provide invitation count"""
    if request.user.is_authenticated:
        try:
            student = StudentProfile.objects.get(user=request.user)
            count = CollaborationInvitation.objects.filter(
                recipient=student,
                status='pending'
            ).count()
            return {'invitation_count': count}
        except StudentProfile.DoesNotExist:
            pass
    return {'invitation_count': 0}