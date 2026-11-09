from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from tasks.models import Project, Task, TaskAttachment
from tasks.permissions import is_project_member


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'owner', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'id',
            'project',
            'assigned_to',
            'title',
            'description',
            'status',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_title(self, value):
        value = value.strip()

        if len(value) < 3:
            raise serializers.ValidationError(
                'Название задачи должно содержать минимум 3 символа'
            )

        return value

    def validate(self, attrs):
        request = self.context.get('request')

        project = attrs.get(
            'project',
            self.instance.project if self.instance else None
        )

        assigned_to = attrs.get(
            'assigned_to',
            self.instance.assigned_to if self.instance else None
        )

        if project and not is_project_member(request.user, project):
            raise serializers.ValidationError({
                'project': 'У вас нет доступа к этому проекту'
            })

        if assigned_to and project and not is_project_member(assigned_to, project):
            raise serializers.ValidationError({
                'assigned_to': 'Пользователь не состоит в проекте'
            })

        return attrs


class TaskAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskAttachment
        fields = [
            'id',
            'file',
            'original_name',
            'size',
            'uploaded_at'
        ]
        read_only_fields = [
            'id',
            'original_name',
            'size',
            'uploaded_at'
        ]

    def validate_file(self, file):
        if file.size > 5 * 1024 * 1024:
            raise ValidationError('Максимальный размер файла — 5 МБ')

        extension = file.name.lower().rsplit('.', 1)[-1]

        if extension not in ['pdf', 'png']:
            raise ValidationError('Разрешены только PDF и PNG')

        file.seek(0)
        signature = file.read(8)
        file.seek(0)

        if extension == 'pdf' and not signature.startswith(b'%PDF-'):
            raise ValidationError('Файл не является настоящим PDF')

        if extension == 'png' and signature != b'\x89PNG\r\n\x1a\n':
            raise ValidationError('Файл не является настоящим PNG')

        return file

    def create(self, validated_data):
        file = validated_data['file']

        validated_data['uploaded_by'] = self.context['request'].user
        validated_data['original_name'] = file.name
        validated_data['size'] = file.size

        return super().create(validated_data)
