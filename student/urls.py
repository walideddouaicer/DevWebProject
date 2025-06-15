

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'student'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<int:project_id>/edit/', views.project_edit, name='project_edit'),
    path('projects/<int:project_id>/delete/', views.project_delete, name='project_delete'),
    path('projects/<int:project_id>/status/<str:new_status>/', views.project_change_status, name='project_change_status'),
    path('projects/<int:project_id>/upload/', views.upload_deliverable, name='upload_deliverable'),
    path('projects/<int:project_id>/milestone/add/', views.add_milestone, name='add_milestone'),
    path('milestone/<int:milestone_id>/toggle/', views.toggle_milestone, name='toggle_milestone'),
    
    # NEW: Confirmation page before submission
    path('projects/<int:project_id>/submit-confirmation/', views.project_submit_confirmation, name='project_submit_confirmation'),
    
    # Existing submission URL (now used after confirmation)
    path('projects/<int:project_id>/submit/', views.project_submit, name='project_submit'),
    
    path('projects/<int:project_id>/approve/', views.project_approve, name='project_approve'),
    path('projects/<int:project_id>/reject/', views.project_reject, name='project_reject'),
    path('milestone/<int:milestone_id>/complete/', views.complete_milestone, name='complete_milestone'),
    path('projects/<int:project_id>/collaborator/add/', views.add_collaborator, name='add_collaborator'),
    path('projects/<int:project_id>/feedback/add/', views.add_feedback, name='add_feedback'),
    path('invitations/', views.invitations_list, name='invitations_list'),
    path('invitations/<int:invitation_id>/cancel/', views.cancel_invitation, name='cancel_invitation'),
    path('invitations/<int:invitation_id>/<str:response>/', views.respond_to_invitation, name='respond_to_invitation'),
    path('projects/<int:project_id>/collaborator/<int:collaborator_id>/remove/', views.remove_collaborator, name='remove_collaborator'),
    
    path('projects/<int:project_id>/comment/', views.add_comment, name='add_comment'),
    
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    # Module-related URLs
    path('modules/join/', views.join_module, name='join_module'),
    path('modules/', views.my_modules, name='my_modules'), 
    path('modules/<int:module_id>/leave/', views.leave_module, name='leave_module'),

    path('projects/<int:project_id>/make-public/', views.make_project_public, name='make_project_public'),
    path('projects/<int:project_id>/make-private/', views.make_project_private, name='make_project_private'),


     # Profile Management URLs
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('settings/', views.profile_settings, name='profile_settings'),
    path('settings/account/', views.account_settings, name='account_settings'),
    path('profile/picture/delete/', views.delete_profile_picture, name='delete_profile_picture'),

    # Password Change URLs
    path('password/change/', auth_views.PasswordChangeView.as_view(
        template_name='student/password_change.html',
        success_url='/student/settings/?tab=account&changed=true'
    ), name='password_change'),
    
    path('password/change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='student/password_change_done.html'
    ), name='password_change_done'),
]