from django.contrib.auth.models import User
from django.db import models


class PendingRegistration(models.Model):
    """Store pending registrations until admin approval"""

    ROLE_CHOICES = [
        ("student", "Étudiant"),
        ("teacher", "Enseignant"),
        ("administrator", "Administrateur"),
    ]

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)  # Will be hashed
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # Role-specific fields
    student_id = models.CharField(max_length=20, blank=True, null=True)
    teacher_id = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True)
    year_of_study = models.IntegerField(null=True, blank=True)

    # Status tracking
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.role}"

    # ============================================
    # FORMS FOR SIGNUP
    # ============================================

    def approve(self, by):
        """Create the account and its role profile atomically, then email the user.

        `by` is the approving User. Raises ValidationError if already approved and
        IntegrityError if the username/email/ID is taken in the meantime (nothing is
        left half-created in that case).
        """
        from django.core.exceptions import ValidationError
        from django.db import transaction
        from django.utils import timezone

        from administrator.models import AdminProfile
        from student.models import StudentProfile
        from teacher.models import TeacherProfile

        from .utils import send_approval_email

        if self.is_approved:
            raise ValidationError("Cette demande a déjà été approuvée.")
        with transaction.atomic():
            user = User(
                username=self.username,
                email=self.email,
                first_name=self.first_name,
                last_name=self.last_name,
                is_active=True,
            )
            user.password = self.password  # already hashed at signup
            user.save()
            if self.role == "student":
                StudentProfile.objects.create(
                    user=user,
                    student_id=self.student_id,
                    year_of_study=self.year_of_study,
                    department=self.department,
                )
            elif self.role == "teacher":
                TeacherProfile.objects.create(
                    user=user, teacher_id=self.teacher_id or None, department=self.department
                )
            elif self.role == "administrator":
                AdminProfile.objects.create(
                    user=user, department=self.department or "Administration"
                )
            self.is_approved = True
            self.approved_by = by
            self.approved_at = timezone.now()
            self.save()
            transaction.on_commit(lambda: send_approval_email(self))
        return user
