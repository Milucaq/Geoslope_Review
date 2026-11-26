"""User-owned review decisions; authorization is checked inside the service."""

from datetime import datetime, timezone

from gsreview.application.workflow import analysis_context, context_id, data_version
from gsreview.domain.rules import ReviewInput, ValidationError
from gsreview.infrastructure.scenario_reviews import ScenarioReviews


class ScenarioReviewService:
    def __init__(self, auth, path):
        self.auth, self.repository = auth, ScenarioReviews(path)

    def listing(self, token, scenario_id, frame):
        actor = self.auth.authorize(token, "review")
        if scenario_id not in {"external", "john_henry"}:
            raise ValidationError("Las revisiones históricas tienen su propia bandeja.")
        return self.repository.records(actor["id"], scenario_id, data_version(frame))

    def save(self, token, scenario_id, frame, prism, cutoff, model_version, analysis_id, decision):
        actor = self.auth.authorize(token, "review")
        decision.validate_choices()
        context = analysis_context(frame, scenario_id, prism, cutoff, model_version, analysis_id)
        # Use the original auth transaction guard through the independent commit.
        # Lock order is auth -> scenario store, never reversed in this service.
        with self.auth.store.tx() as connection:
            self.auth.guard(connection, token, "review")
            saved = self.repository.append(actor["id"], context_id(context), decision.expected_version,
                context | decision.model_dump(exclude={"expected_version"}) |
                {"actor_id": actor["id"], "reviewer": actor["display_name"],
                 "created_at": datetime.fromtimestamp(self.auth.clock(), timezone.utc).isoformat()})
        return saved


__all__ = ["ScenarioReviewService", "ReviewInput"]
