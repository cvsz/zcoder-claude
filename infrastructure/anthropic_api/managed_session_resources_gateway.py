"""Managed Agents session-resource transport adapter."""

from typing import Iterable

from domain.agents.session_resources import GitHubRepositoryResource

MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"


class ManagedSessionResourcesGateway:
    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)

    def create_session_with_github_resources(
        self,
        agent_id: str,
        environment_id: str,
        repositories: Iterable[GitHubRepositoryResource],
        *,
        title: str = "",
        initial_events=None,
    ) -> dict:
        resources = list(repositories)
        payload_resources = [resource.to_api_dict() for resource in resources]
        kwargs = {
            "agent": agent_id,
            "environment_id": environment_id,
            "title": title,
            "resources": payload_resources,
            "betas": [MANAGED_AGENTS_BETA],
        }
        if initial_events:
            if len(initial_events) > 50:
                raise ValueError("initial_events supports at most 50 events")
            kwargs["initial_events"] = initial_events
        session = self.client.beta.sessions.create(**kwargs)
        return {
            "id": session.id,
            "agent_id": agent_id,
            "environment_id": environment_id,
            "resources": [resource.safe_dict() for resource in resources],
        }

    def list_resources(self, session_id: str):
        return self.client.beta.sessions.resources.list(
            session_id, betas=[MANAGED_AGENTS_BETA]
        )

    def get_resource(self, session_id: str, resource_id: str):
        return self.client.beta.sessions.resources.retrieve(
            resource_id, session_id=session_id, betas=[MANAGED_AGENTS_BETA]
        )

    def rotate_github_token(self, session_id: str, resource_id: str,
                            authorization_token: str):
        if not authorization_token:
            raise ValueError("authorization_token must not be empty")
        return self.client.beta.sessions.resources.update(
            resource_id,
            session_id=session_id,
            authorization_token=authorization_token,
            betas=[MANAGED_AGENTS_BETA],
        )

    def delete_resource(self, session_id: str, resource_id: str):
        return self.client.beta.sessions.resources.delete(
            resource_id, session_id=session_id, betas=[MANAGED_AGENTS_BETA]
        )
