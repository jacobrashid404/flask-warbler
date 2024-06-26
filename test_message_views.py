"""Message View tests."""

import os
from unittest import TestCase

from app import app, CURR_USER_KEY
from models import db, dbx, Message, User, Like

# To run the tests, you must provide a "test database", since these tests
# delete & recreate the tables & data. In your shell:
#
# Do this only once:
#   $ createdb warbler_test
#
# To run the tests using that test data:
#   $ FLASK_DEBUG=False DATABASE_URL=postgresql:///warbler_test python3 -m unittest

if not app.config['SQLALCHEMY_DATABASE_URI'].endswith("_test"):
    raise Exception(
        "\n\nMust set DATABASE_URL env var to db ending with _test")

# NOW WE KNOW WE'RE IN THE RIGHT DATABASE, SO WE CAN CONTINUE
os.environ['FLASK_DEBUG'] = '0'

# Don't have WTForms use CSRF at all, since it's a pain to test
app.config['WTF_CSRF_ENABLED'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False

app.app_context().push()
db.drop_all()
db.create_all()


class MessageBaseViewTestCase(TestCase):
    def setUp(self):
        dbx(db.delete(User))
        db.session.commit()

        u1 = User.signup("u1", "u1@email.com",
                         "password", None)
        db.session.flush()

        u2 = User.signup("u2", "u2@email.com",
                         "password", None)
        db.session.flush()

        m1 = Message(text="m1-text", user_id=u1.id)
        m2 = Message(text="m2-text", user_id=u2.id)

        db.session.add_all([m1, m2])
        db.session.commit()

        self.u1_id = u1.id
        self.m1_id = m1.id

        self.u2_id = u2.id
        self.m2_id = m2.id

        like = Like(user_id=u2.id, message_id=m1.id)
        db.session.add(like)
        db.session.commit()


class MessageAddViewTestCase(MessageBaseViewTestCase):
    def test_add_message(self):
        # Since we need to change the session to mimic logging in,
        # we need to use the changing-session trick:
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.u1_id

            # Now, that session setting is saved, so we can have
            # the rest of ours test
            resp = c.post("/messages/new", data={"text": "Hello"})

            self.assertEqual(resp.status_code, 302)

            q = db.select(Message).filter_by(text="Hello")
            message = dbx(q).scalar_one_or_none()
            self.assertIsNotNone(message)

    def test_add_message_logged_out(self):
        with app.test_client() as c:

            q = db.select(Message)
            messages_before = dbx(q).all()
            self.assertEqual(len(messages_before), 2)

            resp = c.post("/messages/new",
                          data={"text": "Hello"}, follow_redirects=True)
            html = resp.get_data(as_text=True)

            self.assertEqual(resp.status_code, 200)
            self.assertIn('Access unauthorized', html)

            # NOTE: THIS WILL BREAK WITH FOLLOW REDIRECTS
            # self.assertEqual(resp.location, "/") WHY DOESN'T THIS WORK??? TODO:

            q = db.select(Message)
            messages_after = dbx(q).all()
            self.assertEqual(len(messages_after), 2)


class MessageShowViewTestCase(MessageBaseViewTestCase):
    def test_show_message(self):
        # mimic logging in
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.u1_id

            resp = c.get(f"/messages/{self.m1_id}")
            html = resp.get_data(as_text=True)

            self.assertEqual(resp.status_code, 200)
            # TODO: check that message text is there
            self.assertIn("<!-- comment for testing message show -->", html)

    def test_show_message_logged_out(self):
        # mimic logging in
        with app.test_client() as c:

            resp = c.get(f"/messages/{self.m1_id}", follow_redirects=True)
            html = resp.get_data(as_text=True)

            self.assertEqual(resp.status_code, 200)
            # TODO: make sure message text is not there
            self.assertIn('<!-- Comment for logged out test -->', html)


class MessageDeleteViewTestCase(MessageBaseViewTestCase):
    def test_delete_message(self):
        # mimic logging in
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.u1_id

            q_msg = db.select(Message)
            messages = dbx(q_msg).all()
            self.assertEqual(len(messages), 2)

            # TODO: follow redirect, check for 200 instead of 302
            resp = c.post(f"/messages/{self.m1_id}/delete")

            self.assertEqual(resp.status_code, 302)

            # TODO: try to get deleted message, check that the query gets 'None'
            q_msg_after_del = db.select(Message)
            messages_after_del = dbx(q_msg_after_del).all()
            self.assertEqual(len(messages_after_del), 1)

    def test_delete_message_logged_out(self):
        # mimic logging in
        with app.test_client() as c:

            q_msg = db.select(Message)
            messages = dbx(q_msg).all()
            self.assertEqual(len(messages), 2)

            resp = c.post(f"/messages/{self.m1_id}/delete")

            self.assertEqual(resp.status_code, 302)
            self.assertEqual(resp.location, "/")

            # TODO: also check that the message still exists in database
            q_msg_after_del = db.select(Message)
            messages_after_del = dbx(q_msg_after_del).all()
            self.assertEqual(len(messages_after_del), 2)

    def test_delete_other_user_message(self):
        # mimic logging in
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.u2_id

            q_msg = db.select(Message)
            messages = dbx(q_msg).all()
            self.assertEqual(len(messages), 2)

            # TODO: follow redirects, check for 200 status
            resp = c.post(f"/messages/{self.m1_id}/delete")

            self.assertEqual(resp.status_code, 302)
            self.assertEqual(resp.location, "/")

            # TODO: also check that the message still exists in database
            q_msg_after_del = db.select(Message)
            messages_after_del = dbx(q_msg_after_del).all()
            self.assertEqual(len(messages_after_del), 2)


class MessageAddLikeViewTestCase(MessageBaseViewTestCase):
    def test_liking_message(self):
        # mimic logging in
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.u1_id

            q_like = db.select(Like)
            likes = dbx(q_like).all()

            self.assertEqual(len(likes), 1)

            # TODO: check for star icon toggle at origin of request
            resp = c.post(
                f"/messages/{self.m2_id}/like",
                data={"url": "/"}
            )

            self.assertEqual(resp.status_code, 302)

            q_likes_after_add_like = db.select(Like)
            likes_after_add_like = dbx(q_likes_after_add_like).all()

            self.assertEqual(len(likes_after_add_like), 2)

    def test_liking_own_message(self):
        # mimic logging in
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.u1_id

            q_like = db.select(Like)
            likes = dbx(q_like).all()

            self.assertEqual(len(likes), 1)

            # TODO: follow redirects, check 200 status
            resp = c.post(
                f"/messages/{self.m1_id}/like",
                data={"url": "/"}
            )

            self.assertEqual(resp.status_code, 302)

            q_likes_after_add_like = db.select(Like)
            likes_after_add_like = dbx(q_likes_after_add_like).all()
            self.assertEqual(len(likes_after_add_like), 1)

    def test_liking_message_logged_out(self):
        # mimic logging in
        with app.test_client() as c:

            q_like = db.select(Like)
            likes = dbx(q_like).all()

            self.assertEqual(len(likes), 1)

            # TODO: follow redirects, check 200 status, check flash unauthorized
            resp = c.post(f"/messages/{self.m1_id}/like",
                          data={
                              "url": "/"
                          }
                          )

            self.assertEqual(resp.status_code, 302)

            q_likes_after_add_like = db.select(Like)
            likes_after_add_like = dbx(q_likes_after_add_like).all()
            self.assertEqual(len(likes_after_add_like), 1)


class MessageRemoveLikeViewTestCase(MessageBaseViewTestCase):
    def test_remove_like(self):
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.u2_id

            q_like = db.select(Like)
            likes = dbx(q_like).all()

            self.assertEqual(len(likes), 1)

            # TODO: follow redirects, check status 200
            resp = c.post(
                f"/messages/{self.m1_id}/unlike",
                data={"url": "/"}
            )

            self.assertEqual(resp.status_code, 302)

            q_likes_after_add_like = db.select(Like)
            likes_after_add_like = dbx(q_likes_after_add_like).all()
            self.assertEqual(len(likes_after_add_like), 0)

    def test_remove_like_logged_out(self):
        with app.test_client() as c:

            q_like = db.select(Like)
            likes = dbx(q_like).all()

            self.assertEqual(len(likes), 1)

            # TODO: follow redirects, check 200 status
            resp = c.post(
                f"/messages/{self.m1_id}/unlike",
                data={"url": "/"}
            )

            self.assertEqual(resp.status_code, 302)

            q_likes_after_add_like = db.select(Like)
            likes_after_add_like = dbx(q_likes_after_add_like).all()
            self.assertEqual(len(likes_after_add_like), 1)
