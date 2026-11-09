
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from django.urls import reverse

from tasks.models import Project, Task


class APITest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='azamat',
            password='12345'
        )

        self.project = Project.objects.create(
            name='Test project',
            owner=self.user
        )

        self.task = Task.objects.create(
            project=self.project,
            assigned_to=self.user,
            title='First task',
            status=Task.Status.TODO
        )

        Task.objects.create(
            project=self.project,
            assigned_to=self.user,
            title='Second task',
            status=Task.Status.DONE
        )

    def test_projects_list(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse('project-list'))

        self.assertEqual(response.status_code, 200)

    def test_create_project(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('project-list'),
            {'name': 'New project'}
        )

        self.assertEqual(response.status_code, 201)

    def test_create_task(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('task-list'),
            {
                'project': self.project.id,
                'assigned_to': self.user.id,
                'title': 'New task',
                'status': 'TODO'
            }
        )

        self.assertEqual(response.status_code, 201)

    def test_invalid_task_title(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse('task-list'),
            {
                'project': self.project.id,
                'title': ' a ',
                'status': 'TODO'
            }
        )

        self.assertEqual(response.status_code, 400)

    def test_task_filter(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse('task-list'),
            {'status': 'TODO'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_project_stats(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse('project-stats', kwargs={'pk': self.project.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 2)

    def test_update_task(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            reverse('task-detail', kwargs={'pk': self.task.id}),
            {'title': 'Updated task'}
        )

        self.assertEqual(response.status_code, 200)

    def test_delete_task(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse('task-detail', kwargs={'pk': self.task.id})
        )

        self.assertEqual(response.status_code, 204)

    def test_filter_by_project(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse('task-list'),
            {'project': self.project.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)

    def test_filter_by_assigned_to(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse('task-list'),
            {'assigned_to': self.user.id}
        )

        self.assertEqual(response.status_code, 200)
