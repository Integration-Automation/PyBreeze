AI Tools
========

PyBreeze has five tools for AI-assisted code review and prompt work. Each opens as a
tab from **Tools > AI** or as a dock from **Dock > AI**. The code review of a file or a
pull request by prthinker is in the **Automation** menu instead (see
:doc:`menu_automation`).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Tool
     - What it does
   * - **AI Code Review**
     - Sends code to an endpoint in one request; accept or reject the answer.
   * - **CoT Code Review**
     - Runs the eight-step Chain-of-Thought (CoT) review: one request per step.
   * - **CoT Prompt Editor**
     - Edits the eight CoT prompts.
   * - **Skill Prompt Editor**
     - Edits the two skill prompts (code review, code explanation).
   * - **Skill Send**
     - Sends one skill prompt, with your code in it, and shows the answer.

In AI Code Review, CoT Code Review and Skill Send, **Ctrl+Enter** anywhere in the panel
presses its send button. The request runs in the background, and the send button stays
greyed out until it ends.

.. note::

   The endpoint URL must be a public ``http`` / ``https`` address. It is checked before
   anything is sent, and the connection goes only to the address checked: an endpoint on
   this machine or on a private network, such as a local model server, is refused.
   Redirects are not followed, the answer is capped at 16 MB, and a request that runs
   past five minutes is stopped. Only AI Code Review records the URLs it used, and only as
   fingerprints (see below), since an API URL can carry a token.

AI Code Review
--------------

**Menu:** Tools > AI > AI Code Review Tab / Dock > AI > AI Code Review Dock

Interface Layout
^^^^^^^^^^^^^^^^

- **URL** -- the endpoint URL
- **Method** -- ``GET``, ``POST`` (the default), ``PUT`` or ``DELETE``
- **Code to Send** (left) -- the code to review
- **Response** (right, read-only) -- the answer, or why there is none
- **Send Request** -- sends the request
- **Accept Response** / **Reject Response** -- your verdict on the answer

Usage
^^^^^

1. Enter the endpoint URL and choose the method. ``POST`` and ``PUT`` send the code as
   the form field ``code`` in the body; ``GET`` and ``DELETE`` send the URL alone.
2. Paste the code to review on the left (``POST`` and ``PUT`` need some).
3. Click **Send Request**. The response panel first says whether this URL has been used
   before, then shows the answer when it arrives. An answer that is not a success (an
   HTTP error, or a redirect, which is not followed) is shown as an error with its status.
4. Click **Accept Response** or **Reject Response**. They are enabled once an answer has
   arrived, and take one verdict per answer.

Files
^^^^^

- ``~/.pybreeze/response_stats.txt`` -- the running totals of accepted and rejected
  answers, shared by every AI Code Review panel
- ``~/.pybreeze/urls.txt`` -- the URLs used, as SHA-256 fingerprints: the URL itself is
  never written to disk

CoT Code Review
---------------

**Menu:** Tools > AI > CoT Code Review Tab / Dock > AI > CoT Code Review Dock

Interface Layout
^^^^^^^^^^^^^^^^

- **API URL** -- the endpoint URL
- **Code to Review** -- the code the review is about
- **Response Area** -- **Step** selector (each step whose answer has arrived) beside the
  selected step's answer (read-only)
- **Start Sending** -- runs the review

How a review runs
^^^^^^^^^^^^^^^^^

The eight steps run in this order, because each may quote the answers of the steps
before it:

1. ``first_summary_prompt.md`` -- a first summary of the code
2. ``first_code_review.md`` -- a first review
3. ``judge_single_review.md`` -- a judge of that review
4. ``linter.md`` -- lint findings
5. ``code_smell_detector.md`` -- code smells
6. ``step_by_step_analysis.md`` -- each lint finding and code smell walked through
7. ``total_summary.md`` -- the summary of everything above
8. ``judge.md`` -- a judge of the summary

Each step's prompt, wrapped in the global review rules, is sent as a ``POST`` of the JSON
``{"prompt": "..."}``, and the response body, as text, is that step's answer. It appears
under **Step** as it arrives and is shown at once. A step that fails shows why, and the
steps after it do not quote the failure. **Start Sending** clears the previous run's
answers, and closing the panel stops the review after the request in flight.

The prompts are the CoT Prompt Editor's: an edited prompt is used in place of the
built-in one.

CoT Prompt Editor
-----------------

**Menu:** Tools > AI > CoT Prompt Editor Tab / Dock > AI > CoT Prompt Editor Dock

Interface Layout
^^^^^^^^^^^^^^^^

- **Edit File Content** -- the text of the prompt chosen below
- The folder the prompt files are kept in, ``~/.pybreeze/prompts/``
- The prompt selector (one entry per step, as listed above)
- **Reload** -- reads the file again from disk
- **Save** -- writes the text to the file
- **Create File** -- creates the file from the built-in prompt

How prompts are kept
^^^^^^^^^^^^^^^^^^^^

Every prompt is built in. A file of the same name in ``~/.pybreeze/prompts/`` replaces it
while that file has content, so a review sends what you saved. Until the file exists, the
edit area is empty and says so; **Create File** writes the built-in prompt into it as a
starting point.

A prompt's placeholders, such as ``{code_diff}``, are filled in when the review runs. An
edited prompt that names a placeholder the step cannot fill falls back to the built-in
one for that run.

The files are watched: an edit made outside the editor shows up at once. Whenever
showing another text would lose unsaved edits -- choosing another prompt, **Reload**,
**Create File**, an outside change, or closing the tab, the dock or the IDE -- the editor
asks first, with **No** as the default. A file that is not UTF-8 is shown with what cannot
be read replaced, and says so; saving writes it back as UTF-8.

Skill Prompt Editor
-------------------

**Menu:** Tools > AI > Skill Prompt Editor Tab / Dock > AI > Skill Prompt Editor Dock

The same editor as the CoT Prompt Editor, for the two skill prompts:
``code_review_skill.md`` (a code review) and ``code_explainer_skill.md`` (a code
explanation). Its files are kept in the same folder and work the same way.

Skill Send
----------

**Menu:** Tools > AI > Skill Send Tab / Dock > AI > Skill Send Dock

Interface Layout
^^^^^^^^^^^^^^^^

- **LLM API URL** -- the endpoint URL
- **Select Prompt Template** -- the skill prompt to start from
- **Prompt** -- the prompt that is sent, editable
- **Send** -- sends it
- **Response** (read-only) -- the answer, or why there is none

Usage
^^^^^

1. Enter the endpoint URL.
2. Choose a template. Its text (the edited file if there is one, otherwise the built-in
   prompt) fills **Prompt**. Choosing another template after editing the prompt asks
   first.
3. Put your code in place of ``{code_diff}`` in the prompt. The prompt is not sent while
   ``{code_diff}`` is still in it.
4. Click **Send**. The prompt goes as a ``POST`` of the JSON ``{"code": "..."}``, and the
   response body is shown as it is. A refused request (401, 403) and a server error are
   shown as errors; a redirect is not followed and says where it pointed (its scheme and
   host only).
