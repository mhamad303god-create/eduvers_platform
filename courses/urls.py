from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Course listing and detail
    path('', views.course_list, name='course_list'),
    path('<int:course_id>/', views.course_detail, name='course_detail'),

    # Course management (teachers)
    path('create/', views.course_create, name='course_create'),
    path('<int:course_id>/edit/', views.course_edit, name='course_edit'),
    path('teacher/', views.teacher_course_list, name='teacher_course_list'),
    path('<int:course_id>/download-preview/', views.download_course_preview, name='download_course_preview'),
    path('<int:course_id>/download-lessons/', views.download_course_lessons_bundle, name='download_course_lessons_bundle'),

    # Lesson management
    path('<int:course_id>/lessons/create/', views.lesson_create, name='lesson_create'),
    path('<int:course_id>/lessons/<int:lesson_id>/edit/', views.lesson_edit, name='lesson_edit'),
    path('<int:course_id>/lessons/<int:lesson_id>/delete/', views.lesson_delete, name='lesson_delete'),
    path('<int:course_id>/lessons/publish-all/', views.publish_all_lessons, name='publish_all_lessons'),

    # Enrollment
    path('<int:course_id>/enroll/', views.enroll_course, name='enroll_course'),

    # Lesson viewing and progress
    path('<int:course_id>/lessons/<int:lesson_id>/', views.lesson_view, name='lesson_view'),
    path('<int:course_id>/lessons/<int:lesson_id>/download/', views.download_lesson_video, name='download_lesson_video'),
    path('lessons/<int:lesson_id>/complete/', views.mark_lesson_complete, name='mark_lesson_complete'),

    # API endpoints
    path('api/', views.api_courses_list, name='api_courses_list'),
    path('api/<int:course_id>/', views.api_course_detail, name='api_course_detail'),
    
    # Advanced Search
    path('search/', views.advanced_search, name='advanced_search'),
    path('api/search/courses/', views.api_search_courses, name='api_search_courses'),
    path('api/search/teachers/', views.api_search_teachers, name='api_search_teachers'),
    path('api/recommendations/', views.api_recommendations, name='api_recommendations'),
    path('api/trending/', views.api_trending_courses, name='api_trending_courses'),
    
    # Analytics Dashboard
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    
    # Certificates
    path('certificate/<str:certificate_id>/', views.certificate_view, name='certificate_view'),
    path('certificate/<str:certificate_id>/verify/', views.verify_certificate, name='verify_certificate'),
]
