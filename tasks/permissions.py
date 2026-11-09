from rest_framework.permissions import BasePermission

from accounts.models import Membership, Role


def is_project_member(user, project):
    return project.owner_id == user.id or Membership.objects.filter(
        project=project,
        user=user
    ).exists()


def is_project_admin(user, project):
    return project.owner_id == user.id or Membership.objects.filter(
        project=project,
        user=user,
        role=Role.ADMIN
    ).exists()


class TaskAccessPermission(BasePermission):

    def has_object_permission(self, request, view, obj):
        if not is_project_member(request.user, obj.project):
            return False

        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True

        if request.method == 'DELETE':
            return is_project_admin(request.user, obj.project)

        if request.method == 'PATCH':
            if is_project_admin(request.user, obj.project):
                return True

            return (
                obj.assigned_to_id == request.user.id
                and set(request.data.keys()) == {'status'}
            )

        return False