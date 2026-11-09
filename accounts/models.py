
from django.db import models


class Role(models.TextChoices):
    ADMIN = 'ADMIN', 'Администратор'
    MEMBER = 'MEMBER', 'Участник'


class Membership(models.Model):
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='memberships'
    )

    project = models.ForeignKey(
        'tasks.Project',
        on_delete=models.CASCADE,
        related_name='members'
    )

    role = models.CharField(
        max_length=10,
        choices=Role.choices
    )

    class Meta:
        constraints: list = [
            models.UniqueConstraint(
                fields=['user', 'project'],
                name='unique_user_project'
            )
        ]

        indexes = [
            models.Index(fields=['project', 'role']),
        ]
