"""Unit tests for Secret class."""

import vedro

from gitlab_queue.config import Secret


class Scenario(vedro.Scenario):
    subject = "create secret and hide value in str representation"

    def given_secret_value(self):
        self.secret_value = "glpat-super-secret-token"

    def when_secret_is_created(self):
        self.secret = Secret(self.secret_value)

    def then_str_should_hide_value(self):
        assert str(self.secret) == "***"

    def and_repr_should_hide_value(self):
        assert "***" in repr(self.secret)
        assert self.secret_value not in repr(self.secret)


class Scenario__get_secret_value(vedro.Scenario):
    subject = "retrieve actual secret value"

    def given_secret(self):
        self.secret_value = "my-api-key-12345"
        self.secret = Secret(self.secret_value)

    def when_getting_secret_value(self):
        self.retrieved = self.secret.get_secret_value()

    def then_it_should_return_original_value(self):
        assert self.retrieved == self.secret_value


class Scenario__secret_blocks_direct_access(vedro.Scenario):
    subject = "secret blocks direct access to _secret_value"

    def given_secret(self):
        self.secret = Secret("hidden-value")

    def when_trying_to_access_secret_value_directly(self):
        try:
            _ = self.secret._secret_value
            self.error = None
        except AttributeError as e:
            self.error = e

    def then_it_should_raise_attribute_error(self):
        assert self.error is not None
        assert "Direct access" in str(self.error) or "not allowed" in str(self.error)


class Scenario__secret_is_immutable(vedro.Scenario):
    subject = "secret is immutable"

    def given_secret(self):
        self.secret = Secret("original-value")

    def when_trying_to_set_attribute(self):
        try:
            self.secret.new_attr = "new-value"
            self.error = None
        except AttributeError as e:
            self.error = e

    def then_it_should_raise_attribute_error(self):
        assert self.error is not None
        assert "immutable" in str(self.error).lower()


class Scenario__secret_cannot_be_deleted(vedro.Scenario):
    subject = "secret attributes cannot be deleted"

    def given_secret(self):
        self.secret = Secret("test-value")

    def when_trying_to_delete_attribute(self):
        try:
            del self.secret.get_secret_value
            self.error = None
        except AttributeError as e:
            self.error = e

    def then_it_should_raise_attribute_error(self):
        assert self.error is not None


class Scenario__secret_equality_comparison(vedro.Scenario):
    subject = "secret equality uses constant-time comparison"

    def given_two_equal_secrets(self):
        self.secret1 = Secret("same-value")
        self.secret2 = Secret("same-value")

    def when_comparing_secrets(self):
        self.result = self.secret1 == self.secret2

    def then_they_should_be_equal(self):
        assert self.result is True


class Scenario__secret_inequality(vedro.Scenario):
    subject = "different secrets are not equal"

    def given_two_different_secrets(self):
        self.secret1 = Secret("value-one")
        self.secret2 = Secret("value-two")

    def when_comparing_secrets(self):
        self.result = self.secret1 == self.secret2

    def then_they_should_not_be_equal(self):
        assert self.result is False


class Scenario__secret_not_equal_to_non_secret(vedro.Scenario):
    subject = "secret not equal to non-secret type"

    def given_secret_and_string(self):
        self.secret = Secret("my-value")
        self.string = "my-value"

    def when_comparing_secret_to_string(self):
        self.result = self.secret == self.string

    def then_it_should_return_not_implemented(self):
        assert self.result is NotImplemented


class Scenario__secret_length(vedro.Scenario):
    subject = "secret length returns correct value"

    def given_secret_with_known_length(self):
        self.value = "12345678"
        self.secret = Secret(self.value)

    def when_getting_length(self):
        self.length = len(self.secret)

    def then_it_should_return_correct_length(self):
        assert self.length == 8


class Scenario__secret_is_hashable(vedro.Scenario):
    subject = "secret is hashable"

    def given_secret(self):
        self.secret = Secret("hashable-value")

    def when_getting_hash(self):
        self.hash_value = hash(self.secret)

    def then_it_should_return_hash(self):
        assert isinstance(self.hash_value, int)


class Scenario__secrets_with_same_value_have_same_hash(vedro.Scenario):
    subject = "secrets with same value have same hash"

    def given_two_secrets_with_same_value(self):
        self.secret1 = Secret("identical")
        self.secret2 = Secret("identical")

    def when_getting_hashes(self):
        self.hash1 = hash(self.secret1)
        self.hash2 = hash(self.secret2)

    def then_hashes_should_be_equal(self):
        assert self.hash1 == self.hash2


class Scenario__secret_not_leaked_in_format_string(vedro.Scenario):
    subject = "secret not leaked in format string"

    def given_secret(self):
        self.secret_value = "super-secret-api-key"
        self.secret = Secret(self.secret_value)

    def when_using_in_format_string(self):
        self.formatted = f"Token: {self.secret}"

    def then_value_should_be_hidden(self):
        assert self.secret_value not in self.formatted
        assert "***" in self.formatted
