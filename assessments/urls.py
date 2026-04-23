from django.urls import path
from . import views

app_name = 'assessments'

urlpatterns = [
    # Teacher views
    path('teacher/', views.teacher_assessment_list, name='teacher_assessment_list'),
    path('teacher/create/', views.assessment_create, name='assessment_create'),
    path('teacher/<int:assessment_id>/edit/', views.assessment_edit, name='assessment_edit'),
    path('teacher/<int:assessment_id>/questions/', views.question_list, name='question_list'),
    path('teacher/<int:assessment_id>/questions/add/', views.question_add, name='question_add'),
    path('teacher/<int:assessment_id>/questions/<int:question_id>/edit/', views.question_edit, name='question_edit'),
    path('teacher/<int:assessment_id>/questions/<int:question_id>/delete/', views.question_delete, name='question_delete'),
    path('teacher/<int:assessment_id>/publish/', views.assessment_publish, name='assessment_publish'),

    # Student views
    path('', views.student_assessment_list, name='student_assessment_list'),
    path('<int:assessment_id>/', views.assessment_detail, name='assessment_detail'),
    path('<int:assessment_id>/take/', views.assessment_take, name='assessment_take'),
    path('<int:assessment_id>/submit/', views.assessment_submit, name='assessment_submit'),
    path('<int:assessment_id>/results/', views.assessment_results, name='assessment_results'),
    path('<int:assessment_id>/attempts/', views.attempt_history, name='attempt_history'),

    # AJAX endpoints
    path('<int:assessment_id>/start/', views.start_attempt, name='start_attempt'),
    path('attempt/<int:attempt_id>/save/', views.save_answer, name='save_answer'),
]