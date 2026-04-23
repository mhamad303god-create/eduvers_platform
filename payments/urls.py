from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment history
    path('', views.payment_list, name='payment_list'),

    # Course checkout
    path('courses/<int:course_id>/checkout/', views.course_checkout, name='course_checkout'),

    # Payment details
    path('<uuid:payment_uuid>/', views.payment_detail, name='payment_detail'),

    # Make payment
    path('process/', views.process_payment, name='process_payment'),
    path('create-intent/', views.create_intent, name='create_intent'),
    path('confirm/<uuid:payment_id>/', views.confirm_payment, name='confirm_payment'),

    # Payment success/failure
    path('success/', views.payment_success, name='payment_success'),
    path('failure/', views.payment_failure, name='payment_failure'),

    # Refund request
    path('<uuid:payment_uuid>/refund/', views.request_refund, name='request_refund'),
]
