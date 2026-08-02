"""The chain-of-thought wiring: what each step quotes, and that the order allows it."""
from __future__ import annotations

import pytest

from pybreeze.pybreeze_ui.extend_ai_gui.ai_gui_global_variable import (
    COT_TEMPLATE_FILES, COT_TEMPLATE_RELATION
)
from pybreeze.pybreeze_ui.extend_ai_gui.code_review.cot_chain import (
    CODE_DIFF, STEP_ARGUMENTS, STEP_RESULT_KEY, build_prompt
)

CODE = "def apply_discount(total, percent):\n    return total - total * percent / 100\n"


def run_chain(steps=None, answers=None) -> dict[str, str]:
    """Walk the chain, recording the prompt each step would send.

    :param steps: the steps to run, defaulting to the whole chain
    :param answers: answer text per step, defaulting to a recognisable marker
    :return: step name -> the prompt built for it
    """
    steps = COT_TEMPLATE_FILES if steps is None else steps
    answers = answers or {}
    results = {CODE_DIFF: CODE}
    prompts: dict[str, str] = {}
    for step in steps:
        prompts[step] = build_prompt(step, results)
        results[STEP_RESULT_KEY[step]] = answers.get(step, f"<<answer from {step}>>")
    return prompts


class TestTheChainIsCompletelyWired:
    def test_every_step_has_a_template(self):
        assert set(COT_TEMPLATE_FILES) <= set(COT_TEMPLATE_RELATION)

    def test_every_step_has_arguments_and_a_result_key(self):
        for step in COT_TEMPLATE_FILES:
            assert step in STEP_ARGUMENTS, step
            assert step in STEP_RESULT_KEY, step

    def test_no_template_is_left_out_of_the_chain(self):
        # A template nobody runs is dead weight: this is the guard that caught
        # judge, judge_single_review and step_by_step_analysis sitting unused.
        assert set(COT_TEMPLATE_RELATION) == set(COT_TEMPLATE_FILES)

    def test_result_keys_are_distinct(self):
        keys = [STEP_RESULT_KEY[step] for step in COT_TEMPLATE_FILES]
        assert len(keys) == len(set(keys))

    def test_arguments_match_the_template_placeholders(self):
        for step in COT_TEMPLATE_FILES:
            # format() raises KeyError for a placeholder the wiring forgot, and
            # the wiring naming one the template lacks is caught by the diff below.
            filled = {name: "x" for name in STEP_ARGUMENTS[step]}
            assert COT_TEMPLATE_RELATION[step].format(**filled)


class TestTheOrderIsADependencyOrder:
    def test_no_step_quotes_a_result_that_has_not_been_produced_yet(self):
        produced = {CODE_DIFF}
        for step in COT_TEMPLATE_FILES:
            needed = set(STEP_ARGUMENTS[step].values())
            assert needed <= produced, (
                f"{step} quotes {needed - produced}, which no earlier step produces")
            produced.add(STEP_RESULT_KEY[step])

    def test_every_step_builds_a_prompt_when_run_in_order(self):
        assert all(prompt for prompt in run_chain().values())


class TestWhatEachStepQuotes:
    def test_the_code_reaches_the_first_review(self):
        assert CODE in run_chain()["first_code_review.md"]

    def test_the_single_review_judge_quotes_the_review_it_scores(self):
        prompts = run_chain()
        assert "<<answer from first_code_review.md>>" in prompts["judge_single_review.md"]

    def test_the_single_review_judge_also_sees_the_original_code(self):
        assert CODE in run_chain()["judge_single_review.md"]

    def test_the_step_by_step_analysis_walks_the_linter_and_the_smells(self):
        prompt = run_chain()["step_by_step_analysis.md"]
        assert "<<answer from linter.md>>" in prompt
        assert "<<answer from code_smell_detector.md>>" in prompt

    def test_the_total_summary_gathers_the_four_earlier_answers(self):
        prompt = run_chain()["total_summary.md"]
        for earlier in ("first_summary_prompt.md", "first_code_review.md",
                        "linter.md", "code_smell_detector.md"):
            assert f"<<answer from {earlier}>>" in prompt, earlier

    def test_the_final_judge_scores_the_summary_with_the_findings_in_hand(self):
        prompt = run_chain()["judge.md"]
        assert "<<answer from total_summary.md>>" in prompt
        assert "<<answer from linter.md>>" in prompt
        assert "<<answer from code_smell_detector.md>>" in prompt

    def test_every_prompt_carries_the_global_rules(self):
        for step, prompt in run_chain().items():
            assert "conduct a code review according to the following global rules" in prompt, step


class TestRunningPartOfTheChain:
    def test_a_step_whose_input_never_ran_quotes_nothing_rather_than_none(self):
        # Selecting only the judge leaves it with no review to score. It must see
        # an empty section, not the literal word "None" read as a review.
        prompt = build_prompt("judge.md", {CODE_DIFF: CODE})
        assert prompt is not None
        assert "None" not in prompt.split("## Review Comment:")[1].split("##")[0]

    def test_an_unknown_step_is_skipped(self):
        assert build_prompt("nonsense.md", {CODE_DIFF: CODE}) is None

    def test_a_step_can_run_on_its_own(self):
        assert CODE in build_prompt("linter.md", {CODE_DIFF: CODE})


@pytest.mark.parametrize("step", COT_TEMPLATE_FILES)
def test_a_step_never_leaves_an_unfilled_placeholder(step):
    prompt = run_chain()[step]
    for placeholder in STEP_ARGUMENTS[step]:
        assert "{" + placeholder + "}" not in prompt
