
import os
import uuid

from django.conf import settings
from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='projects'
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = 'TODO', 'К выполнению'
        PROGRESS = 'PROGRESS', 'В процессе'
        DONE = 'DONE', 'Завершено'

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks'
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks'
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.TODO
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['project', 'status']),
        ]


class NotificationDelivery(models.Model):
    event_id = models.CharField(max_length=100, unique=True)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.event_id


def task_attachment_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    return f'task_attachments/{uuid.uuid4()}{extension}'


class TaskAttachment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='attachments'
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    file = models.FileField(upload_to=task_attachment_upload_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name


class WebhookEvent(models.Model):
    event_id = models.CharField(max_length=100, unique=True)

    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name='webhook_events'
    )

    status = models.CharField(max_length=20)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.event_id
