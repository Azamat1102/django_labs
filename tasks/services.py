
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction

from accounts.models import Membership, Role
from tasks.models import Project, Task


def create_project(owner, name, description=''):
    project = Project.objects.create(
        owner=owner,
        name=name,
        description=description
    )

    Membership.objects.create(
        user=owner,
        project=project,
        role=Role.ADMIN
    )

    return project


def create_task(project, title, assigned_to=None, description=''):
    if assigned_to is not None:
        is_member = Membership.objects.filter(
            project=project,
            user=assigned_to
        ).exists()

        if not is_member:
            raise ValueError('Пользователь не состоит в этом проекте')

    task = Task.objects.create(
        project=project,
        title=title,
        assigned_to=assigned_to,
        description=description
    )

    return task


def transfer_project_ownership(project_id, new_owner_id):
    with transaction.atomic():
        project = Project.objects.select_for_update().get(
            id=project_id
        )

        new_owner = User.objects.get(id=new_owner_id)
        old_owner = project.owner

        if old_owner.id == new_owner.id:
            return project

        memberships = Membership.objects.filter(
            project=project
        ).order_by('id')

        list(memberships.select_for_update())

        old_membership = Membership.objects.filter(
            project=project,
            user=old_owner
        ).first()

        new_membership = Membership.objects.filter(
            project=project,
            user=new_owner
        ).first()

        if old_membership:
            old_membership.role = Role.MEMBER
            old_membership.save(update_fields=['role'])

        if new_membership:
            new_membership.role = Role.ADMIN
            new_membership.save(update_fields=['role'])
        else:
            Membership.objects.create(
                project=project,
                user=new_owner,
                role=Role.ADMIN
            )

        project.owner = new_owner
        project.save(update_fields=['owner'])

        return project


def stats_key(project_id):
    return f'project-stats:v1:{project_id}'


def invalidate_project_stats(project_id):
    transaction.on_commit(
        lambda: cache.delete(stats_key(project_id))
    )
