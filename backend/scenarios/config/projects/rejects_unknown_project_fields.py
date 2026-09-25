"""Project JSON rejects misspelled or unsupported fields."""

import vedro
from vedro import catched

from gitlab_queue.config import _parse_projects_json


class Scenario(vedro.Scenario):
    subject = "reject an unknown project setting"

    def given_project_json_with_an_unknown_field(self):
        self.raw = '[{"project_id": 17, "token": "token", "queue_lable": "queue"}]'

    def when_project_json_is_parsed(self):
        with catched(ValueError) as self.exception:
            _parse_projects_json(self.raw)

    def then_error_names_the_unknown_field(self):
        assert "queue_lable" in str(self.exception.value)
