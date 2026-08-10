"""LLM-originated experiment wiring tests.

The scheduler's llm_analyze job proposes experiments with
origin=ExperimentOrigin.LLM; these tests prove that origin exists, that the
engine accepts such proposals, and that they are retained by the engine.
"""

from cudaquant.experiments.engine import ExperimentEngine, ExperimentOrigin


class TestLLMOrigin:
    """ExperimentOrigin.LLM exists and round-trips as a string."""

    def test_llm_origin_exists(self):
        """ExperimentOrigin.LLM exists with value 'llm'."""
        assert ExperimentOrigin.LLM is not None
        assert ExperimentOrigin.LLM.value == "llm"

    def test_llm_experiment_can_be_proposed(self):
        """propose() with origin=ExperimentOrigin.LLM returns an llm experiment."""
        engine = ExperimentEngine(db_path=None)
        exp = engine.propose(
            hypothesis="LLM suggests widening the feature window",
            origin=ExperimentOrigin.LLM,
            notes="proposed by llm_analyze scheduler job",
        )
        assert exp.origin == ExperimentOrigin.LLM
        assert exp.hypothesis.startswith("LLM")
        assert engine.get(exp.experiment_id) is exp

    def test_llm_experiment_persists(self):
        """A proposed LLM experiment is retained and listed by the same engine."""
        engine = ExperimentEngine(db_path=None)
        exp = engine.propose(
            hypothesis="LLM drift signal on short horizon",
            origin=ExperimentOrigin.LLM,
        )
        ids = [e.experiment_id for e in engine.list_all()]
        assert exp.experiment_id in ids
        listed = engine.list_all()[ids.index(exp.experiment_id)]
        assert listed.origin == ExperimentOrigin.LLM
