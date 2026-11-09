from tasks.models import Project, Task
from django.db.models import Count, Q


def get_projects_report():
    projects = Project.objects.all()
    result = []

    for project in projects:
        tasks = []

        for task in project.tasks.all():
            tasks.append({
                'task': task,
                'executor': task.assigned_to
            })

        result.append({
            'project': project,
            'tasks': tasks
        })

    return result


def get_projects_report_optimized():
    projects = Project.objects.prefetch_related(
        'tasks__assigned_to'
    )

    result = []

    for project in projects:
        tasks = []

        for task in project.tasks.all():
            tasks.append({
                'task': task,
                'executor': task.assigned_to
            })

        result.append({
            'project': project,
            'tasks': tasks
        })

    return result


def get_project_statistics():
    projects = Project.objects.annotate(
        total=Count('tasks'),
        todo=Count('tasks', filter=Q(tasks__status=Task.Status.TODO)),
        progress=Count('tasks', filter=Q(tasks__status=Task.Status.PROGRESS)),
        done=Count('tasks', filter=Q(tasks__status=Task.Status.DONE))
    )

    result = []

    for project in projects:
        completion_rate = 0

        if project.total > 0:
            completion_rate = round(project.done / project.total * 100, 2)

        result.append({
            'project': project.name,
            'total': project.total,
            'todo': project.todo,
            'progress': project.progress,
            'done': project.done,
            'completion_rate': completion_rate
        })

    return result