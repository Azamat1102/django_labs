from django.test import TransactionTestCase
from django.db import connection, close_old_connections
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth.models import User
from tasks.models import Project
from accounts.models import Membership, Role
from tasks.services import transfer_project_ownership


@skipUnless(connection.vendor == 'postgresql', 'Тест только для PostgreSQL')
class ConcurrentOwnershipTest(TransactionTestCase):

    def setUp(self):
        self.user1 = User.objects.create_user(username='owner1')
        self.user2 = User.objects.create_user(username='owner2')
        self.user3 = User.objects.create_user(username='owner3')

        self.project = Project.objects.create(
            name='Concurrent project',
            owner=self.user1
        )

        for user, role in [
            (self.user1, Role.ADMIN),
            (self.user2, Role.MEMBER),
            (self.user3, Role.MEMBER)
        ]:
            Membership.objects.create(
                user=user,
                project=self.project,
                role=role
            )

    def test_concurrent_transfers(self):
        barrier = Barrier(2)

        def transfer(user_id):
            close_old_connections()
            try:
                barrier.wait()
                transfer_project_ownership(
                    self.project.id,
                    user_id
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(transfer, self.user2.id)
            second = executor.submit(transfer, self.user3.id)

            first.result()
            second.result()

        self.project.refresh_from_db()

        self.assertIn(
            self.project.owner_id,
            [self.user2.id, self.user3.id]
        )

        memberships = Membership.objects.filter(
            project=self.project
        )

        admins = memberships.filter(role=Role.ADMIN)

        self.assertEqual(admins.count(), 1)
        self.assertEqual(
            admins.first().user_id,
            self.project.owner_id
        )