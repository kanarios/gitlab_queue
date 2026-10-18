import json

from vedro import catched, given, params, scenario, then, when

from gitlab_queue.config import ProjectConfig, Secret, Settings


@scenario()
def project_automation_labels_are_exact_and_allow_existing_triggers():
    with given("a project with ordinary automation names and both existing trigger aliases"):
        settings = Settings(
            jwt_secret="a" * 64,
            projects_json=json.dumps(
                [
                    {
                        "project_id": 123,
                        "token": "test-token",
                        "automation_labels": ["dependencies", "Dependencies", "hotfix", "merge_queue"],
                    }
                ]
            ),
        )

    with when("the public settings resolve the project's immutable policy"):
        projects = settings.projects

    with then("names retain their exact spelling and trigger overlap is accepted"):
        assert projects[0].automation_labels == ("dependencies", "Dependencies", "hotfix", "merge_queue")


@scenario(
    [
        params(None),
        params("dependencies"),
        params(1),
        params({}),
        params([1]),
        params([None]),
        params([""]),
        params([" "]),
        params([" dep"]),
        params(["dep "]),
        params(["dep", "dep"]),
    ]
)
def invalid_automation_config_is_rejected_before_startup(value):
    with given("a project JSON entry with an invalid automation-label policy"):
        settings = Settings(
            jwt_secret="a" * 64,
            projects_json=json.dumps([{"project_id": 123, "token": "test", "automation_labels": value}]),
        )
    with when("startup resolves the public project settings"), catched(ValueError) as error:
        _projects = settings.projects
    with then("the policy is refused before any component or database is created"):
        assert error.type is ValueError
        assert "automation_labels" in str(error.value)


@scenario([params({}), params({"automation_labels": []})])
def missing_and_empty_project_policy_preserve_legacy_default(fields):
    with given("a project without an enabled automation policy"):
        settings = Settings(
            jwt_secret="a" * 64, projects_json=json.dumps([{"project_id": 123, "token": "test", **fields}])
        )
    with when("the public policy is resolved"):
        policy = settings.projects[0]
    with then("automation is disabled without changing existing trigger names"):
        assert policy.automation_labels == ()
        assert (policy.queue_label, policy.hotfix_label) == ("merge_queue", "hotfix")


@scenario([params(["dep"]), params(("dep", "dep")), params((" dep",))])
def direct_project_construction_applies_the_same_validation(value):
    with given("an invalid direct project configuration"):
        token = Secret("test")
    with when("a caller constructs the public immutable policy"), catched(ValueError) as error:
        ProjectConfig(123, token, automation_labels=value)
    with then("bypassing JSON cannot bypass policy validation"):
        assert error.type is ValueError
