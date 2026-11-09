from tasks.models import Project, Task
from django.contrib.auth.models import User
import random


def generate_data():
    users = list(User.objects.all())

    if not users:
        return

    projects = []

    for i in range(100):
        project = Project(
            name=f'Проект {i + 1}',
            description=f'Описание проекта {i + 1}',
            owner=random.choice(users)
        )
        projects.append(project)

    Project.objects.bulk_create(projects)

    projects = list(Project.objects.order_by('-id')[:100])

    tasks = []

    for i in range(1000):
        task = Task(
            project=random.choice(projects),
            assigned_to=random.choice(users),
            title=f'Задача {i + 1}',
            description=f'Описание задачи {i + 1}',
            status=random.choice([
                Task.Status.TODO,
                Task.Status.PROGRESS,
                Task.Status.DONE
            ])
        )
        tasks.append(task)

    Task.objects.bulk_create(tasks)