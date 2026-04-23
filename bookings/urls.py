from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    # Teacher availability management
    path('teacher/availability/', views.teacher_availability_list, name='teacher_availability_list'),
    path('teacher/availability/create/', views.teacher_availability_create, name='teacher_availability_create'),
    path('teacher/availability/<int:availability_id>/edit/', views.teacher_availability_edit, name='teacher_availability_edit'),
    path('teacher/availability/<int:availability_id>/delete/', views.teacher_availability_delete, name='teacher_availability_delete'),

    # Booking management
    path('teacher/bookings/', views.teacher_booking_list, name='teacher_booking_list'),
    path('teacher/bookings/<int:booking_id>/', views.teacher_booking_detail, name='teacher_booking_detail'),
    path('teacher/bookings/<int:booking_id>/confirm/', views.confirm_booking, name='confirm_booking'),
    path('teacher/bookings/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('teacher/bookings/<int:booking_id>/complete/', views.complete_booking, name='complete_booking'),

    # Student booking
    path('student/teachers/', views.student_teacher_list, name='student_teacher_list'),
    path('student/teacher/<int:teacher_id>/availability/', views.teacher_availability_view, name='teacher_availability_view'),
    path('student/book/', views.student_book_session, name='student_book_session'),
    path('student/bookings/', views.student_booking_list, name='student_booking_list'),
    path('student/bookings/<int:booking_id>/', views.student_booking_detail, name='student_booking_detail'),
    path('student/bookings/<int:booking_id>/cancel/', views.student_cancel_booking, name='student_cancel_booking'),
    path('student/bookings/<int:booking_id>/classroom/', views.student_live_classroom, name='student_live_classroom'),
    path('teacher/bookings/<int:booking_id>/classroom/', views.teacher_live_classroom, name='teacher_live_classroom'),
    path('live/<str:room_name>/', views.booking_live_room_entry, name='booking_live_room_entry'),
]
