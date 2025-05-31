# Add to a new file called context_processors.py
from .models import StudentProfile, CollaborationInvitation, Notification

def student_context(request):
    """Combined context processor for invitations and notifications"""
    context = {
        'invitation_count': 0,
        'unread_notifications_count': 0
    }
    
    if request.user.is_authenticated:
        try:
            student = StudentProfile.objects.get(user=request.user)
            # Invitation count
            context['invitation_count'] = CollaborationInvitation.objects.filter(
                recipient=student,
                status='pending'
            ).count()
            # Unread notifications count
            context['unread_notifications_count'] = Notification.objects.filter(
                recipient=student,
                is_read=False
            ).count()
        except StudentProfile.DoesNotExist:
            pass
    return context