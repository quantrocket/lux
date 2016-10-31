from sqlalchemy.exc import DataError
from sqlalchemy.orm.exc import NoResultFound


class AuthEventsMixin:

    class User:

        @staticmethod
        def insert(app, session, user):
            """
            Called when a new user is being added to the database.

            Implementation checks if the user's email domain matches an
            existing one, and if so sets their organisation to that of the
            domain, and adds the user to the users group.

            :param session:     SQLAlchemy session
            :param user:        User model instance
            """
            odm = app.odm()
            try:
                users = session.query(odm.group).filter_by(name='users').one()
            except (DataError, NoResultFound):
                pass
            else:
                user.groups.append(users)
            # if user.email:
            #    start, at, domain = user.email.rpartition('@')
            #    if at:
            #        res = session.query(odm.domain).filter(
            #            odm.domain.id == domain).first()
            #        if res:
            #            user.organisation_id = res.organisation_id
            #            user_group = session.query(odm.group).filter(
            #                odm.group.name == 'users').first()
            #            if user_group and len(user.groups) == 0:
            #                user.groups.append(user_group)

    class _Organisation:

        @staticmethod
        def insert(app, session, organisation):
            """
            Called when a new organisation is being added to the database.

            Implementation creates a group and permission for administrators
            of the organisation. It also makes the creator of the organisation
            an administrator.

            :param session:         SQLAlchemy session
            :param organisation:    User model instance
            """
            odm = app.odm()

            permission_name = 'org-admin-%s' % organisation.username
            description = ('Admin permissions for %s organisation' %
                           organisation.username)
            resource = 'organisation:%s' % organisation.username
            permission_policy = {
                'resource': resource,
                'action': ['read', 'create', 'update', 'delete']
            }

            group = session.query(odm.group).filter(
                odm.group.name == permission_name).first()
            permission = session.query(odm.permission).filter(
                odm.permission.name == permission_name).first()

            if not group and not permission:
                permission = odm.permission(name=permission_name,
                                            description=description,
                                            policy=permission_policy)

                group = odm.group(name=permission_name)
                group.permissions.append(permission)
                creator = organisation.creator
                if creator:
                    creator.groups.append(group)
                    session.add(creator)
                session.add(group)

        @staticmethod
        def delete(app, session, organisation):
            """
            Called when an organisation is being deleted.

            :param session:         SQLAlchemy session
            :param organisation:    organisation instance
            """
            odm = app.odm()

            permission_name = '{}-admin'.format(organisation.username)
            group = session.query(odm.group).filter(
                odm.group.name == permission_name).first()
            permission = session.query(odm.permission).filter(
                odm.permission.name == permission_name).first()
            if group:
                session.delete(group)
            if permission:
                session.delete(permission)

    def on_before_commit(self, app, session):  # pragma nocover
        """
        Called before SQLAlchemy commit.

        :param app:         Lux app object
        :param session:     SQLAlchemy session
        :param changes:     dict of model changes
        """
        # We make a shallow copy of the generator as it will be
        # modified by the other callbacks
        for instance, event in tuple(session.changes()):
            actions = getattr(self, instance.__class__.__name__, None)
            if actions:
                action = getattr(actions, event, None)
                if action:
                    action(app, session, instance)