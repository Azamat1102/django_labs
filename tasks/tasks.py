
from celery import shared_task
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from tasks.models import NotificationDelivery, Task


@shared_task(bind=True, max_retries=5)
def send_assignment_notification(self, task_id, assignee_id, event_id):
    try:
        with transaction.atomic():
            delivery = NotificationDelivery.objects.select_for_update().get(
                event_id=event_id
            )

            if delivery.sent_at:
                return 'Уведомление уже отправлено'

            task = Task.objects.get(id=task_id)

            send_mail(
                subject='Вам назначена новая задача',
                message=f'Вам назначена задача: {task.title}',
                from_email=None,
                recipient_list=[delivery.assignee.email],
                fail_silently=False
            )

            delivery.sent_at = timezone.now()
            delivery.save(update_fields=['sent_at'])

        return 'Уведомление отправлено'

    except Exception as error:
        raise self.retry(
            exc=error,
            countdown=2 ** self.request.retries
        )
