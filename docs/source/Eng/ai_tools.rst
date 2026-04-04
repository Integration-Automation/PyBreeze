AI Tools
========

PyBreeze integrates several AI-powered tools for code review, prompt engineering,
and LLM interaction. All AI tools are accessible from the **Tools** menu and can
be opened as either tabs or dock widgets.

AI Code-Review Client
---------------------

**Menu:** Tools > AI Code-Review Tab / AI Code-Review Dock

A client for sending code to an AI API endpoint for automated code review.

Interface Layout
^^^^^^^^^^^^^^^^

- **URL Input** -- Enter the API endpoint URL
- **Method Selector** -- Choose HTTP method (GET, POST, PUT, DELETE)
- **Code Input** (left panel) -- Paste or write code to be reviewed
- **Response Display** (right panel, read-only) -- Shows the AI review response
- **Send Request** button -- Sends the code to the API endpoint

Features
^^^^^^^^

- Tracks accept/reject statistics for AI responses
- Saves URL history to ``.pybreeze/urls.txt``
- Stores response statistics in ``.pybreeze/response_stats.txt``

Usage
^^^^^

1. Enter your AI API endpoint URL in the URL input field
2. Select the HTTP method (typically POST)
3. Paste the code you want reviewed in the left panel
4. Click **Send Request**
5. Review the AI's response in the right panel

CoT Code Review GUI
--------------------

**Menu:** Tools > AI Code-Review Tab / Dock

An advanced code review tool using Chain-of-Thought (CoT) prompting for
more structured and detailed reviews.

Interface Layout
^^^^^^^^^^^^^^^^

- **API URL Input** -- Enter the API endpoint URL
- **Code Area** -- Paste code for review
- **Response Selector** (ComboBox) -- Browse through multiple review responses
- **Response Viewer** (read-only) -- Displays the selected review response
- **Send Button** -- Sends code for review

Features
^^^^^^^^

- Supports reviewing multiple files at once via ``SenderThread``
- Background threading prevents UI freezing during API calls
- Multiple responses can be stored and browsed

CoT Prompt Editor
-----------------

**Menu:** Tools > CoT Prompt Editor Tab / CoT Prompt Editor Dock

A template-based editor for creating and managing Chain-of-Thought prompt templates.

Interface Layout
^^^^^^^^^^^^^^^^

- **File Selector** (ComboBox) -- Select from available prompt template files
- **Edit Panel** (QTextEdit) -- Edit the selected prompt template
- **Create** button -- Creates a new prompt template file
- **Save** button -- Saves changes to the current template
- **Reload** button -- Reloads the template from disk

Features
^^^^^^^^

- Template-based file management with ``COT_TEMPLATE_RELATION`` mapping
- File system watcher for detecting external changes
- Auto-reloads templates when modified outside the editor
- Pre-configured templates for common CoT review patterns

Usage
^^^^^

1. Select a template from the dropdown or create a new one
2. Edit the prompt template in the text area
3. Click **Save** to persist your changes
4. The template can then be used in the CoT Code Review GUI

Skill Prompt Editor
-------------------

**Menu:** Tools > Skill Prompt Editor Tab / Skill Prompt Editor Dock

Similar to the CoT Prompt Editor, but specialized for skill-based prompt templates
such as code review and code explanation prompts.

Interface Layout
^^^^^^^^^^^^^^^^

- **File Selector** (ComboBox) -- Select from available skill prompt templates
- **Edit Panel** (QTextEdit) -- Edit the selected skill prompt
- **Create** button -- Creates a new skill prompt template
- **Save** button -- Saves changes
- **Reload** button -- Reloads from disk

Pre-built Skill Templates
^^^^^^^^^^^^^^^^^^^^^^^^^^

- Code Review prompts
- Code Explanation prompts

Skills Send GUI
---------------

**Menu:** Tools > Skill Send GUI Tab / Skill Prompt Dock

An interface for sending skill-based prompts to an LLM API and viewing responses.

Interface Layout
^^^^^^^^^^^^^^^^

- **API URL Input** -- Enter the LLM API endpoint URL
- **Prompt Template Selector** (ComboBox) -- Choose a pre-defined skill prompt template
- **Prompt Text Area** -- Edit or customize the prompt before sending
- **Send Button** -- Sends the prompt to the API (runs in background thread)
- **Response Display** (read-only) -- Shows the LLM response

Features
^^^^^^^^

- Background threading via ``RequestThread`` prevents UI freezing
- Error handling with specific HTTP status code messages
- Prompt templates are loaded from the Skill Prompt Editor's template files

Usage
^^^^^

1. Enter your LLM API endpoint URL
2. Select a prompt template from the dropdown
3. Customize the prompt text if needed (e.g., paste code to review)
4. Click **Send**
5. Wait for the response to appear in the response display area

.. note::

   All AI tools require a compatible API endpoint. Configure your API URL
   to point to your LLM service (e.g., OpenAI-compatible API, local LLM server, etc.).
