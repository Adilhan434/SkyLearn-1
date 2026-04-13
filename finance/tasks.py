from celery import shared_task
from django.core.mail import send_mail


@shared_task
def send_payment_notification(payment_id, student_id, amount):
    print(f"Payment {payment_id} processed for student {student_id}, amount {amount}")