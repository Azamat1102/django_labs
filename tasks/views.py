import json
import time
import uuid

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Membership, Role
from tasks.models import (
    NotificationDelivery,
    Project,
    Task,
    TaskAttachment,
    WebhookEvent,
)
from tasks.pagination import TaskPagination
from tasks.permissions import TaskAccessPermission, is_project_admin, is_project_member
from tasks.serializers import (
    ProjectSerializer,
    TaskAttachmentSerializer,
    TaskSerializer,
)
from tasks.services import create_project, invalidate_project_stats
from tasks.tasks import send_assignment_notification
from tasks.webhooks import verify_webhook_signature


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return Project.objects.filter(
            Q(owner=self.request.user) |
            Q(members__user=self.request.user)
        ).distinct()

    def perform_create(self, serializer):
        create_project(
            owner=self.request.user,
            name=serializer.validated_data['name'],
            description=serializer.validated_data.get('description', '')
        )

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        project = self.get_object()

        cache_key = f'project-stats:v1:{project.id}'

        cached_stats = cache.get(cache_key)

        if cached_stats is not None:
            return Response(cached_stats)

        tasks = project.tasks.aggregate(
            total=Count('id'),
            todo=Count('id', filter=Q(status=Task.Status.TODO)),
            progress=Count('id', filter=Q(status=Task.Status.PROGRESS)),
            done=Count('id', filter=Q(status=Task.Status.DONE))
        )

        cache.set(cache_key, tasks, 60)

        return Response(tasks)

    @action(detail=True, methods=['post'])
    def members(self, request, pk=None):
        project = self.get_object()

        if not is_project_admin(request.user, project):
            raise PermissionDenied('Только ADMIN может добавлять участников')

        user_id = request.data.get('user_id')

        try:
            user = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            raise ValidationError({'user_id': 'Пользователь не найден'})

        Membership.objects.get_or_create(
            user=user,
            project=project,
            defaults={'role': Role.MEMBER}
        )

        return Response(
            {'message': 'Участник добавлен'},
            status=status.HTTP_201_CREATED
        )


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    pagination_class = TaskPagination
    permission_classes = [IsAuthenticated, TaskAccessPermission]

    filter_backends = [OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']


    def perform_create(self, serializer):
        with transaction.atomic():
            task = serializer.save()

            invalidate_project_stats(task.project_id)

            if task.assigned_to:
                delivery = NotificationDelivery.objects.create(
                    event_id=str(uuid.uuid4()),
                    task=task,
                    assignee=task.assigned_to
                )

                transaction.on_commit(
                    lambda task_id=task.id,
                    assignee_id=task.assigned_to_id,
                    event_id=delivery.event_id:
                    send_assignment_notification.delay(
                        task_id,
                        assignee_id,
                        event_id
                    )
                )

    def perform_update(self, serializer):
        old_project_id = serializer.instance.project_id
        old_assignee_id = serializer.instance.assigned_to_id

        with transaction.atomic():
            task = serializer.save()

            invalidate_project_stats(old_project_id)

            if task.project_id != old_project_id:
                invalidate_project_stats(task.project_id)

            if (
                task.assigned_to_id is not None
                and task.assigned_to_id != old_assignee_id
            ):
                delivery = NotificationDelivery.objects.create(
                    event_id=str(uuid.uuid4()),
                    task=task,
                    assignee=task.assigned_to
                )

                transaction.on_commit(
                    lambda task_id=task.id,
                    assignee_id=task.assigned_to_id,
                    event_id=delivery.event_id:
                    send_assignment_notification.delay(
                        task_id,
                        assignee_id,
                        event_id
                    )
                )

    def perform_destroy(self, instance):
        project_id = instance.project_id

        instance.delete()

        invalidate_project_stats(project_id)


    def get_queryset(self):
        queryset = Task.objects.filter(
            Q(project__owner=self.request.user) |
            Q(project__members__user=self.request.user)
        ).distinct()

        allowed_params = {
            'status',
            'project',
            'assigned_to',
            'page',
            'page_size',
            'ordering',
            'format'
        }

        unknown_params = (
            set(self.request.query_params.keys()) - allowed_params
        )

        if unknown_params:
            raise ValidationError({
                'message': 'Неизвестные параметры',
                'params': list(unknown_params)
            })

        status_filter = self.request.query_params.get('status')
        project_filter = self.request.query_params.get('project')
        assigned_filter = self.request.query_params.get('assigned_to')

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if project_filter:
            queryset = queryset.filter(project_id=project_filter)

        if assigned_filter:
            queryset = queryset.filter(assigned_to_id=assigned_filter)

        return queryset

class TaskAttachmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_task(self, task_id, user):
        task = get_object_or_404(Task, id=task_id)

        if not is_project_member(user, task.project):
            raise PermissionDenied('Нет доступа к этой задаче')

        return task

    def get(self, request, task_id):
        task = self.get_task(task_id, request.user)

        attachments = task.attachments.all()
        serializer = TaskAttachmentSerializer(
            attachments,
            many=True
        )

        return Response(serializer.data)

    def post(self, request, task_id):
        task = self.get_task(task_id, request.user)

        serializer = TaskAttachmentSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save(task=task)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


class TaskAttachmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_attachment(self, task_id, attachment_id, user):
        task = get_object_or_404(Task, id=task_id)

        if not is_project_member(user, task.project):
            raise PermissionDenied('Нет доступа к этой задаче')

        return get_object_or_404(
            TaskAttachment,
            id=attachment_id,
            task=task
        )

    def get(self, request, task_id, attachment_id):
        attachment = self.get_attachment(
            task_id,
            attachment_id,
            request.user
        )

        return FileResponse(
            attachment.file.open('rb'),
            as_attachment=True,
            filename=attachment.original_name
        )

    def delete(self, request, task_id, attachment_id):
        attachment = self.get_attachment(
            task_id,
            attachment_id,
            request.user
        )

        attachment.file.delete(save=False)
        attachment.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class TaskWebhookView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        if len(request.body) > 64 * 1024:
            return Response(
                {'error': 'Слишком большой запрос'},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            )

        signature = request.headers.get('X-Webhook-Signature', '')

        if not verify_webhook_signature(request.body, signature):
            return Response(
                {'error': 'Неверная подпись'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            data = json.loads(request.body)

            event_id = data['event_id']
            task_id = data['task_id']
            new_status = data['status']
            timestamp = int(data['timestamp'])

            if not event_id or len(event_id) > 100:
                raise ValueError

        except (ValueError, KeyError, TypeError):
            return Response(
                {'error': 'Неверный формат данных'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if abs(time.time() - timestamp) > 300:
            return Response(
                {'error': 'Время события истекло'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_status not in Task.Status.values:
            return Response(
                {'error': 'Недопустимый статус'},
                status=status.HTTP_400_BAD_REQUEST
            )

        allowed_transitions = {
            Task.Status.TODO: [Task.Status.PROGRESS],
            Task.Status.PROGRESS: [Task.Status.DONE],
            Task.Status.DONE: []
        }

        try:
            with transaction.atomic():
                task = Task.objects.select_for_update().get(id=task_id)

                if new_status not in allowed_transitions[task.status]:
                    return Response(
                        {'error': 'Недопустимый переход статуса'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                WebhookEvent.objects.create(
                    event_id=event_id,
                    task=task,
                    status=new_status
                )

                task.status = new_status
                task.save(update_fields=['status'])

                transaction.on_commit(
                    lambda: invalidate_project_stats(task.project_id)
                )

        except IntegrityError:
            return Response(
                {'message': 'Событие уже обработано'},
                status=status.HTTP_200_OK
            )

        except Task.DoesNotExist:
            return Response(
                {'error': 'Задача не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({'message': 'Событие обработано'})
