from django.urls import path
from rest_framework.routers import DefaultRouter
from tasks.views import TaskWebhookView

from tasks.views import (
    ProjectViewSet,
    TaskViewSet,
    TaskAttachmentListCreateView,
    TaskAttachmentDetailView,
    TaskWebhookView
)
router = DefaultRouter()

router.register('projects', ProjectViewSet, basename='project')
router.register('tasks', TaskViewSet, basename='task')

urlpatterns = [
    path(
        'tasks/<int:task_id>/attachments/',
        TaskAttachmentListCreateView.as_view(),
        name='task-attachments'
    ),
path(
    'webhooks/task-events/',
    TaskWebhookView.as_view(),
    name='task-webhook'
),
    path(
        'tasks/<int:task_id>/attachments/<int:attachment_id>/',
        TaskAttachmentDetailView.as_view(),
        name='task-attachment-detail'
    ),
] + router.urls

path(
    'webhooks/task-events/',
    TaskWebhookView.as_view(),
    name='task-webhook'
),