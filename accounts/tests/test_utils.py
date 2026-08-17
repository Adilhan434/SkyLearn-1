import string

from django.test import SimpleTestCase

from accounts.utils import generate_password


class PasswordGenerationTests(SimpleTestCase):
    def test_generated_password_is_strong_and_random(self):
        first = generate_password()
        second = generate_password()

        self.assertEqual(len(first), 16)
        self.assertNotEqual(first, second)
        self.assertTrue(any(character in string.ascii_lowercase for character in first))
        self.assertTrue(any(character in string.ascii_uppercase for character in first))
        self.assertTrue(any(character in string.digits for character in first))
        self.assertTrue(any(character in "!@#$%^&*" for character in first))
